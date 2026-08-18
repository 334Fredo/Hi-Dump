#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hi-Dump - Convertisseur FLAC -> WAV (bit-perfect) et/ou MP3 (LAME V0)

(c) 2026 HiGRID - Tous droits reserves.
Contact : contact@higrid.eu   -   @334fredo
HiDump, HiGRID, le logo, la mascotte et la charte graphique sont la propriete
exclusive de HiGRID. Reproduction, diffusion ou modification interdites sans
autorisation ecrite prealable. Composants tiers (ffmpeg, LAME) soumis a leurs
licences respectives - voir MENTIONS-LEGALES.md.
============================================================================

Reproduit a l'identique l'arborescence de dossiers du repertoire source.

  SOURCE/Artiste/Album/01 - Titre.flac
     ->  DEST/WAV/Artiste/Album/01 - Titre.wav
     ->  DEST/MP3/Artiste/Album/01 - Titre.mp3

Garanties :
  * WAV = PCM natif decode du FLAC, MEME frequence d'echantillonnage,
    MEME profondeur de bits, MEME nombre de canaux. Aucun reechantillonnage,
    aucun dithering, aucune normalisation. Le resultat est bit-perfect
    (verifiable avec --verify).
  * MP3 = LAME VBR V0 (~245 kbps) par defaut, transparent a l'oreille.
    Reechantillonnage uniquement si indispensable (>48 kHz, limite du format
    MP3) et dans ce cas avec le resampler SoXR haute precision.
  * Tags (titre, artiste, album, annee, piste, etc.) et pochette integree
    recopies depuis le FLAC.
  * Reprise sur incident : les fichiers deja convertis sont ignores.
  * Ecriture atomique : un fichier n'apparait a destination que lorsqu'il est
    complet et valide (fichier temporaire .part puis renommage).

Dependance : ffmpeg + ffprobe (voir README.md).

Editeur : HiGRID.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------

VERSION = "3.0"
BRAND = "HiGRID"
YEAR = "2026"
COPYRIGHT = f"(c) {YEAR} {BRAND} - Tous droits reserves"

AUDIO_EXT = ".flac"

# Fichiers annexes recopies tels quels avec --copy-extras
EXTRA_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".cue", ".log", ".txt", ".nfo", ".m3u", ".m3u8", ".pdf", ".md",
}

# Frequences maximales supportees par le format MP3 (MPEG-1 Layer III)
MP3_MAX_RATE = 48000
MP3_RATES = (32000, 44100, 48000)

# Correspondance profondeur de bits -> codec PCM WAV
PCM_BY_DEPTH = {
    8:  "pcm_u8",
    16: "pcm_s16le",
    20: "pcm_s24le",   # 20 bits stockes dans un conteneur 24 bits
    24: "pcm_s24le",
    32: "pcm_s32le",
}

# Correspondance format d'echantillon ffmpeg -> codec PCM (repli)
PCM_BY_FMT = {
    "u8": "pcm_u8", "u8p": "pcm_u8",
    "s16": "pcm_s16le", "s16p": "pcm_s16le",
    "s32": "pcm_s32le", "s32p": "pcm_s32le",
    "flt": "pcm_f32le", "fltp": "pcm_f32le",
    "dbl": "pcm_f64le", "dblp": "pcm_f64le",
}

PRINT_LOCK = threading.Lock()


# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------

def log(msg: str) -> None:
    with PRINT_LOCK:
        print(msg, flush=True)


def find_tool(name: str, explicit: str | None = None) -> str:
    """Localise ffmpeg/ffprobe : option explicite, PATH, dossier du script,
    puis emplacements habituels sous Windows."""
    if explicit:
        p = Path(explicit)
        if p.is_dir():
            p = p / (name + (".exe" if os.name == "nt" else ""))
        if p.exists():
            return str(p)
        raise SystemExit(f"[ERREUR] {name} introuvable a l'emplacement indique : {explicit}")

    found = shutil.which(name)
    if found:
        return found

    candidates: list[Path] = []
    here = Path(__file__).resolve().parent
    exe = name + (".exe" if os.name == "nt" else "")
    candidates += [here / exe, here / "ffmpeg" / "bin" / exe, here / "bin" / exe]
    if os.name == "nt":
        for base in (r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin",
                     r"C:\ProgramData\chocolatey\bin"):
            candidates.append(Path(base) / exe)
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Microsoft" / "WinGet" / "Links" / exe)
    for c in candidates:
        if c.exists():
            return str(c)

    raise SystemExit(
        f"[ERREUR] {name} est introuvable.\n"
        "         Installez ffmpeg puis relancez. Le plus simple sous Windows :\n"
        "             winget install Gyan.FFmpeg\n"
        "         (puis fermez/rouvrez le terminal)\n"
        "         Ou passez le chemin manuellement : --ffmpeg \"C:\\ffmpeg\\bin\"")


def long_path(p: Path) -> str:
    """Contourne la limite historique de 260 caracteres de Windows."""
    s = str(p)
    if os.name == "nt" and len(s) >= 240 and not s.startswith("\\\\?\\"):
        if s.startswith("\\\\"):
            return "\\\\?\\UNC\\" + s[2:]
        return "\\\\?\\" + s
    return s


def human(n: float) -> str:
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}".replace(",", " ")
        n /= 1024
    return f"{n:.1f} Po"


def hms(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}h{m:02d}m{s:02d}s" if h else f"{m:d}m{s:02d}s"


# --------------------------------------------------------------------------
# Analyse du fichier source
# --------------------------------------------------------------------------

@dataclass
class Probe:
    sample_rate: int = 44100
    channels: int = 2
    depth: int = 16
    sample_fmt: str = "s16"
    has_cover: bool = False
    cover_codec: str = ""
    duration: float = 0.0


def probe(ffprobe: str, src: Path) -> Probe:
    cmd = [ffprobe, "-v", "error", "-print_format", "json",
           "-show_streams", "-show_format", long_path(src)]
    out = subprocess.run(cmd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe: {out.stderr.strip()[:400]}")
    data = json.loads(out.stdout or "{}")

    info = Probe()
    try:
        info.duration = float(data.get("format", {}).get("duration", 0) or 0)
    except (TypeError, ValueError):
        pass

    audio_found = False
    for st in data.get("streams", []):
        kind = st.get("codec_type")
        if kind == "audio" and not audio_found:
            audio_found = True
            info.sample_rate = int(st.get("sample_rate") or 44100)
            info.channels = int(st.get("channels") or 2)
            info.sample_fmt = st.get("sample_fmt") or "s16"
            depth = st.get("bits_per_raw_sample") or st.get("bits_per_sample") or 0
            try:
                info.depth = int(depth)
            except (TypeError, ValueError):
                info.depth = 0
        elif kind == "video":
            # dans un FLAC, un flux video = pochette integree
            info.has_cover = True
            info.cover_codec = st.get("codec_name") or ""

    if not audio_found:
        raise RuntimeError("aucun flux audio detecte")
    return info


def wav_codec(info: Probe) -> str:
    if info.depth in PCM_BY_DEPTH:
        return PCM_BY_DEPTH[info.depth]
    return PCM_BY_FMT.get(info.sample_fmt, "pcm_s24le")


def mp3_rate(rate: int) -> int | None:
    """Retourne la frequence cible MP3, ou None si aucune conversion n'est
    necessaire. Le format MP3 plafonne a 48 kHz."""
    if rate <= MP3_MAX_RATE:
        return None
    # 88.2 / 176.4 / 352.8 kHz -> 44.1 kHz ; le reste -> 48 kHz
    return 44100 if rate % 44100 == 0 else 48000


# --------------------------------------------------------------------------
# Construction des commandes ffmpeg
# --------------------------------------------------------------------------

def cmd_wav(ffmpeg: str, src: Path, dst: Path, info: Probe, keep_tags: bool) -> list[str]:
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
           "-i", long_path(src),
           "-map", "0:a:0",          # audio uniquement
           "-vn", "-sn", "-dn",      # pas de pochette / sous-titres / donnees
           "-c:a", wav_codec(info),  # PCM natif, aucune conversion
           "-ar", str(info.sample_rate),
           "-ac", str(info.channels)]
    # Au-dela de 4 Go ou en multicanal, RF64 est necessaire ; ffmpeg bascule seul
    cmd += ["-rf64", "auto"]
    cmd += ["-map_metadata", "0" if keep_tags else "-1"]
    # -f wav : le format est impose car le fichier temporaire se termine
    # par .part et non par .wav
    cmd += ["-write_bext", "0", "-f", "wav", long_path(dst)]
    return cmd


def cmd_mp3(ffmpeg: str, src: Path, dst: Path, info: Probe,
            quality: str, keep_tags: bool, keep_cover: bool) -> list[str]:
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
           "-i", long_path(src), "-map", "0:a:0"]

    cover = keep_cover and info.has_cover
    if cover:
        cmd += ["-map", "0:v:0"]
    else:
        cmd += ["-vn"]
    cmd += ["-sn", "-dn"]

    cmd += ["-c:a", "libmp3lame"]
    if quality.upper().startswith("V"):
        cmd += ["-q:a", quality[1:]]           # VBR : V0 = -q:a 0
    else:
        cmd += ["-b:a", quality]               # CBR : ex. 320k
    cmd += ["-compression_level", "0"]         # analyse LAME la plus poussee

    target = mp3_rate(info.sample_rate)
    if target:
        # SoXR, precision 28 bits, bande passante 95% : reechantillonnage
        # de qualite mastering (uniquement pour les sources > 48 kHz)
        cmd += ["-af", f"aresample=resampler=soxr:precision=28:"
                       f"cheby=1:out_sample_rate={target}"]
    if info.channels > 2:
        cmd += ["-ac", "2"]                    # MP3 : 2 canaux maximum

    if cover:
        # JPEG recopie tel quel ; PNG/autre reencode en JPEG (compatibilite
        # maximale des lecteurs et autoradios)
        if info.cover_codec in ("mjpeg", "jpeg", "jpegls"):
            cmd += ["-c:v", "copy"]
        else:
            cmd += ["-c:v", "mjpeg", "-q:v", "2", "-pix_fmt", "yuvj420p"]
        cmd += ["-disposition:v:0", "attached_pic", "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)"]

    cmd += ["-map_metadata", "0" if keep_tags else "-1"]
    cmd += ["-id3v2_version", "3", "-write_id3v1", "1"]
    cmd += ["-f", "mp3", long_path(dst)]
    return cmd


def pcm_md5(ffmpeg: str, path: Path, info: Probe) -> str:
    """Empreinte MD5 du flux PCM decode, dans un format commun aux deux
    fichiers : permet de prouver que le WAV est identique au FLAC."""
    codec = wav_codec(info)
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
           "-i", long_path(path), "-map", "0:a:0", "-vn",
           "-c:a", codec, "-f", "md5", "-"]
    out = subprocess.run(cmd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return ""
    return (out.stdout or "").strip().split("=")[-1]


# --------------------------------------------------------------------------
# Traitement d'un fichier
# --------------------------------------------------------------------------

@dataclass
class Result:
    src: Path
    status: str                    # ok | skip | error
    outputs: list[str] = field(default_factory=list)
    detail: str = ""
    src_bytes: int = 0
    out_bytes: int = 0
    duration: float = 0.0
    verified: str = ""             # ok | MISMATCH | ""


def run_ffmpeg(cmd: list[str]) -> None:
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000    # CREATE_NO_WINDOW
    res = subprocess.run(cmd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", **kwargs)
    if res.returncode != 0:
        lines = [ln.strip() for ln in (res.stderr or "").splitlines() if ln.strip()]
        msg = " / ".join(lines[-3:])[:400]
        raise RuntimeError(msg or f"ffmpeg a retourne le code {res.returncode}")


def convert_one(src: Path, root: Path, opts, tools) -> Result:
    ffmpeg, ffprobe = tools
    rel = src.relative_to(root)
    res = Result(src=src, status="ok")
    try:
        res.src_bytes = src.stat().st_size
    except OSError:
        pass

    try:
        info = probe(ffprobe, src)
    except Exception as exc:                                  # noqa: BLE001
        res.status = "error"
        res.detail = f"analyse impossible : {exc}"
        return res

    res.duration = info.duration
    jobs: list[tuple[str, Path, list[str]]] = []

    def temp_of(path: Path) -> Path:
        return path.with_name(path.name + ".part")

    # `force` contient les sources dont la sortie doit etre refaite meme si
    # elle existe deja (fichier obsolete ou doublon accepte par l'utilisateur)
    redo = opts.overwrite or src in (getattr(opts, "force", None) or ())

    if "wav" in opts.formats:
        dst = (opts.dest / opts.wav_dir / rel).with_suffix(".wav")
        if dst.exists() and not redo:
            res.outputs.append(str(dst) + " (deja present)")
        else:
            jobs.append(("wav", dst,
                         cmd_wav(ffmpeg, src, temp_of(dst), info, opts.tags)))

    if "mp3" in opts.formats:
        dst = (opts.dest / opts.mp3_dir / rel).with_suffix(".mp3")
        if dst.exists() and not redo:
            res.outputs.append(str(dst) + " (deja present)")
        else:
            jobs.append(("mp3", dst,
                         cmd_mp3(ffmpeg, src, temp_of(dst), info,
                                 opts.quality, opts.tags, opts.cover)))

    if not jobs:
        res.status = "skip"
        res.detail = "sorties deja presentes"
        return res

    if opts.dry_run:
        res.status = "skip"
        res.detail = "simulation"
        res.outputs = [str(d) for _, d, _ in jobs]
        return res

    for kind, dst, cmd in jobs:
        tmp_real = temp_of(dst)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            run_ffmpeg(cmd)
            if not tmp_real.exists() or tmp_real.stat().st_size == 0:
                raise RuntimeError("fichier de sortie vide")
            if dst.exists():
                dst.unlink()
            tmp_real.replace(dst)
            res.out_bytes += dst.stat().st_size
            res.outputs.append(str(dst))
            if kind == "wav" and opts.verify:
                a = pcm_md5(ffmpeg, src, info)
                b = pcm_md5(ffmpeg, dst, info)
                res.verified = "ok" if (a and a == b) else "MISMATCH"
                if res.verified == "MISMATCH":
                    res.status = "error"
                    res.detail = "verification MD5 PCM en echec"
        except Exception as exc:                              # noqa: BLE001
            res.status = "error"
            res.detail = f"[{kind}] {exc}"
            try:
                if tmp_real.exists():
                    tmp_real.unlink()
            except OSError:
                pass
            break

    return res


# --------------------------------------------------------------------------
# Rapport CSV (utilise par la ligne de commande ET par l'interface graphique)
# --------------------------------------------------------------------------

def write_report(results: list[Result], path: Path) -> Path | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["statut", "source", "taille_source_octets",
                        "taille_sortie_octets", "duree_s", "verification",
                        "sorties", "detail"])
            for r in sorted(results, key=lambda x: str(x.src)):
                w.writerow([r.status, str(r.src), r.src_bytes, r.out_bytes,
                            f"{r.duration:.3f}", r.verified,
                            " | ".join(r.outputs), r.detail])
        return path
    except OSError:
        return None


# --------------------------------------------------------------------------
# Fichiers annexes
# --------------------------------------------------------------------------

def copy_extras(root: Path, opts) -> int:
    n = 0
    targets = [opts.dest / opts.wav_dir] if "wav" in opts.formats else []
    if "mp3" in opts.formats:
        targets.append(opts.dest / opts.mp3_dir)
    for src in root.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in EXTRA_EXT:
            continue
        rel = src.relative_to(root)
        for base in targets:
            dst = base / rel
            if dst.exists() and not opts.overwrite:
                continue
            if opts.dry_run:
                n += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    return n


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hi-dump",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Convertit une arborescence FLAC en WAV (bit-perfect) "
                    "et/ou MP3 (LAME V0), hierarchie de dossiers preservee.",
        epilog="""Exemples
--------
  python hidump_engine.py "D:\\Musique\\FLAC" "E:\\Sortie"
  python hidump_engine.py "D:\\Musique" "E:\\Sortie" --formats mp3 --quality V0
  python hidump_engine.py "D:\\Musique" "E:\\Sortie" --verify --jobs 8
  python hidump_engine.py "D:\\Musique" "E:\\Sortie" --dry-run
""")
    p.add_argument("source", type=Path, help="dossier racine contenant les FLAC")
    p.add_argument("dest", type=Path, help="dossier de destination")
    p.add_argument("--formats", default="both",
                   choices=["both", "wav", "mp3"],
                   help="formats a produire (defaut : both)")
    p.add_argument("--quality", default="V0",
                   help="qualite MP3 : V0..V9 (VBR) ou 320k, 256k... (CBR). Defaut : V0")
    p.add_argument("--jobs", "-j", type=int, default=0,
                   help="conversions simultanees (defaut : nb de coeurs, max 8)")
    p.add_argument("--overwrite", action="store_true",
                   help="reecrire les fichiers deja presents")
    p.add_argument("--verify", action="store_true",
                   help="verifier que le WAV est bit-perfect (MD5 du PCM, plus lent)")
    p.add_argument("--no-tags", dest="tags", action="store_false",
                   help="ne pas recopier les metadonnees")
    p.add_argument("--no-cover", dest="cover", action="store_false",
                   help="ne pas integrer la pochette dans les MP3")
    p.add_argument("--copy-extras", action="store_true",
                   help="recopier aussi pochettes .jpg, .cue, .log, .txt...")
    p.add_argument("--flat", action="store_true",
                   help="ne pas creer les sous-dossiers WAV/ et MP3/ "
                        "(possible uniquement avec un seul format)")
    p.add_argument("--wav-dir", default="WAV", help="nom du sous-dossier WAV")
    p.add_argument("--mp3-dir", default="MP3", help="nom du sous-dossier MP3")
    p.add_argument("--dry-run", action="store_true",
                   help="simulation : n'ecrit rien, affiche ce qui serait fait")
    p.add_argument("--report", type=Path, default=None,
                   help="chemin du rapport CSV (defaut : <dest>/_rapport_conversion.csv)")
    p.add_argument("--ffmpeg", default=None, help="chemin de ffmpeg (ou de son dossier)")
    p.add_argument("--ffprobe", default=None, help="chemin de ffprobe (ou de son dossier)")
    p.add_argument("--version", action="version",
                   version=f"Hi-Dump {VERSION} - {COPYRIGHT}")
    return p


def main(argv: list[str] | None = None) -> int:
    opts = build_parser().parse_args(argv)

    opts.formats = ["wav", "mp3"] if opts.formats == "both" else [opts.formats]
    if opts.flat:
        if len(opts.formats) > 1:
            print("[ERREUR] --flat est incompatible avec deux formats de sortie.")
            return 2
        opts.wav_dir = opts.mp3_dir = ""

    source: Path = opts.source.expanduser().resolve()
    opts.dest = opts.dest.expanduser().resolve()
    if not source.is_dir():
        print(f"[ERREUR] Dossier source introuvable : {source}")
        return 2
    if opts.dest == source or opts.dest in source.parents:
        print("[ERREUR] La destination ne doit pas contenir la source.")
        return 2

    ffmpeg = find_tool("ffmpeg", opts.ffmpeg)
    ffprobe = find_tool("ffprobe", opts.ffprobe)

    files = sorted(p for p in source.rglob("*")
                   if p.is_file() and p.suffix.lower() == AUDIO_EXT)
    if not files:
        print(f"[INFO] Aucun fichier .flac trouve dans {source}")
        return 1

    jobs = opts.jobs or min(8, os.cpu_count() or 4)
    total_src = sum(f.stat().st_size for f in files)

    print("=" * 74)
    print(f" Hi-Dump {VERSION}   -   (c) {YEAR} {BRAND} - Tous droits reserves")
    print("=" * 74)
    print(f" Source      : {source}")
    print(f" Destination : {opts.dest}")
    print(f" Formats     : {', '.join(f.upper() for f in opts.formats)}"
          + (f"   (MP3 : {opts.quality})" if "mp3" in opts.formats else ""))
    print(f" Fichiers    : {len(files)}  ({human(total_src)})")
    print(f" Simultane   : {jobs} conversion(s)")
    if opts.verify:
        print(" Verification: MD5 du flux PCM active (plus lent)")
    if opts.dry_run:
        print(" MODE SIMULATION - aucun fichier ne sera ecrit")
    print("=" * 74)

    results: list[Result] = []
    started = time.time()
    done = 0

    with futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        pending = {pool.submit(convert_one, f, source, opts, (ffmpeg, ffprobe)): f
                   for f in files}
        for fut in futures.as_completed(pending):
            res = fut.result()
            results.append(res)
            done += 1
            rel = res.src.relative_to(source)
            mark = {"ok": "  OK  ", "skip": " SAUT ", "error": "ERREUR"}[res.status]
            extra = ""
            if res.verified == "ok":
                extra = "  [bit-perfect]"
            elif res.status == "error":
                extra = f"  -> {res.detail}"
            log(f"[{done:>{len(str(len(files)))}}/{len(files)}] {mark}  {rel}{extra}")

    elapsed = time.time() - started
    ok = [r for r in results if r.status == "ok"]
    skipped = [r for r in results if r.status == "skip"]
    errors = [r for r in results if r.status == "error"]
    out_bytes = sum(r.out_bytes for r in ok)
    audio_time = sum(r.duration for r in results)

    extras = copy_extras(source, opts) if opts.copy_extras else 0

    report = opts.report or (opts.dest / "_rapport_conversion.csv")
    if not opts.dry_run:
        report = write_report(results, report)
        if report is None:
            print("[AVERTISSEMENT] Le rapport CSV n'a pas pu etre ecrit.")

    print("=" * 74)
    print(f" Termine en {hms(elapsed)}"
          + (f"  ({hms(audio_time)} d'audio traite)" if audio_time else ""))
    print(f" Convertis : {len(ok)}    Ignores : {len(skipped)}    Erreurs : {len(errors)}")
    if extras:
        print(f" Fichiers annexes copies : {extras}")
    if out_bytes:
        ratio = (out_bytes / total_src * 100) if total_src else 0
        print(f" Volume ecrit : {human(out_bytes)}  ({ratio:.0f} % de la source)")
    if opts.verify:
        bad = [r for r in ok if r.verified == "MISMATCH"]
        good = [r for r in ok if r.verified == "ok"]
        print(f" Verification bit-perfect : {len(good)} conforme(s), {len(bad)} ecart(s)")
    if report and not opts.dry_run:
        print(f" Rapport CSV : {report}")
    if errors:
        print("-" * 74)
        print(" Fichiers en erreur :")
        for r in errors[:25]:
            print(f"   - {r.src}\n       {r.detail}")
        if len(errors) > 25:
            print(f"   ... et {len(errors) - 25} autre(s), voir le rapport CSV.")
    print("=" * 74)

    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INTERROMPU] Relancez la meme commande pour reprendre "
              "la ou vous en etiez.")
        sys.exit(130)
