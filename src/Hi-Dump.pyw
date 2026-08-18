#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hi-Dump - Convertisseur FLAC vers WAV (bit-perfect) et MP3 (LAME)
=================================================================

(c) 2026 HiGRID - Tous droits reserves.
Contact : contact@higrid.eu   -   @334fredo

Hi-Dump, le nom HiGRID, le logo, la mascotte, la charte graphique et les
habillages ("skins") sont la propriete exclusive de HiGRID. Toute
reproduction, diffusion, modification ou reutilisation, totale ou partielle,
du present logiciel ou de ces elements d'identite, est interdite sans
autorisation ecrite prealable de HiGRID.

Les composants tiers (ffmpeg, LAME, polices Anton / Archivo / Space Mono)
restent soumis a leurs licences respectives - voir MENTIONS-LEGALES.md.

Interface graphique du moteur `hidump_engine.py`.

Lancement :
    Hi-Dump.exe                     (Windows, autonome)
    Hi-Dump.app                     (macOS, autonome)
    pythonw Hi-Dump.pyw             (depuis les sources)
"""

from __future__ import annotations

import concurrent.futures as futures
import json
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox

APP_NAME = "Hi-Dump"
BRAND = "HiGRID"
YEAR = "2026"
CONTACT = "contact@higrid.eu"
AUTHOR = "334fredo"
COPYRIGHT = f"© {YEAR} {BRAND}"

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RES_DIR = Path(getattr(sys, "_MEIPASS", str(APP_DIR)))

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

try:
    import hidump_engine as engine
except Exception as exc:
    _r = tk.Tk()
    _r.withdraw()
    messagebox.showerror(APP_NAME,
                         "Le moteur 'hidump_engine.py' est introuvable.\n\n"
                         f"Detail : {exc}")
    sys.exit(1)


def res(*parts) -> Path:
    return RES_DIR.joinpath(*parts)


def _appdata() -> Path:
    """Dossier de reglages, aux conventions de chaque systeme."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".hidump"


DATA_DIR = _appdata()
BIN_DIR = DATA_DIR / "bin"
CFG_PATH = DATA_DIR / "config.json"

MAC_STATIC = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0"
FFB = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v6.1"
BTBN = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest")


def ffmpeg_recipes():
    """Sources de telechargement de ffmpeg, de la plus legere a la plus sure.

    Chaque recette est une liste d'adresses : archive zip, archive tar.xz ou
    binaire brut. L'extraction reconnait les trois cas.
    """
    if sys.platform == "darwin":
        arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
        return [
            (f"build natif macOS {arch}",
             [f"{MAC_STATIC}/ffmpeg-darwin-{arch}",
              f"{MAC_STATIC}/ffprobe-darwin-{arch}"]),
            ("build macOS intel",
             [f"{FFB}/ffmpeg-6.1-macos-64.zip", f"{FFB}/ffprobe-6.1-macos-64.zip"]),
            ("evermeet.cx",
             ["https://evermeet.cx/ffmpeg/getrelease/zip",
              "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"]),
        ]
    if os.name == "nt":
        return [
            ("essentials (~35 Mo)",
             ["https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"]),
            ("shared (~77 Mo)", [f"{BTBN}-win64-gpl-shared.zip"]),
            ("static (~165 Mo)", [f"{BTBN}-win64-gpl.zip"]),
        ]
    return [("static linux64", [f"{BTBN}-linux64-gpl.tar.xz"])]


EXE = ".exe" if os.name == "nt" else ""


# ==========================================================================
#  Langues
# ==========================================================================

LANG = "fr"

STRINGS = {
    "tagline":        ("FLAC → WAV BIT-PERFECT · MP3 LAME VBR",
                       "FLAC → WAV BIT-PERFECT · MP3 LAME VBR"),
    "engine_ok":      ("● MOTEUR AUDIO OPÉRATIONNEL", "● AUDIO ENGINE READY"),
    "engine_ko":      ("● MOTEUR AUDIO MANQUANT", "● AUDIO ENGINE MISSING"),
    "skin":           ("SKIN", "SKIN"),
    "lang":           ("LANGUE", "LANG"),
    "p_folders":      ("DOSSIERS", "FOLDERS"),
    "p_output":       ("SORTIE", "OUTPUT"),
    "p_options":      ("OPTIONS", "OPTIONS"),
    "p_console":      ("CONSOLE", "CONSOLE"),
    "source":         ("SOURCE", "SOURCE"),
    "dest":           ("DESTINATION", "DESTINATION"),
    "browse":         ("PARCOURIR", "BROWSE"),
    "formats":        ("FORMATS", "FORMATS"),
    "quality":        ("QUALITÉ MP3", "MP3 QUALITY"),
    "threads":        ("THREADS", "THREADS"),
    "cores":          ("cœurs : {n}", "cores: {n}"),
    "q_hint":         ("V0 = réglage recommandé · le WAV, lui, n'est jamais compressé",
                       "V0 = recommended · WAV itself is never compressed"),
    "q_tip":          ("Débit de l'encodage MP3.\n\n"
                       "Le débit (kbps) n'est pas l'échantillonnage. La "
                       "fréquence d'échantillonnage reste 44,1 kHz, identique "
                       "au FLAC d'origine, quel que soit le réglage choisi "
                       "ici : le débit ne décrit que la quantité de données "
                       "conservée par seconde de musique.\n\n"
                       "V0 * débit variable, ~245 kbps de moyenne. "
                       "L'encodeur descend sur les passages simples et monte "
                       "jusqu'à 320 kbps sur les passages difficiles.\n\n"
                       "V2 * débit variable, ~190 kbps de moyenne. Même "
                       "principe, budget plus serré. Fichiers environ 25 % "
                       "plus légers que V0.\n\n"
                       "320k CBR * débit constant : 320 kbps partout, y "
                       "compris sur un silence ou une note tenue, où il n'y a "
                       "rien à coder. Environ 30 % plus lourd que V0 sans "
                       "avantage audible démontré, puisque V0 atteint déjà "
                       "320 kbps là où c'est utile. Son intérêt réel est la "
                       "compatibilité avec certains lecteurs anciens qui "
                       "gèrent mal le débit variable.\n\n"
                       "En clair : V0 par défaut, V2 si la place manque, "
                       "320k CBR si un appareil l'exige.",
                       "MP3 bitrate.\n\n"
                       "Bitrate (kbps) is not the sample rate. The sample "
                       "rate stays at 44.1 kHz, same as the source FLAC, "
                       "whatever you pick here: bitrate only describes how "
                       "much data is kept per second of music.\n\n"
                       "V0 * variable bitrate, ~245 kbps on average. The "
                       "encoder drops on simple passages and climbs to "
                       "320 kbps on hard ones.\n\n"
                       "V2 * variable bitrate, ~190 kbps on average. Same "
                       "principle, tighter budget. Files about 25 % smaller "
                       "than V0.\n\n"
                       "320k CBR * constant bitrate: 320 kbps everywhere, "
                       "including a silence or a held note where there is "
                       "nothing to encode. About 30 % larger than V0 with no "
                       "demonstrated audible advantage, since V0 already "
                       "reaches 320 kbps where it matters. Its real value is "
                       "compatibility with some older players that handle "
                       "variable bitrate poorly.\n\n"
                       "In short: V0 by default, V2 when space is tight, "
                       "320k CBR when a device demands it."),
    "f_tip":          ("Ce que contient chaque format.\n\n"
                       "WAV * PCM brut, aucune compression. Même fréquence "
                       "d'échantillonnage, même profondeur de bits, même "
                       "nombre de canaux que le FLAC : le signal est "
                       "identique au bit près. L'option de vérification le "
                       "prouve fichier par fichier.\n\n"
                       "FLAC * compressé, mais sans perte. Il occupe 50 à "
                       "60 % de la taille du WAV et son décodage redonne "
                       "exactement les mêmes échantillons. Un WAV plus lourd "
                       "ne contient donc pas plus de musique, seulement moins "
                       "de compression.\n\n"
                       "MP3 * compressé avec perte. Des informations jugées "
                       "inaudibles sont écartées définitivement. Parfait pour "
                       "l'écoute au quotidien, à ne jamais utiliser comme "
                       "source d'une nouvelle conversion : partez toujours du "
                       "FLAC ou du WAV.",
                       "What each format holds.\n\n"
                       "WAV * raw PCM, no compression at all. Same sample "
                       "rate, same bit depth, same channel count as the FLAC: "
                       "the signal is identical down to the bit. The verify "
                       "option proves it file by file.\n\n"
                       "FLAC * compressed, but losslessly. It takes 50 to "
                       "60 % of the WAV size and decoding gives back exactly "
                       "the same samples. A heavier WAV does not hold more "
                       "music, just less compression.\n\n"
                       "MP3 * lossy compression. Information judged inaudible "
                       "is discarded for good. Fine for everyday listening, "
                       "never to be used as the source of another conversion: "
                       "always start from FLAC or WAV."),
    "t_hint":         ("plus de threads = plus rapide, PC plus chargé",
                       "more threads = faster, heavier on the PC"),
    "t_tip":          ("Nombre de fichiers convertis en même temps.\n\n"
                       "Chaque thread occupe un cœur du processeur. Plus il y "
                       "en a, plus la conversion est rapide - mais la machine "
                       "devient moins réactive pour le reste.\n\n"
                       "Règle simple : autant de threads que de cœurs, et "
                       "moitié moins si vous voulez continuer à travailler "
                       "pendant la conversion.\n\n"
                       "La qualité du résultat est identique quel que soit ce "
                       "réglage.",
                       "How many files are converted at the same time.\n\n"
                       "Each thread uses one CPU core. More threads means a "
                       "faster job, but a less responsive machine.\n\n"
                       "Rule of thumb: as many threads as cores, or half that "
                       "if you want to keep working during the conversion.\n\n"
                       "Output quality is identical whatever you pick."),
    "o_verify":       ("Vérifier chaque WAV en bit-perfect (plus lent)",
                       "Check every WAV is bit-perfect (slower)"),
    "o_extras":       ("Copier aussi pochettes, .cue, .log, .txt",
                       "Also copy artwork, .cue, .log, .txt"),
    "o_tags":         ("Conserver tags et pochettes intégrées",
                       "Keep tags and embedded artwork"),
    "o_over":         ("Écraser les fichiers déjà convertis",
                       "Overwrite files already converted"),
    "b_start":        ("▶  LANCER LA CONVERSION", "▶  START CONVERSION"),
    "b_stop":         ("■  ARRÊTER", "■  STOP"),
    "b_open":         ("OUVRIR", "OPEN"),
    "b_shortcut":     ("RACCOURCI BUREAU", "DESKTOP SHORTCUT"),
    "b_about":        ("À PROPOS", "ABOUT"),
    "b_install":      ("INSTALLER FFMPEG", "INSTALL FFMPEG"),
    "b_installing":   ("INSTALLATION…", "INSTALLING…"),
    "b_choose":       ("CHOISIR…", "CHOOSE…"),
    "b_close":        ("FERMER", "CLOSE"),
    "setup_msg":      ("ffmpeg n'est pas installé sur ce PC - un clic suffit.",
                       "ffmpeg is not installed on this PC - one click is enough."),
    "st_idle":        ("EN ATTENTE", "IDLE"),
    "st_init":        ("» INITIATION DE SÉQUENCE", "» SEQUENCE INITIATION"),
    "st_dl":          ("TÉLÉCHARGEMENT DE FFMPEG…", "DOWNLOADING FFMPEG…"),
    "st_ready":       ("FFMPEG INSTALLÉ - PRÊT", "FFMPEG INSTALLED - READY"),
    "st_dl_fail":     ("ÉCHEC DE L'INSTALLATION", "INSTALLATION FAILED"),
    "st_done":        ("» TERMINÉ SANS ERREUR", "» COMPLETED WITHOUT ERROR"),
    "st_done_err":    ("» TERMINÉ · {n} ERREUR(S)", "» COMPLETED · {n} ERROR(S)"),
    "st_stopped":     ("INTERROMPU", "STOPPED"),
    "st_stopping":    ("ARRÊT DEMANDÉ…", "STOPPING…"),
    "c_ready":        ("{app} prêt. Sélectionnez un dossier source.",
                       "{app} ready. Pick a source folder."),
    "c_engine":       ("  moteur audio : {path}", "  audio engine: {path}"),
    "c_noffmpeg1":    ("ffmpeg est absent de ce PC.",
                       "ffmpeg is missing on this PC."),
    "c_noffmpeg2":    ("Cliquez sur « INSTALLER FFMPEG » : l'application le "
                       "télécharge et l'installe seule.",
                       "Click “INSTALL FFMPEG”: the application downloads and "
                       "installs it on its own."),
    "c_scan":         ("Analyse : {n} fichier(s) FLAC · {size}",
                       "Scan: {n} FLAC file(s) · {size}"),
    "c_src":          (" SOURCE      {v}", " SOURCE      {v}"),
    "c_dst":          (" DESTINATION {v}", " DESTINATION {v}"),
    "c_fmt":          (" FORMATS     {v}", " FORMATS     {v}"),
    "c_files":        (" FICHIERS    {n}   ·   THREADS {j}{extra}",
                       " FILES       {n}   ·   THREADS {j}{extra}"),
    "c_verify_on":    ("   ·   VÉRIFICATION MD5 ACTIVE", "   ·   MD5 CHECK ON"),
    "c_skipped":      ("  {n} fichier(s) déjà converti(s) - ignoré(s).",
                       "  {n} file(s) already converted - skipped."),
    "c_dupskip":      ("  {n} doublon(s) de nom ignoré(s).",
                       "  {n} duplicate name(s) skipped."),
    "c_redo":         ("  {n} fichier(s) obsolète(s) seront reconverti(s).",
                       "  {n} outdated file(s) will be converted again."),
    "c_already":      ("  ·  {v}   (déjà converti)", "  ·  {v}   (already converted)"),
    "c_extras_n":     ("  Fichiers annexes copiés : {n}",
                       "  Extra files copied: {n}"),
    "c_done":         (" TERMINÉ en {t}  ·  {ok} converti(s)  ·  {sk} ignoré(s)"
                       "  ·  {er} erreur(s)",
                       " DONE in {t}  ·  {ok} converted  ·  {sk} skipped"
                       "  ·  {er} error(s)"),
    "c_volume":       (" Volume écrit : {v}", " Data written: {v}"),
    "c_report":       (" Rapport CSV : {v}", " CSV report: {v}"),
    "c_thanks":       (" HiGRID vous remercie - bonne écoute.",
                       " HiGRID thanks you - enjoy the music."),
    "c_thanks2":      (" Une question, un bug, une idée ?   {a}   ·   {c}",
                       " A question, a bug, an idea?   {a}   ·   {c}"),
    "c_stopped":      (" INTERROMPU · {ok} converti(s) en {t}. Relancez pour "
                       "reprendre où vous en étiez.",
                       " STOPPED · {ok} converted in {t}. Run it again to "
                       "resume where you left off."),
    "c_install":      (" Installation de ffmpeg - 1 à 3 minutes selon la "
                       "connexion.",
                       " Installing ffmpeg - 1 to 3 minutes depending on your "
                       "connection."),
    "c_installed":    (" ffmpeg est installé. Vous pouvez lancer la conversion.",
                       " ffmpeg is installed. You can start the conversion."),
    "c_dlfail1":      (" Le téléchargement a échoué (pas de connexion ?).",
                       " Download failed (no connection?)."),
    "c_dlfail2":      (" Solution manuelle : téléchargez ffmpeg sur "
                       "gyan.dev/ffmpeg/builds puis cliquez « CHOISIR… ».",
                       " Manual fix: download ffmpeg from gyan.dev/ffmpeg/builds "
                       "then click “CHOOSE…”."),
    "d_nosrc":        ("Dossier source introuvable.", "Source folder not found."),
    "d_nested":       ("La destination ne doit pas contenir la source.",
                       "The destination must not contain the source."),
    "d_noflac":       ("Aucun fichier .flac dans ce dossier.",
                       "No .flac file in this folder."),
    "d_noffmpeg":     ("ffmpeg n'est pas encore installé.\n\nVoulez-vous "
                       "l'installer maintenant ?",
                       "ffmpeg is not installed yet.\n\nDo you want to install "
                       "it now?"),
    "d_noprobe":      ("ffprobe est introuvable à côté de ffmpeg.\nLes deux "
                       "fichiers doivent être dans le même dossier.",
                       "ffprobe was not found next to ffmpeg.\nBoth files must "
                       "sit in the same folder."),
    "d_quit":         ("Une conversion est en cours.\nQuitter quand même ?",
                       "A conversion is running.\nQuit anyway?"),
    "d_dup_t":        ("Doublons de noms", "Duplicate names"),
    "d_dup":          ("{n} fichier(s) source différents produiraient le même "
                       "fichier de sortie :\n\n{ex}\n\nOUI  =  tout convertir "
                       "(le dernier écrase le précédent)\nNON  =  ne convertir "
                       "que le premier de chaque doublon\nANNULER  =  ne rien "
                       "faire",
                       "{n} different source file(s) would produce the same "
                       "output file:\n\n{ex}\n\nYES  =  convert everything (the "
                       "last one overwrites)\nNO  =  convert only the first of "
                       "each duplicate\nCANCEL  =  do nothing"),
    "d_stale_t":      ("Fichiers à revoir", "Files worth checking"),
    "d_stale":        ("{n} fichier(s) sont déjà présents à destination, mais "
                       "le FLAC source a été modifié depuis leur "
                       "conversion :\n\n{ex}\n\nOUI  =  les reconvertir\n"
                       "NON  =  les garder tels quels",
                       "{n} file(s) already exist in the destination, but the "
                       "source FLAC changed after they were "
                       "converted:\n\n{ex}\n\nYES  =  convert them again\n"
                       "NO  =  keep them as they are"),
    "d_over_t":       ("Écrasement", "Overwrite"),
    "d_over":         ("L'option « écraser » est active : {n} fichier(s) déjà "
                       "convertis seront remplacés.\n\nContinuer ?",
                       "The “overwrite” option is on: {n} already converted "
                       "file(s) will be replaced.\n\nContinue?"),
    "d_short_ok":     ("Raccourci créé sur le Bureau :\n{v}",
                       "Shortcut created on the Desktop:\n{v}"),
    "d_short_ko":     ("Le raccourci n'a pas pu être créé. Vous pouvez glisser "
                       "l'application sur le Bureau ou dans le Dock.",
                       "The shortcut could not be created. You can drag the "
                       "application onto the Desktop or into the Dock."),
    "d_short_win":    ("Raccourci Bureau : Windows et macOS uniquement.",
                       "Desktop shortcut: Windows and macOS only."),
    "a_title":        ("VERSION {v}   ·   ÉDITION {b}", "VERSION {v}   ·   {b} EDITION"),
    "a_body":         ("""{cop} - Tous droits réservés

{app}, {b}, le logo, la mascotte et la charte graphique sont la propriété exclusive de {b}. Toute reproduction, diffusion, modification ou réutilisation, totale ou partielle, du logiciel ou de ces éléments d'identité est interdite sans autorisation écrite préalable de {b}.

Le code source, l'architecture de conversion et les habillages livrés avec l'application demeurent la propriété de {b}.

CONTACT - licences, partenariats, signalements :
  ·  {mail}
  ·  {auth}

COMPOSANTS TIERS - conservent leurs licences respectives :
  ·  FFmpeg / FFprobe - moteur de décodage et d'encodage (LGPL/GPL)
  ·  LAME - encodeur MP3 (LGPL)
  ·  Anton, Archivo, Space Mono - SIL Open Font License 1.1
  ·  Python / Tcl-Tk - licences PSF et BSD

Ces composants sont utilisés sans modification ; leurs textes de licence figurent dans MENTIONS-LEGALES.md.""",
                       """{cop} - All rights reserved

{app}, {b}, the logo, the mascot and the visual identity are the exclusive property of {b}. Any reproduction, distribution, modification or reuse, in whole or in part, of the software or of these identity elements is forbidden without prior written permission from {b}.

The source code, the conversion architecture and the skins shipped with the application remain the property of {b}.

CONTACT - licensing, partnerships, reports:
  ·  {mail}
  ·  {auth}

THIRD-PARTY COMPONENTS - keep their own licences:
  ·  FFmpeg / FFprobe - decoding and encoding engine (LGPL/GPL)
  ·  LAME - MP3 encoder (LGPL)
  ·  Anton, Archivo, Space Mono - SIL Open Font License 1.1
  ·  Python / Tcl-Tk - PSF and BSD licences

These components are used without modification; their licence texts are listed in MENTIONS-LEGALES.md."""),
    "f_left":         ("{cop} - Tous droits réservés   ·   {app} v{v}",
                       "{cop} - All rights reserved   ·   {app} v{v}"),
    "f_right":        ("{mail}   ·   conçu par {auth}",
                       "{mail}   ·   crafted by {auth}"),
}


def human(n: float) -> str:
    """Taille de fichier dans les unites de la langue courante."""
    units = ("o", "Ko", "Mo", "Go", "To") if LANG == "fr" else \
            ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}".replace(",", " ")
        n /= 1024
    return f"{n:.1f} {units[-1]}"


def tr(key: str, **kw) -> str:
    fr, en = STRINGS[key]
    text = fr if LANG == "fr" else en
    return text.format(**kw) if kw else text


# ==========================================================================
#  Skins
# ==========================================================================

SKINS = {
    # Charte HiGRID : noir, creme, rouge, rouge sombre, gris chaud
    "HIGRID": {
        "bg": "#0B0B0B", "panel": "#141312", "panel_hi": "#1E1B19",
        "line": "#2C2823", "text": "#EFEBE3", "dim": "#807A6F",
        "accent": "#E11D17", "accent2": "#8E0F0B", "ok": "#EFEBE3",
        "warn": "#E1A317", "err": "#E11D17", "console": "#080808",
        "logo": "logo88.png", "banner": "banniere.png",
    },
    "CYBERPUNK": {
        "bg": "#06060d", "panel": "#0c0c18", "panel_hi": "#12122a",
        "line": "#1e1e3a", "text": "#d8d8f0", "dim": "#5c5c85",
        "accent": "#00f0ff", "accent2": "#a259ff", "ok": "#05ffa1",
        "warn": "#ffcc00", "err": "#ff2a6d", "console": "#04040a",
        "logo": "logo88.png", "banner": "banniere.png",
    },
    "OFFGRID": {
        "bg": "#EFEBE3", "panel": "#FFFFFF", "panel_hi": "#F6F2EA",
        "line": "#D6D0C6", "text": "#0B0B0B", "dim": "#807A6F",
        "accent": "#E11D17", "accent2": "#8E0F0B", "ok": "#1E7A3C",
        "warn": "#A8730B", "err": "#8E0F0B", "console": "#FFFFFF",
        "logo": "logo88_light.png", "banner": "banniere_light.png",
    },
}

SCALE = 1.0
FONT_DISPLAY = "Anton"
FONT_BODY = "Archivo"
FONT_MONO = "Space Mono"


def S(v: float) -> int:
    return int(round(v * SCALE))


def FD(size: int):
    return (FONT_DISPLAY, size)


def FB(size: int, bold: bool = False):
    return (FONT_BODY, size, "bold") if bold else (FONT_BODY, size)


def FM(size: int, bold: bool = False):
    return (FONT_MONO, size, "bold") if bold else (FONT_MONO, size)


def load_fonts(root: tk.Tk) -> None:
    """Charge Anton / Archivo / Space Mono livrees avec l'application."""
    global FONT_DISPLAY, FONT_BODY, FONT_MONO
    folder = res("assets", "fonts")
    files = sorted(folder.glob("*.ttf")) if folder.is_dir() else []

    if files and os.name == "nt":
        try:
            import ctypes
            FR_PRIVATE = 0x10
            for f in files:
                ctypes.windll.gdi32.AddFontResourceExW(str(f), FR_PRIVATE, 0)
        except Exception:
            pass
    elif files:
        try:
            # macOS : dossier de polices de l'utilisateur ; Linux : ~/.fonts
            dest = (Path.home() / "Library" / "Fonts") if sys.platform == "darwin" \
                else (Path.home() / ".fonts")
            dest.mkdir(parents=True, exist_ok=True)
            changed = False
            for f in files:
                if not (dest / f.name).exists():
                    shutil.copy2(f, dest / f.name)
                    changed = True
            if changed and sys.platform != "darwin":
                subprocess.run(["fc-cache", "-f"], capture_output=True, timeout=60)
        except Exception:
            pass

    available = {name.lower() for name in tkfont.families(root)}

    def pick(preferred, fallbacks):
        if preferred.lower() in available:
            return preferred
        for fb in fallbacks:
            if fb.lower() in available:
                return fb
        return preferred

    FONT_DISPLAY = pick("Anton", ["Impact", "Arial Black", "Helvetica Neue",
                                  "DejaVu Sans", "Helvetica"])
    FONT_BODY = pick("Archivo", ["Segoe UI", "Helvetica Neue", "DejaVu Sans",
                                 "Helvetica"])
    FONT_MONO = pick("Space Mono", ["Consolas", "Menlo", "DejaVu Sans Mono",
                                    "Courier"])


# ==========================================================================
#  Widgets
# ==========================================================================

class Panel(tk.Canvas):
    """Base des widgets dessines : garde une reference au theme."""

    def __init__(self, master, theme, width, height, **kw):
        self.T = theme
        super().__init__(master, width=S(width), height=S(height),
                         bg=kw.pop("canvas_bg", theme["bg"]),
                         highlightthickness=0, bd=0, **kw)
        self.cw, self.ch = S(width), S(height)


class Tip:
    """Bulle d'aide : apparait au survol, disparait a la sortie."""

    _open = None

    def __init__(self, widget, theme, text, delay=350, width=340):
        self.w, self.T, self.text = widget, theme, text
        self.delay, self.width = delay, width
        self.after_id = None
        self.win = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._toggle, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self.after_id = self.w.after(self.delay, self._show)

    def _cancel(self):
        if self.after_id:
            try:
                self.w.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _toggle(self, _=None):
        if self.win:
            self._hide()
        else:
            self._show()

    def _show(self):
        if self.win:
            return
        if Tip._open is not None:
            Tip._open._hide()
        T = self.T
        self.win = tk.Toplevel(self.w)
        self.win.wm_overrideredirect(True)
        self.win.configure(bg=T["accent"])
        inner = tk.Frame(self.win, bg=T["panel"])
        inner.pack(padx=1, pady=1)
        tk.Label(inner, text=self.text, bg=T["panel"], fg=T["text"],
                 font=FB(9), justify="left", wraplength=S(self.width),
                 padx=S(12), pady=S(10)).pack()
        self.win.update_idletasks()
        x = self.w.winfo_rootx() + self.w.winfo_width() + S(10)
        y = self.w.winfo_rooty() - S(6)
        sw = self.w.winfo_screenwidth()
        if x + self.win.winfo_width() > sw - S(10):
            x = max(S(10), self.w.winfo_rootx() - self.win.winfo_width() - S(10))
        self.win.wm_geometry(f"+{x}+{y}")
        Tip._open = self

    def _hide(self, _=None):
        self._cancel()
        if self.win:
            self.win.destroy()
            self.win = None
        if Tip._open is self:
            Tip._open = None


class InfoBadge(Panel):
    """Petite pastille « ? » porteuse d'une bulle d'aide."""

    def __init__(self, master, theme, text):
        super().__init__(master, theme, 16, 16)
        self._hover = False
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self.draw()), add="+")
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self.draw()), add="+")
        self.configure(cursor="question_arrow")
        Tip(self, theme, text)
        self.draw()

    def draw(self):
        self.delete("all")
        T = self.T
        col = T["accent"] if self._hover else T["dim"]
        self.create_oval(S(1), S(1), S(14), S(14), outline=col, width=1,
                         fill=T["panel_hi"] if self._hover else T["bg"])
        self.create_text(S(7.5), S(8), text="?", fill=col, font=FM(7, True))


class Button(Panel):
    def __init__(self, master, theme, text, command=None, color=None,
                 width=150, height=32, size=9, canvas_bg=None):
        super().__init__(master, theme, width, height,
                         canvas_bg=canvas_bg or theme["bg"])
        self.command = command
        self.color = color or theme["accent"]
        self.text = text
        self.font = FM(size, True)
        self._enabled = True
        self._hover = False
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self.draw()))
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self.draw()))
        self.bind("<Button-1>", lambda e: self._enabled and self.draw(True))
        self.bind("<ButtonRelease-1>", self._release)
        self.configure(cursor="hand2")
        self.draw()

    def draw(self, pressed=False):
        self.delete("all")
        w, h, c = self.cw, self.ch, S(7)
        col = self.color if self._enabled else self.T["dim"]
        if pressed or (self._hover and self._enabled):
            fill, fg = col, self.T["bg"]
        else:
            fill, fg = self.T["panel"], col
        self.create_polygon([c, 1, w - 1, 1, w - 1, h - c, w - c, h - 1, 1, h - 1, 1, c],
                            fill=fill, outline=col, width=1)
        self.create_text(w // 2, h // 2 + 1, text=self.text, fill=fg, font=self.font)

    def _release(self, _=None):
        if not self._enabled:
            return
        self.draw()
        if self.command:
            self.command()

    def set_text(self, text, color=None):
        self.text = text
        if color:
            self.color = color
        self.draw()

    def set_enabled(self, state: bool):
        self._enabled = bool(state)
        self.configure(cursor="hand2" if state else "arrow")
        self.draw()


class Toggle(Panel):
    def __init__(self, master, theme, text, group, value, color=None,
                 width=110, height=26):
        super().__init__(master, theme, width, height)
        self.text, self.group, self.value = text, group, value
        self.color = color or theme["accent"]
        self._hover = False
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self.draw()))
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self.draw()))
        self.bind("<Button-1>", lambda e: self.group.select(self.value))
        self.configure(cursor="hand2")
        self.draw()

    def draw(self):
        self.delete("all")
        w, h, c = self.cw, self.ch, S(6)
        on = self.group.get() == self.value
        if on:
            fill, fg, out = self.color, self.T["bg"], self.color
        elif self._hover:
            fill, fg, out = self.T["panel_hi"], self.color, self.color
        else:
            fill, fg, out = self.T["panel"], self.T["dim"], self.T["line"]
        self.create_polygon([c, 1, w - 1, 1, w - 1, h - c, w - c, h - 1, 1, h - 1, 1, c],
                            fill=fill, outline=out, width=1)
        self.create_text(w // 2, h // 2 + 1, text=self.text, fill=fg, font=FM(8, True))


class ToggleGroup:
    def __init__(self, default, on_change=None):
        self._value = default
        self._items = []
        self.on_change = on_change

    def add(self, item):
        self._items.append(item)

    def get(self):
        return self._value

    def select(self, value):
        self._value = value
        for it in self._items:
            try:
                it.draw()
            except tk.TclError:
                pass
        if self.on_change:
            self.on_change(value)


class Check(Panel):
    def __init__(self, master, theme, text, color=None, checked=False, width=300):
        super().__init__(master, theme, width, 22)
        self.text = text
        self.color = color or theme["accent"]
        self._on = checked
        self._hover = False
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self.draw()))
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self.draw()))
        self.bind("<Button-1>", lambda e: self.toggle())
        self.configure(cursor="hand2")
        self.draw()

    def draw(self):
        self.delete("all")
        col = self.color if (self._on or self._hover) else self.T["dim"]
        self.create_rectangle(S(2), S(4), S(16), S(18), outline=col, width=1,
                              fill=self.color if self._on else self.T["panel"])
        if self._on:
            self.create_line(S(5), S(11), S(8), S(15), fill=self.T["bg"], width=S(2))
            self.create_line(S(8), S(15), S(13), S(7), fill=self.T["bg"], width=S(2))
        self.create_text(S(24), S(11), text=self.text, anchor="w",
                         fill=self.T["text"] if self._on else self.T["dim"],
                         font=FB(9))

    def toggle(self):
        self._on = not self._on
        self.draw()

    def get(self):
        return self._on

    def set(self, v):
        self._on = bool(v)
        self.draw()


class GlyphStrip(Panel):
    """Barre de progression ecrite en glyphes.

    Chaque cellule est un glyphe angulaire genere a partir du NOM du fichier
    correspondant : la barre est donc litteralement la liste des morceaux,
    transcrite. Les glyphes en attente restent en filigrane, ceux traites
    s'allument, et un curseur balaye la position courante.
    """

    def __init__(self, master, theme, width=876, height=26, cell=11):
        super().__init__(master, theme, width, height)
        self.cellw = S(cell)
        self.gap = S(4)
        self.n = max(8, int((self.cw + self.gap) // (self.cellw + self.gap)))
        self.seeds = [self._seed(f"hidump-{i}") for i in range(self.n)]
        self.names = []
        self._ratio = 0.0
        self._color = theme["accent"]
        self._cursor = -1
        self._blink = 0
        self.sweep = -1                 # >= 0 pendant la sequence d'initiation
        self.draw()

    @staticmethod
    def _seed(text: str) -> int:
        h = 2166136261
        for ch in text:                 # FNV-1a : stable d'une session a l'autre
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
        return h

    def set_files(self, names):
        """Encode la liste des fichiers dans les glyphes de la barre."""
        self.names = list(names)
        if not self.names:
            return
        step = max(1, len(self.names) / self.n)
        self.seeds = [self._seed(self.names[min(len(self.names) - 1,
                                                int(i * step))] + str(i))
                      for i in range(self.n)]
        self.draw()

    def set(self, ratio, color=None):
        self._ratio = max(0.0, min(1.0, ratio))
        if color:
            self._color = color
        self.draw()

    def pulse(self):
        self._blink = (self._blink + 1) % 4
        self._cursor = int(self._ratio * self.n)
        self.draw()

    def _glyph(self, x, seed, col, weight):
        """Dessine un glyphe dans la cellule commencant en x."""
        w, h = self.cellw, self.ch
        top, bot = S(3), h - S(3)
        mid = (top + bot) // 2
        lw = max(1, S(weight))
        left, right = x + S(1), x + w - S(3)

        b = seed

        # hampe principale : hauteur variable selon le glyphe, pour que la
        # bande se lise comme une ecriture et non comme une trame reguliere
        variant = (b >> 10) & 3
        if variant == 1:
            y0, y1 = top, mid + S(3)
        elif variant == 2:
            y0, y1 = mid - S(3), bot
        else:
            y0, y1 = top, bot
        self.create_line(left, y0, left, y1, fill=col, width=lw + S(1))

        if b & 1:                                   # barre haute
            self.create_line(left, top, right, top, fill=col, width=lw)
        if b & 2:                                   # barre basse
            self.create_line(left, bot, right, bot, fill=col, width=lw)
        if b & 4:                                   # encoche mediane
            self.create_line(left, mid, right - S(2), mid, fill=col, width=lw)
        if b & 8:                                   # montant droit complet
            self.create_line(right, top, right, bot, fill=col, width=lw)
        elif b & 16:                                # demi-montant droit
            ya, yb = (top, mid) if b & 32 else (mid, bot)
            self.create_line(right, ya, right, yb, fill=col, width=lw)
        if b & 64:                                  # point
            cy = top + S(2) if b & 128 else bot - S(2)
            self.create_oval(right - S(1), cy - S(1), right + S(1), cy + S(1),
                             fill=col, outline=col)
        if b & 256:                                 # dent de peigne
            y = mid - S(3) if b & 512 else mid + S(3)
            self.create_line(left, y, left + S(4), y, fill=col, width=lw)
        if (b >> 12) & 1:                           # point detache
            cx = left + (w - S(4)) // 2
            cy = top - S(1) if (b >> 13) & 1 else bot + S(1)
            cy = max(S(1), min(h - S(2), cy))
            self.create_oval(cx - S(1), cy - S(1), cx + S(1), cy + S(1),
                             fill=col, outline=col)

    def draw(self):
        self.delete("all")
        n = self.n
        filled = self._ratio * n
        for i in range(n):
            x = i * (self.cellw + self.gap)
            if self.sweep >= 0:                     # sequence d'initiation
                if i <= self.sweep:
                    col, weight = self._color, 2
                elif i <= self.sweep + 2:
                    col, weight = self.T["text"], 2
                else:
                    col, weight = self.T["line"], 1
            elif i < int(filled):                   # deja converti : allume
                col, weight = self._color, 2
            elif i == self._cursor and self._ratio > 0:
                col = self.T["text"] if self._blink < 2 else self.T["accent2"]
                weight = 2
            else:                                   # en attente : filigrane
                col, weight = self.T["line"], 1
            self._glyph(x, self.seeds[i], col, weight)

        y = self.ch - S(1)
        self.create_line(0, y, self.cw, y, fill=self.T["panel"], width=S(2))
        if self._ratio > 0:
            self.create_line(0, y, max(S(2), self.cw * self._ratio), y,
                             fill=self._color, width=S(2))


# ==========================================================================
#  ffmpeg
# ==========================================================================

def locate_tools() -> tuple[str | None, str | None]:
    for folder in (APP_DIR, APP_DIR / "ffmpeg" / "bin", BIN_DIR):
        f, p = folder / f"ffmpeg{EXE}", folder / f"ffprobe{EXE}"
        if f.exists() and p.exists():
            return str(f), str(p)
    f, p = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if f and p:
        return f, p
    if os.name == "nt":
        bases = (r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin",
                 r"C:\ProgramData\chocolatey\bin")
    else:
        # Homebrew (Apple Silicon et Intel), MacPorts, installations manuelles
        bases = ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin",
                 "/usr/bin", str(Path.home() / "bin"))
    for base in bases:
        f, p = Path(base) / f"ffmpeg{EXE}", Path(base) / f"ffprobe{EXE}"
        if f.exists() and p.exists():
            return str(f), str(p)
    return None, None


def _fetch(url: str, dest: Path, progress, log) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        got, last = 0, 0.0
        while True:
            chunk = resp.read(262144)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            if total:
                progress(got / total)
                if time.time() - last > 1.5:
                    last = time.time()
                    log(f"    {human(got)} / {human(total)}")
            else:
                progress(0.5)


def _wanted(name: str) -> bool:
    base = Path(name).name.lower()
    if base in (f"ffmpeg{EXE}", f"ffprobe{EXE}", "ffmpeg", "ffprobe"):
        return True
    return os.name == "nt" and base.endswith(".dll")


def _extract(archive: Path, url: str, dest_dir: Path) -> None:
    """Deballe une archive zip / tar.xz, ou recopie un binaire brut."""
    with open(archive, "rb") as fh:
        magic = fh.read(8)

    if magic[:2] == b"PK":
        with zipfile.ZipFile(archive) as z:
            for m in z.namelist():
                if m.endswith("/") or not _wanted(m):
                    continue
                if "ffplay" in m.lower():
                    continue
                with z.open(m) as src, open(dest_dir / Path(m).name, "wb") as out:
                    shutil.copyfileobj(src, out)
        return

    if (magic[:6] == b"\xfd7zXZ\x00" or magic[:2] == b"\x1f\x8b"
            or url.endswith((".tar.xz", ".tar.gz", ".tgz"))):
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                if not m.isfile() or not _wanted(m.name) or "ffplay" in m.name.lower():
                    continue
                src = t.extractfile(m)
                if src is None:
                    continue
                with src, open(dest_dir / Path(m.name).name, "wb") as out:
                    shutil.copyfileobj(src, out)
        return

    # binaire brut : le nom de fichier vient de l'adresse
    name = Path(url).name.split("-")[0].split(".")[0]
    if name not in ("ffmpeg", "ffprobe"):
        raise ValueError(f"archive non reconnue : {Path(url).name}")
    shutil.copyfile(archive, dest_dir / (name + EXE))


def download_ffmpeg(progress, log) -> tuple[str | None, str | None]:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_DIR / "ffmpeg_download.tmp"
    target_ff, target_fp = BIN_DIR / f"ffmpeg{EXE}", BIN_DIR / f"ffprobe{EXE}"

    for label, urls in ffmpeg_recipes():
        try:
            log(f"  ffmpeg - {label}")
            for url in urls:
                _fetch(url, tmp, progress, log)
                _extract(tmp, url, BIN_DIR)
            try:
                tmp.unlink()
            except OSError:
                pass

            if target_ff.exists() and target_fp.exists():
                if os.name != "nt":
                    target_ff.chmod(0o755)
                    target_fp.chmod(0o755)
                    if sys.platform == "darwin":
                        # binaire telecharge par l'application : pas de mise en
                        # quarantaine, mais on nettoie l'attribut par securite
                        subprocess.run(["xattr", "-dr", "com.apple.quarantine",
                                        str(BIN_DIR)], capture_output=True)
                chk = subprocess.run([str(target_ff), "-version"],
                                     capture_output=True, text=True, timeout=30)
                if chk.returncode == 0:
                    log(f"  > {BIN_DIR}")
                    return str(target_ff), str(target_fp)
        except Exception as exc:
            log(f"  {type(exc).__name__} : {str(exc)[:120]}")
    return None, None


def make_desktop_shortcut() -> Path | None:
    """Raccourci sur le Bureau : .lnk sous Windows, lien vers l'application
    sous macOS."""
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    if not desktop.exists():
        desktop = Path.home() / "Bureau"
    if not desktop.exists():
        return None

    if sys.platform == "darwin":
        # dans un paquet .app, l'executable est .../HiDump.app/Contents/MacOS/
        bundle = None
        for parent in APP_DIR.parents:
            if parent.suffix == ".app":
                bundle = parent
                break
        target = bundle or APP_DIR
        link = desktop / (target.name if bundle else f"{APP_NAME}.command")
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target)
        return link

    if os.name != "nt":
        return None

    target = Path(sys.executable)
    args = "" if FROZEN else f'"{APP_DIR / "Hi-Dump.pyw"}"'
    link = desktop / f"{APP_NAME}.lnk"
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
          f"$s.TargetPath='{target}';$s.Arguments='{args}';"
          f"$s.WorkingDirectory='{APP_DIR}';$s.IconLocation='{target}';"
          f"$s.Description='{APP_NAME} - {BRAND}';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   capture_output=True, text=True, creationflags=0x08000000)
    return link if link.exists() else None


# ==========================================================================
#  Application
# ==========================================================================

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False
        self.installing = False
        self.total = self.done = 0
        self.started = 0.0
        self.last_dest: Path | None = None
        self.ffmpeg = self.ffprobe = None
        self._imgs = []
        self._status = ("st_idle", "dim", None, {})
        self.log_model = []

        global LANG
        self.cfg = self._load_cfg()
        LANG = self.cfg.get("lang", "fr")
        if LANG not in ("fr", "en"):
            LANG = "fr"
        self.skin = self.cfg.get("skin", "HIGRID")
        if self.skin not in SKINS:
            self.skin = "HIGRID"
        self.T = SKINS[self.skin]

        root.title(f"{APP_NAME}  ·  FLAC → WAV / MP3")
        root.geometry(f"{S(920)}x{S(930)}")
        root.minsize(S(900), S(820))

        self._build()
        self._check_tools()
        self.root.after(90, self._drain)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------- skin / langue
    def _rebuild(self):
        state = self._snapshot()
        for child in list(self.root.winfo_children()):
            child.destroy()
        self._imgs.clear()
        self._build()
        self._restore(state)
        self._save_cfg()

    def _switch_skin(self, name):
        if name != self.skin:
            self.skin = name
            self.T = SKINS[name]
            self._rebuild()

    def _switch_lang(self, code):
        global LANG
        if code != LANG:
            LANG = code
            self._rebuild()

    def _snapshot(self):
        return {
            "src": self.e_src.get(), "dst": self.e_dst.get(),
            "fmt": self.g_fmt.get(), "qua": self.g_qua.get(),
            "jobs": self.g_jobs.get(), "verify": self.c_verify.get(),
            "extras": self.c_extras.get(), "tags": self.c_tags.get(),
            "over": self.c_over.get(),
            "counter": self.lbl_counter.cget("text"),
            "ratio": self.bar._ratio, "names": self.bar.names,
        }

    def _restore(self, st):
        self.e_src.delete(0, "end")
        self.e_src.insert(0, st["src"])
        self.e_dst.delete(0, "end")
        self.e_dst.insert(0, st["dst"])
        self.g_fmt.select(st["fmt"])
        self.g_qua.select(st["qua"])
        self.g_jobs.select(st["jobs"])
        self.c_verify.set(st["verify"])
        self.c_extras.set(st["extras"])
        self.c_tags.set(st["tags"])
        self.c_over.set(st["over"])
        self.lbl_counter.configure(text=st["counter"])
        if st.get("names"):
            self.bar.set_files(st["names"])
        self.bar.set(st["ratio"])
        self._refresh_tools_label()
        if self.running:
            self.btn_go.set_enabled(False)
            self.btn_stop.set_enabled(True)
        if self.last_dest and self.last_dest.exists():
            self.btn_open.set_enabled(True)

    # -------------------------------------------------------------- layout
    def _img(self, name):
        path = res("assets", name)
        if not path.exists():
            return None
        try:
            img = tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None
        self._imgs.append(img)
        return img

    def _panel(self, parent, title, expand=False):
        T = self.T
        wrap = tk.Frame(parent, bg=T["bg"])
        wrap.pack(fill="both" if expand else "x", expand=expand,
                  padx=S(22), pady=(S(9), 0))
        head = tk.Frame(wrap, bg=T["bg"])
        head.pack(fill="x")
        tk.Label(head, text=title, bg=T["bg"], fg=T["accent"],
                 font=FM(8, True)).pack(side="left")
        tk.Frame(head, bg=T["line"], height=1).pack(
            side="left", fill="x", expand=True, padx=(S(10), 0), pady=(S(8), 0))
        body = tk.Frame(wrap, bg=T["bg"])
        body.pack(fill="both" if expand else "x", expand=expand, pady=(S(7), 0))
        return body

    def _entry(self, parent):
        T = self.T
        box = tk.Frame(parent, bg=T["line"], padx=1, pady=1)
        e = tk.Entry(box, bg=T["panel"], fg=T["text"], insertbackground=T["accent"],
                     relief="flat", font=FB(9), highlightthickness=0)
        e.pack(fill="x", ipady=S(6), ipadx=S(8))
        return box, e

    def _label(self, parent, text, width=12):
        return tk.Label(parent, text=text, bg=self.T["bg"], fg=self.T["dim"],
                        font=FM(8, True), width=width, anchor="w")

    def _build(self):
        T = self.T
        r = self.root
        r.configure(bg=T["bg"])

        # ---- en-tete
        head = tk.Frame(r, bg=T["bg"])
        head.pack(fill="x", padx=S(22), pady=(S(14), 0))
        logo = self._img(T["logo"])
        if logo:
            tk.Label(head, image=logo, bg=T["bg"], bd=0).pack(side="left",
                                                              padx=(0, S(14)))
        title = tk.Frame(head, bg=T["bg"])
        title.pack(side="left", anchor="w")
        tk.Label(title, text=APP_NAME, bg=T["bg"], fg=T["accent"],
                 font=FD(38)).pack(anchor="w")
        tk.Label(title, text=tr("tagline"), bg=T["bg"], fg=T["dim"],
                 font=FM(8)).pack(anchor="w")
        banner = self._img(T["banner"])
        if banner:
            tk.Label(head, image=banner, bg=T["bg"], bd=0).pack(side="right")

        # ---- barre de controle : etat moteur, langue, skin
        ctrl = tk.Frame(r, bg=T["bg"])
        ctrl.pack(fill="x", padx=S(22), pady=(S(8), 0))
        self.lbl_tools = tk.Label(ctrl, text="", bg=T["bg"], fg=T["dim"], font=FM(8))
        self.lbl_tools.pack(side="left")

        self.g_skin = ToggleGroup(self.skin, self._switch_skin)
        for name in ("OFFGRID", "CYBERPUNK", "HIGRID"):
            t = Toggle(ctrl, T, name, self.g_skin, name, T["accent2"], width=92)
            t.pack(side="right", padx=(S(5), 0))
            self.g_skin.add(t)
        tk.Label(ctrl, text=tr("skin"), bg=T["bg"], fg=T["dim"],
                 font=FM(8, True)).pack(side="right", padx=(S(16), S(8)))

        self.g_lang = ToggleGroup(LANG, self._switch_lang)
        for code, label in (("en", "EN"), ("fr", "FR")):
            t = Toggle(ctrl, T, label, self.g_lang, code, T["accent"], width=48)
            t.pack(side="right", padx=(S(5), 0))
            self.g_lang.add(t)
        tk.Label(ctrl, text=tr("lang"), bg=T["bg"], fg=T["dim"],
                 font=FM(8, True)).pack(side="right", padx=(0, S(8)))

        self.sep = tk.Frame(r, bg=T["accent"], height=S(3))
        self.sep.pack(fill="x", padx=S(22), pady=(S(8), 0))

        # ---- bandeau ffmpeg
        self.setup_bar = tk.Frame(r, bg=T["bg"])
        inner = tk.Frame(self.setup_bar, bg=T["panel"],
                         highlightbackground=T["warn"], highlightthickness=1)
        inner.pack(fill="x")
        tk.Label(inner, bg=T["panel"], fg=T["warn"], font=FB(9, True),
                 justify="left", text=tr("setup_msg")).pack(side="left",
                                                            padx=S(12), pady=S(10))
        self.btn_install = Button(inner, T, tr("b_install"), self._install_ffmpeg,
                                  T["warn"], 200, 32, canvas_bg=T["panel"])
        self.btn_install.pack(side="right", padx=S(10), pady=S(8))
        self.btn_manual = Button(inner, T, tr("b_choose"), self._pick_ffmpeg,
                                 T["dim"], 110, 32, canvas_bg=T["panel"])
        self.btn_manual.pack(side="right", pady=S(8))

        # ---- dossiers
        body = self._panel(r, tr("p_folders"))
        row = tk.Frame(body, bg=T["bg"])
        row.pack(fill="x")
        self._label(row, tr("source")).pack(side="left")
        box, self.e_src = self._entry(row)
        box.pack(side="left", fill="x", expand=True)
        Button(row, T, tr("browse"), self._pick_src, T["accent"], 118, 30).pack(
            side="left", padx=(S(8), 0))

        row = tk.Frame(body, bg=T["bg"])
        row.pack(fill="x", pady=(S(8), 0))
        self._label(row, tr("dest")).pack(side="left")
        box, self.e_dst = self._entry(row)
        box.pack(side="left", fill="x", expand=True)
        Button(row, T, tr("browse"), self._pick_dst, T["accent"], 118, 30).pack(
            side="left", padx=(S(8), 0))

        # ---- sortie
        body = self._panel(r, tr("p_output"))
        row = tk.Frame(body, bg=T["bg"])
        row.pack(fill="x")
        self._label(row, tr("formats")).pack(side="left")
        self.g_fmt = ToggleGroup(self.cfg.get("fmt", "both"), lambda v: self._sync_quality())
        for label, val, w in (("WAV + MP3", "both", 118), ("WAV", "wav", 86),
                              ("MP3", "mp3", 86)):
            t = Toggle(row, T, label, self.g_fmt, val, T["accent"], width=w)
            t.pack(side="left", padx=(0, S(6)))
            self.g_fmt.add(t)
        InfoBadge(row, T, tr("f_tip")).pack(side="left", padx=(S(4), 0))

        row = tk.Frame(body, bg=T["bg"])
        row.pack(fill="x", pady=(S(8), 0))
        self._label(row, tr("quality")).pack(side="left")
        self.g_qua = ToggleGroup(self.cfg.get("qua", "V0"))
        for label, val in (("V0 ~245k", "V0"), ("V2 ~190k", "V2"), ("320k CBR", "320k")):
            t = Toggle(row, T, label, self.g_qua, val, T["accent2"], width=100)
            t.pack(side="left", padx=(0, S(6)))
            self.g_qua.add(t)
        InfoBadge(row, T, tr("q_tip")).pack(side="left", padx=(S(4), S(8)))
        self.lbl_qua = tk.Label(row, text="", bg=T["bg"], fg=T["dim"], font=FM(8))
        self.lbl_qua.pack(side="left")

        # ---- options
        body = self._panel(r, tr("p_options"))
        grid = tk.Frame(body, bg=T["bg"])
        grid.pack(fill="x")
        left = tk.Frame(grid, bg=T["bg"])
        left.pack(side="left", fill="x", expand=True)
        right = tk.Frame(grid, bg=T["bg"])
        right.pack(side="left", fill="x", expand=True)
        self.c_verify = Check(left, T, tr("o_verify"), T["ok"],
                              self.cfg.get("verify", False), 410)
        self.c_verify.pack(anchor="w")
        self.c_extras = Check(left, T, tr("o_extras"), T["accent2"],
                              self.cfg.get("extras", True), 410)
        self.c_extras.pack(anchor="w", pady=(S(4), 0))
        self.c_tags = Check(right, T, tr("o_tags"), T["accent"],
                            self.cfg.get("tags", True), 380)
        self.c_tags.pack(anchor="w")
        self.c_over = Check(right, T, tr("o_over"), T["err"],
                            self.cfg.get("over", False), 380)
        self.c_over.pack(anchor="w", pady=(S(4), 0))

        row = tk.Frame(body, bg=T["bg"])
        row.pack(fill="x", pady=(S(8), 0))
        self._label(row, tr("threads")).pack(side="left")
        self.g_jobs = ToggleGroup(str(self.cfg.get("jobs", min(8, os.cpu_count() or 4))))
        for n in ("1", "2", "4", "8", "12"):
            t = Toggle(row, T, n, self.g_jobs, n, T["accent2"], width=52)
            t.pack(side="left", padx=(0, S(6)))
            self.g_jobs.add(t)
        InfoBadge(row, T, tr("t_tip")).pack(side="left", padx=(S(4), S(8)))
        tk.Label(row, text=tr("cores", n=os.cpu_count() or "?"), bg=T["bg"],
                 fg=T["dim"], font=FM(8)).pack(side="left")
        Button(row, T, tr("b_shortcut"), self._make_shortcut, T["dim"],
               180, 26, 8).pack(side="right")

        # ---- actions
        act = tk.Frame(r, bg=T["bg"])
        act.pack(fill="x", padx=S(22), pady=(S(14), 0))
        self.btn_go = Button(act, T, tr("b_start"), self._start, T["accent"], 300, 44, 12)
        self.btn_go.pack(side="left")
        self.btn_stop = Button(act, T, tr("b_stop"), self._stop, T["accent2"], 150, 44, 12)
        self.btn_stop.pack(side="left", padx=(S(10), 0))
        self.btn_stop.set_enabled(False)
        self.btn_open = Button(act, T, tr("b_open"), self._open_dest, T["dim"], 130, 44, 12)
        self.btn_open.pack(side="left", padx=(S(10), 0))
        self.btn_open.set_enabled(False)

        prog = tk.Frame(r, bg=T["bg"])
        prog.pack(fill="x", padx=S(22), pady=(S(12), 0))
        self.bar = GlyphStrip(prog, T, width=876, height=26)
        self.bar.pack(fill="x")
        st = tk.Frame(r, bg=T["bg"])
        st.pack(fill="x", padx=S(22), pady=(S(6), 0))
        self.lbl_status = tk.Label(st, bg=T["bg"], fg=T["dim"], font=FM(8))
        self.lbl_status.pack(side="left")
        self.lbl_counter = tk.Label(st, text="", bg=T["bg"], fg=T["accent"], font=FM(8))
        self.lbl_counter.pack(side="right")

        # ---- pied de fenetre (toujours visible, ancre en bas)
        foot = tk.Frame(r, bg=T["bg"])
        foot.pack(side="bottom", fill="x", padx=S(22), pady=(S(6), S(9)))
        tk.Label(foot, text=tr("f_left", cop=COPYRIGHT, app=APP_NAME,
                               v=engine.VERSION),
                 bg=T["bg"], fg=T["dim"], font=FM(7)).pack(side="left")
        Button(foot, T, tr("b_about"), self._about, T["dim"], 96, 22, 7).pack(side="right")
        tk.Label(foot, text=tr("f_right", mail=CONTACT, auth=AUTHOR),
                 bg=T["bg"], fg=T["dim"], font=FM(7)).pack(side="right",
                                                           padx=(0, S(12)))

        # ---- console
        body = self._panel(r, tr("p_console"), expand=True)
        holder = tk.Frame(body, bg=T["line"], padx=1, pady=1)
        holder.pack(fill="both", expand=True)
        inner = tk.Frame(holder, bg=T["console"])
        inner.pack(fill="both", expand=True)
        self.log = tk.Text(inner, bg=T["console"], fg=T["text"], font=FM(8),
                           relief="flat", height=11, wrap="none", highlightthickness=0,
                           insertbackground=T["accent"], padx=S(10), pady=S(8))
        sb = tk.Scrollbar(inner, command=self.log.yview, bg=T["panel"],
                          troughcolor=T["bg"], relief="flat", bd=0,
                          activebackground=T["accent"], width=S(10))
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        for tag, col in (("ok", T["ok"]), ("err", T["err"]), ("skip", T["dim"]),
                         ("info", T["accent"]), ("warn", T["warn"]), ("dim", T["dim"])):
            self.log.tag_configure(tag, foreground=col)
        self.log.configure(state="disabled")
        self._render_log()

        self._sync_quality()
        self._refresh_tools_label()
        self._apply_status()

    # ------------------------------------------------------------- helpers
    def _set_status(self, key=None, role="dim", literal=None, **kw):
        self._status = (key, role, literal, kw)
        self._apply_status()

    def _apply_status(self):
        key, role, literal, kw = self._status
        text = literal if literal is not None else tr(key, **kw)
        self.lbl_status.configure(text=text, fg=self.T[role])
    def _say(self, tag, key=None, literal=None, **kw):
        """Ajoute une ligne a la console.

        La ligne est memorisee sous forme de cle + arguments : au changement
        de langue, tout l'historique est reecrit dans la nouvelle langue. Les
        lignes purement factuelles (noms de fichiers, separateurs) passent par
        `literal` et restent telles quelles.
        """
        self.log_model.append((tag, key, kw, literal))
        self._write(tag, key, kw, literal)

    def _write(self, tag, key, kw, literal):
        if "_bytes" in kw:                       # unite dependante de la langue
            kw = dict(kw)
            kw["v" if key == "c_volume" else "size"] = human(kw.pop("_bytes"))
        text = literal if literal is not None else tr(key, **kw)
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _render_log(self):
        """Reecrit toute la console (appele apres un changement de langue)."""
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        for tag, key, kw, literal in self.log_model:
            self._write(tag, key, kw, literal)

    def _clear_log(self):
        self.log_model = []
        self._render_log()

    def _sync_quality(self):
        mp3 = self.g_fmt.get() in ("both", "mp3")
        self.lbl_qua.configure(text=tr("q_hint") if mp3 else "")

    def _refresh_tools_label(self):
        if self.ffmpeg:
            self.lbl_tools.configure(text=tr("engine_ok"), fg=self.T["ok"])
            self.setup_bar.pack_forget()
        else:
            self.lbl_tools.configure(text=tr("engine_ko"), fg=self.T["warn"])
            self.setup_bar.pack(fill="x", padx=S(22), pady=(S(10), 0), after=self.sep)

    def _check_tools(self):
        self.ffmpeg, self.ffprobe = locate_tools()
        self._refresh_tools_label()
        if self.ffmpeg:
            self._say("info", "c_ready", app=APP_NAME)
            self._say("dim", "c_engine", path=self.ffmpeg)
        else:
            self._say("warn", "c_noffmpeg1")
            self._say("warn", "c_noffmpeg2")

    def _pick_ffmpeg(self):
        f = filedialog.askopenfilename(
            title=f"ffmpeg{EXE}",
            filetypes=[("ffmpeg", f"ffmpeg{EXE}"), ("*", "*.*")])
        if not f:
            return
        probe = Path(f).parent / f"ffprobe{EXE}"
        if not probe.exists():
            messagebox.showerror(APP_NAME, tr("d_noprobe"))
            return
        self.ffmpeg, self.ffprobe = f, str(probe)
        self._refresh_tools_label()
        self._say("ok", "c_engine", path=f)

    def _install_ffmpeg(self):
        if self.installing or self.running:
            return
        self.installing = True
        self.btn_install.set_enabled(False)
        self.btn_install.set_text(tr("b_installing"))
        self._set_status("st_dl", "warn")
        self._say("info", literal="─" * 92)
        self._say("info", "c_install")

        def work():
            f, p = download_ffmpeg(lambda x: self.q.put(("prog", x, self.T["warn"])),
                                   lambda m: self.q.put(("line", "dim", (None, {}, m))))
            self.q.put(("ffmpeg", (f, p), None))

        threading.Thread(target=work, daemon=True).start()

    def _make_shortcut(self):
        if os.name != "nt" and sys.platform != "darwin":
            messagebox.showinfo(APP_NAME, tr("d_short_win"))
            return
        try:
            link = make_desktop_shortcut()
        except Exception:
            link = None
        if link:
            self._say("ok", literal=f"  {link}")
            messagebox.showinfo(APP_NAME, tr("d_short_ok", v=link.name))
        else:
            messagebox.showwarning(APP_NAME, tr("d_short_ko"))

    def _pick_src(self):
        d = filedialog.askdirectory(title=tr("source"))
        if not d:
            return
        d = os.path.normpath(d)
        self.e_src.delete(0, "end")
        self.e_src.insert(0, d)
        if not self.e_dst.get().strip():
            self.e_dst.insert(0, d + "_converti")
        try:
            files = [p for p in Path(d).rglob("*")
                     if p.is_file() and p.suffix.lower() == ".flac"]
            size = sum(f.stat().st_size for f in files)
            self._say("info", "c_scan", n=len(files), _bytes=size)
        except OSError as exc:
            self._say("err", literal=str(exc))

    def _pick_dst(self):
        d = filedialog.askdirectory(title=tr("dest"))
        if d:
            self.e_dst.delete(0, "end")
            self.e_dst.insert(0, os.path.normpath(d))

    def _open_dest(self):
        if not self.last_dest or not self.last_dest.exists():
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(self.last_dest))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.last_dest)])
            else:
                subprocess.Popen(["xdg-open", str(self.last_dest)])
        except OSError as exc:
            messagebox.showinfo(APP_NAME, f"{self.last_dest}\n\n{exc}")

    def _about(self):
        T = self.T
        win = tk.Toplevel(self.root)
        win.title(f"{APP_NAME} - {tr('b_about')}")
        win.configure(bg=T["bg"])
        win.resizable(False, False)
        win.transient(self.root)

        pad = tk.Frame(win, bg=T["bg"])
        pad.pack(padx=S(24), pady=S(20))
        head = tk.Frame(pad, bg=T["bg"])
        head.pack(fill="x", anchor="w")
        logo = self._img(T["logo"])
        if logo:
            tk.Label(head, image=logo, bg=T["bg"], bd=0).pack(side="left",
                                                              padx=(0, S(14)))
        block = tk.Frame(head, bg=T["bg"])
        block.pack(side="left", anchor="w")
        tk.Label(block, text=APP_NAME, bg=T["bg"], fg=T["accent"],
                 font=FD(30)).pack(anchor="w")
        tk.Label(block, text=tr("a_title", v=engine.VERSION, b=BRAND),
                 bg=T["bg"], fg=T["dim"], font=FM(8)).pack(anchor="w")

        tk.Frame(pad, bg=T["accent"], height=S(2)).pack(fill="x", pady=(S(14), S(12)))

        body = tk.Frame(pad, bg=T["line"], padx=1, pady=1)
        body.pack(fill="both")
        txt = tk.Text(body, bg=T["panel"], fg=T["text"], font=FB(9), relief="flat",
                      width=64, height=22, wrap="word", highlightthickness=0,
                      padx=S(14), pady=S(12))
        txt.insert("1.0", tr("a_body", cop=COPYRIGHT, app=APP_NAME, b=BRAND,
                             mail=CONTACT, auth=AUTHOR))
        txt.configure(state="disabled")
        txt.pack()

        bar = tk.Frame(pad, bg=T["bg"])
        bar.pack(fill="x", pady=(S(14), 0))
        tk.Label(bar, text=f"{BRAND}™   ·   {CONTACT}   ·   {AUTHOR}", bg=T["bg"],
                 fg=T["dim"], font=FM(8, True)).pack(side="left")
        Button(bar, T, tr("b_close"), win.destroy, T["accent"], 120, 30).pack(side="right")

        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + S(60)
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    # -------------------------------------------------------------- config
    def _load_cfg(self) -> dict:
        try:
            return json.loads(CFG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_cfg(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CFG_PATH.write_text(json.dumps({
                "skin": self.skin, "lang": LANG,
                "src": self.e_src.get().strip(), "dst": self.e_dst.get().strip(),
                "fmt": self.g_fmt.get(), "qua": self.g_qua.get(),
                "jobs": int(self.g_jobs.get()), "verify": self.c_verify.get(),
                "extras": self.c_extras.get(), "tags": self.c_tags.get(),
                "over": self.c_over.get()}, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass

    # ---------------------------------------------------------- conversion
    def _make_opts(self, dest: Path):
        class Options:
            pass
        o = Options()
        fmt = self.g_fmt.get()
        o.formats = ["wav", "mp3"] if fmt == "both" else [fmt]
        o.dest = dest
        o.wav_dir = "WAV" if len(o.formats) > 1 else ""
        o.mp3_dir = "MP3" if len(o.formats) > 1 else ""
        o.overwrite = self.c_over.get()
        o.dry_run = False
        o.tags = self.c_tags.get()
        o.cover = self.c_tags.get()
        o.quality = self.g_qua.get()
        o.verify = self.c_verify.get()
        o.force = set()
        return o

    def _outputs_for(self, f: Path, src: Path, opts) -> list[Path]:
        rel = f.relative_to(src)
        outs = []
        if "wav" in opts.formats:
            outs.append((opts.dest / opts.wav_dir / rel).with_suffix(".wav"))
        if "mp3" in opts.formats:
            outs.append((opts.dest / opts.mp3_dir / rel).with_suffix(".mp3"))
        return outs

    def _plan(self, files, src, opts):
        """Compare la liste des fichiers a ce qui existe deja a destination.

        Renvoie (a_convertir, deja_faits, doublons_ignores) apres avoir
        interroge l'utilisateur dans les cas ambigus. Un fichier deja present
        et plus recent que sa source est considere comme deja converti ; s'il
        est plus ancien, la source a bouge depuis et la question est posee.
        """
        planned, seen, dups = [], {}, []
        for f in files:
            outs = self._outputs_for(f, src, opts)
            key = str(outs[0]).lower()
            if key in seen:
                dups.append(f)
                continue
            seen[key] = f
            planned.append((f, outs))

        if dups and not opts.overwrite:
            examples = "\n".join(f"  ·  {p.name}" for p in dups[:6])
            if len(dups) > 6:
                examples += f"\n  …"
            answer = messagebox.askyesnocancel(
                tr("d_dup_t"), tr("d_dup", n=len(dups), ex=examples))
            if answer is None:
                return None, None, None
            if answer:                       # tout convertir : le dernier gagne
                planned += [(f, self._outputs_for(f, src, opts)) for f in dups]
                opts.force.update(dups)
                dups = []

        done, stale, todo = [], [], []
        for f, outs in planned:
            existing = [o for o in outs if o.exists()]
            if len(existing) < len(outs):
                todo.append(f)               # sortie partielle : on complete
                continue
            try:
                src_mtime = f.stat().st_mtime
                outdated = any(o.stat().st_mtime < src_mtime - 2 or
                               o.stat().st_size == 0 for o in outs)
            except OSError:
                outdated = True
            (stale if outdated else done).append(f)

        if opts.overwrite:
            if done or stale:
                if not messagebox.askyesno(tr("d_over_t"),
                                           tr("d_over", n=len(done) + len(stale))):
                    return None, None, None
            return [f for f, _ in planned], [], dups

        if stale:
            examples = "\n".join(f"  ·  {p.name}" for p in stale[:6])
            if len(stale) > 6:
                examples += "\n  …"
            if messagebox.askyesno(tr("d_stale_t"),
                                   tr("d_stale", n=len(stale), ex=examples)):
                opts.force.update(stale)
                todo += stale
            else:
                done += stale

        return todo, done, dups

    def _start(self):
        if self.running or self.installing:
            return
        if not self.ffmpeg:
            if messagebox.askyesno(APP_NAME, tr("d_noffmpeg")):
                self._install_ffmpeg()
            return
        src = Path(self.e_src.get().strip()).expanduser()
        if not src.is_dir():
            messagebox.showerror(APP_NAME, tr("d_nosrc"))
            return
        dst_txt = self.e_dst.get().strip()
        dest = Path(dst_txt).expanduser() if dst_txt else src.parent / (src.name + "_converti")
        src, dest = src.resolve(), dest.resolve()
        if dest == src or dest in src.parents:
            messagebox.showerror(APP_NAME, tr("d_nested"))
            return
        allfiles = sorted(p for p in src.rglob("*")
                          if p.is_file() and p.suffix.lower() == ".flac")
        if not allfiles:
            messagebox.showwarning(APP_NAME, tr("d_noflac"))
            return

        opts = self._make_opts(dest)
        todo, done, dups = self._plan(allfiles, src, opts)
        if todo is None:                     # l'utilisateur a annule
            return

        self.e_dst.delete(0, "end")
        self.e_dst.insert(0, str(dest))
        self._save_cfg()

        self.total, self.done = len(todo), 0
        self.started = time.time()
        self.last_dest = dest
        self.stop_event.clear()
        self.running = True
        self.btn_go.set_enabled(False)
        self.btn_stop.set_enabled(True)
        self.btn_open.set_enabled(False)
        self.bar.set(0, self.T["accent"])

        self._clear_log()
        self._say("info", literal="─" * 92)
        self._say("info", "c_src", v=src)
        self._say("info", "c_dst", v=dest)
        self._say("info", "c_fmt",
                  v=" + ".join(f.upper() for f in opts.formats)
                  + (f"   ·   MP3 {opts.quality}" if "mp3" in opts.formats else ""))
        self._say("info", "c_files", n=len(todo), j=self.g_jobs.get(),
                  extra=tr("c_verify_on") if opts.verify else "")
        if done:
            self._say("skip", "c_skipped", n=len(done))
        if dups:
            self._say("skip", "c_dupskip", n=len(dups))
        if opts.force:
            self._say("warn", "c_redo", n=len(opts.force))
        self._say("info", literal="─" * 92)

        if not todo:
            self.q.put(("done", (0, len(done) + len(dups), 0, 0, None), None))
            return

        self.bar.set_files([str(f.relative_to(src)) for f in todo])
        self._boot_sequence()
        threading.Thread(target=self._run,
                         args=(todo, src, opts, int(self.g_jobs.get()),
                               self.c_extras.get(), len(done) + len(dups)),
                         daemon=True).start()

    def _run(self, files, src, opts, jobs, extras, pre_skipped=0):
        tools = (self.ffmpeg, self.ffprobe)
        ok = err = 0
        skip = pre_skipped
        out_bytes = 0
        collected = []

        def task(f):
            if self.stop_event.is_set():
                return None
            self.q.put(("cur", str(f.relative_to(src)), None))
            return engine.convert_one(f, src, opts, tools)

        try:
            with futures.ThreadPoolExecutor(max_workers=jobs) as pool:
                pending = [pool.submit(task, f) for f in files]
                for fut in futures.as_completed(pending):
                    try:
                        outcome = fut.result()
                    except Exception as exc:
                        err += 1
                        self.q.put(("line", "err", (None, {}, f"  ✗  {exc}")))
                        self.q.put(("tick", None, None))
                        continue
                    if outcome is None:
                        self.q.put(("tick", None, None))
                        continue
                    collected.append(outcome)
                    rel = outcome.src.relative_to(src)
                    if outcome.status == "ok":
                        ok += 1
                        out_bytes += outcome.out_bytes
                        tail = "   [BIT-PERFECT]" if outcome.verified == "ok" else ""
                        self.q.put(("line", "ok", (None, {}, f"  ✓  {rel}{tail}")))
                    elif outcome.status == "skip":
                        skip += 1
                        self.q.put(("line", "skip", ("c_already", {"v": str(rel)}, None)))
                    else:
                        err += 1
                        self.q.put(("line", "err",
                                    (None, {}, f"  ✗  {rel}\n       {outcome.detail}")))
                    self.q.put(("tick", None, None))

            if extras and not self.stop_event.is_set():
                n = engine.copy_extras(src, opts)
                if n:
                    self.q.put(("line", "info", ("c_extras_n", {"n": n}, None)))
        except Exception as exc:
            self.q.put(("line", "err", (None, {}, f"  ✗  {exc}")))

        report = engine.write_report(
            collected, opts.dest / "_rapport_conversion.csv") if collected else None
        self.q.put(("done", (ok, skip, err, out_bytes, report), None))

    # -------------------------------------------------------------- boucle
    def _drain(self):
        try:
            while True:
                kind, a, b = self.q.get_nowait()
                if kind == "line":
                    key, kw, literal = b
                    self._say(a, key, literal=literal, **kw)
                elif kind == "tick":
                    self.done += 1
                    self._refresh()
                elif kind == "cur":
                    self._ticker(a)
                elif kind == "prog":
                    self.bar.set(a, b)
                elif kind == "ffmpeg":
                    self._ffmpeg_installed(*a)
                elif kind == "done":
                    self._finish(*a)
        except queue.Empty:
            pass
        if self.running:
            self.bar.pulse()
        self.root.after(90, self._drain)

    def _ffmpeg_installed(self, f, p):
        self.installing = False
        self.btn_install.set_enabled(True)
        self.btn_install.set_text(tr("b_install"))
        if f and p:
            self.ffmpeg, self.ffprobe = f, p
            self._refresh_tools_label()
            self._set_status("st_ready", "ok")
            self.bar.set(1.0, self.T["ok"])
            self._say("ok", "c_installed")
        else:
            self._set_status("st_dl_fail", "err")
            self.bar.set(0)
            self._say("err", "c_dlfail1")
            self._say("warn", "c_dlfail2")

    @staticmethod
    def _shorten(text: str, limit: int = 56) -> str:
        """Tronque par le milieu : le debut et le nom du fichier restent
        lisibles, la largeur de l'interface ne bouge jamais."""
        if len(text) <= limit:
            return text
        keep = (limit - 3) // 2
        return f"{text[:keep]}…{text[-(limit - 3 - keep):]}"

    def _ticker(self, name: str):
        """Affiche le fichier en cours de traitement. Volontairement rapide :
        c'est un defilement, la console garde la trace exacte."""
        if self.running:
            self._set_status(role="text", literal=f"» {self._shorten(name)}")

    def _boot_sequence(self, step: int = 0):
        """Balayage d'initiation : les glyphes s'allument de gauche a droite
        avant le premier encodage."""
        n = self.bar.n
        if step == 0:
            self._set_status("st_init", "accent")
        if step <= n + 2:
            self.bar.sweep = step
            self.bar.draw()
            self.root.after(16, lambda: self._boot_sequence(step + max(1, n // 20)))
        else:
            self.bar.sweep = -1
            self.bar.draw()

    def _refresh(self):
        ratio = self.done / self.total if self.total else 0
        self.bar.set(ratio)
        elapsed = time.time() - self.started
        eta = ""
        if 0 < ratio < 1 and self.done >= 3:
            eta = f"   ·   {engine.hms(elapsed / ratio - elapsed)}"
        self.lbl_counter.configure(
            text=f"{self.done} / {self.total}   ·   {ratio * 100:5.1f} %{eta}")

    def _finish(self, ok, skip, err, out_bytes, report=None):
        self.running = False
        self.btn_go.set_enabled(True)
        self.btn_stop.set_enabled(False)
        self.btn_open.set_enabled(True)
        elapsed = time.time() - self.started
        self._say("info", literal="─" * 92)
        if self.stop_event.is_set():
            self.bar.set(self.done / max(1, self.total), self.T["warn"])
            self._say("warn", "c_stopped", ok=ok, t=engine.hms(elapsed))
            self._set_status("st_stopped", "warn")
        else:
            self.bar.set(1.0, self.T["ok"] if not err else self.T["err"])
            self._say("ok" if not err else "warn", "c_done",
                      t=engine.hms(elapsed), ok=ok, sk=skip, er=err)
            if out_bytes:
                self._say("dim", "c_volume", _bytes=out_bytes)
            if report:
                self._say("dim", "c_report", v=report)
            self._say("info", literal="")
            self._say("ok", "c_thanks")
            self._say("dim", "c_thanks2", a=AUTHOR, c=CONTACT)
            if err:
                self._set_status("st_done_err", "err", n=err)
            else:
                self._set_status("st_done", "ok")
        self._say("info", literal="─" * 92)

    def _stop(self):
        if self.running:
            self.stop_event.set()
            self.btn_stop.set_enabled(False)
            self._set_status("st_stopping", "warn")

    def _on_close(self):
        if self.running and not messagebox.askyesno(APP_NAME, tr("d_quit")):
            return
        self.stop_event.set()
        self._save_cfg()
        self.root.destroy()


# ==========================================================================

def hide_console():
    """Masque la fenetre console du lanceur : l'application est graphique."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def main():
    global SCALE
    hide_console()
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    try:
        dpi = root.winfo_fpixels("1i")
        SCALE = max(1.0, min(2.0, dpi / 96.0))
        root.tk.call("tk", "scaling", dpi / 72.0)
    except tk.TclError:
        SCALE = 1.0

    load_fonts(root)

    ico = res("assets", "logo256.png")
    if ico.exists():
        try:
            root.iconphoto(True, tk.PhotoImage(file=str(ico)))
        except tk.TclError:
            pass

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
