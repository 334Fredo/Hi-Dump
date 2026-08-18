# Construire Hi-Dump

## Windows

Prérequis : Python 3.12 (python.org) et `pip install pyinstaller`.

```bat
py -3.12 -m PyInstaller --noconfirm --onedir --console --name "Hi-Dump" ^
  --icon build\icone.ico --version-file build\version_info.txt ^
  --hidden-import hidump_engine --paths src ^
  --add-data "src\assets;assets" src\Hi-Dump.pyw
```

`--onedir` produit un dossier `dist\Hi-Dump\` contenant `Hi-Dump.exe` et
`_internal\`. C'est la forme distribuée : elle démarre plus vite et déclenche
moins de faux positifs antivirus que `--onefile`.

L'application masque sa console au démarrage (`hide_console()` dans le code) :
le bootloader console est utilisé parce qu'il est le seul à fonctionner de
façon fiable dans tous les environnements de test, y compris sous Wine.

## macOS

Le paquet `.app` embarque un interpréteur Python autonome, ce qui évite toute
installation côté utilisateur.

1. Télécharger les deux runtimes CPython autonomes (arm64 et x86_64) depuis
   [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
   (`cpython-3.12.x+YYYYMMDD-<arch>-apple-darwin-install_only.tar.gz`).
2. Construire l'arborescence :

```
Hi-Dump.app/Contents/
  Info.plist                    <- build/Info.plist
  MacOS/Hi-Dump                 <- build/mac-launcher.sh (chmod +x)
  Resources/Hi-Dump.icns        <- build/HiDump.icns
  Resources/app/                <- contenu de src/ (Hi-Dump.pyw renommé Hi-Dump.py)
  Resources/runtime-arm64/      <- runtime décompressé (dossier python/ renommé)
  Resources/runtime-x86_64/
```

3. Alléger les runtimes : supprimer `lib/python3.12/{test,idlelib,ensurepip,
   pydoc_data,turtledemo}`, `include/`, `share/`, les `__pycache__`.

Le lanceur retire l'attribut de quarantaine au démarrage et choisit le runtime
selon `uname -m`.
