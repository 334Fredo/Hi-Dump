# Hi-Dump

FLAC to **bit-perfect WAV** and **LAME MP3** converter, by
[HiGRID](https://higrid.eu). Free, ad-free, with no data collection.

- **Windows** and **macOS**: standalone applications.
- A browser version is available at [higrid.eu/hi-dump.html](https://higrid.eu/hi-dump.html)
  and also performs conversion on your machine, without uploading files. Its source
  code is not published here.

This repository exists for one simple reason: **to let you read what you
run**. The code is here in plain form, without obfuscation.

---

## Why some antivirus programs flag the Windows executable

Three or four out of the seventy VirusTotal engines flag
`Hi-Dump.exe`. This is a classic heuristic false positive, and here is the exact mechanism.

The application is written in Python and packaged with **PyInstaller**, the
standard tool in this field. The resulting program contains a small launcher
that unpacks the application into memory at startup. This ordinary behavior can
look, from a distance, like software unpacking itself to hide. Some engines flag
it as a precaution.

The displayed labels actually indicate their own uncertainty:

| Engine | Label | What it means |
|---|---|---|
| Microsoft | `Trojan:Win32/Wacatac.B!ml` | the `!ml` suffix = verdict from a statistical model, not a signature |
| Elastic | `Malicious (moderate confidence)` | "moderate confidence", by their own admission |
| Bkav Pro | `W32.Malware.FE2D3496` | generic signature, with no identified family |
| SecureAge | `Malicious` | binary verdict, without details |

**What's missing:** a Windows code-signing certificate, costing €300 to
€600 per year with business identity verification. For a utility distributed
free of charge, the expense is not sustainable today. When it becomes
sustainable, the application will be signed and these alerts will disappear.

**What you can do right now:**

1. Read the code in this repository. Everything is here in readable Python.
2. Rebuild the executable yourself using the commands below and compare it.
3. Check the automated build in the *Actions* tab: GitHub builds the application
   on its own machines, publicly.
4. Or install nothing at all and use the browser version.

## What the application does, exactly

- Reads `.flac` files from the folder you designate.
- Writes `.wav` and `.mp3` files to the destination folder you choose, recreating
  the directory structure.
- Downloads `ffmpeg` **if you click the designated button**, from GitHub or
  gyan.dev, and stores it in your user profile.
- Saves your preferences (skin, language, recent folders) in a
  `config.json` file in your profile.

It opens no other network connections, collects nothing, does not install itself
in the system, does not write to the Windows registry, and does not launch at
startup. Original FLAC files are never modified or deleted.

---

## Build it yourself

### Windows

```bat
py -3.12 -m pip install pyinstaller
py -3.12 -m PyInstaller --noconfirm --onedir --console --name "Hi-Dump" ^
  --icon build\icone.ico --version-file buildersion_info.txt ^
  --hidden-import hidump_engine --paths src ^
  --add-data "srcssets;assets" src\Hi-Dump.pyw
```

The result is located in `dist\Hi-Dump\`. The `--onefile` variant produces a
single executable, which is more convenient but more prone to false positives.

### macOS

The macOS application is a standard `.app` bundle whose launcher is the
`build/mac-launcher.sh` script: it selects the bundled Python interpreter
according to the architecture (Apple Silicon or Intel) and launches
`src/Hi-Dump.pyw`.
`build/Info.plist` describes the bundle. See `build/README-build.md`.

---

## License

**Visible source code**, all rights reserved. You may read, audit, and
recompile it for your own use. Redistribution, published modification, and
reuse of the HiGRID brand, logo, or visual identity require written
authorization. See `MENTIONS-LEGALES.md`.

Third-party components retained without modification, under their respective licenses:
FFmpeg and libmp3lame (LGPL/GPL), Anton, Archivo, and Space Mono fonts (SIL OFL
1.1), Python and Tcl/Tk (PSF, BSD).

## Contact

contact@higrid.eu · 334fredo
