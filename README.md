# Hi-Dump

Convertisseur FLAC vers **WAV bit-perfect** et **MP3 LAME**, par
[HiGRID](https://higrid.eu). Gratuit, sans publicité, sans collecte de données.

- **Windows** et **macOS** : applications autonomes.
- Une version navigateur existe sur [higrid.eu/hi-dump.html](https://higrid.eu/hi-dump.html)
  et convertit également sur votre machine, sans envoi de fichiers. Son code
  n'est pas publié ici.

Ce dépôt existe pour une raison simple : **vous permettre de lire ce que vous
exécutez**. Le code est ici en clair, sans obscurcissement.

---

## Pourquoi certains antivirus signalent l'exécutable Windows

Trois ou quatre moteurs sur les soixante-dix de VirusTotal signalent
`Hi-Dump.exe`. C'est un faux positif heuristique classique, et voici la
mécanique exacte.

L'application est écrite en Python et empaquetée avec **PyInstaller**, l'outil
standard du domaine. Le programme obtenu embarque un petit lanceur qui déplie
l'application en mémoire au démarrage. Ce comportement, banal, ressemble de
loin à celui d'un logiciel qui se déballe pour se dissimuler. Certains moteurs
le signalent par précaution.

Les étiquettes affichées disent d'ailleurs leur propre incertitude :

| Moteur | Étiquette | Ce que ça signifie |
|---|---|---|
| Microsoft | `Trojan:Win32/Wacatac.B!ml` | le suffixe `!ml` = verdict d'un modèle statistique, pas d'une signature |
| Elastic | `Malicious (moderate confidence)` | « confiance modérée », de leur propre aveu |
| Bkav Pro | `W32.Malware.FE2D3496` | signature générique, sans famille identifiée |
| SecureAge | `Malicious` | verdict binaire, sans détail |

**Ce qui manque :** un certificat de signature de code Windows, facturé 300 à
600 € par an avec vérification d'identité d'entreprise. Pour un utilitaire
distribué gratuitement, la dépense n'est pas tenable aujourd'hui. Le jour où
elle le sera, l'application sera signée et ces alertes disparaîtront.

**Ce que vous pouvez faire, tout de suite :**

1. Lire le code de ce dépôt. Tout est là, en Python lisible.
2. Recompiler vous-même l'exécutable avec les commandes ci-dessous et comparer.
3. Consulter la construction automatique dans l'onglet *Actions* : GitHub
   compile l'application sur ses propres machines, publiquement.
4. Ou n'installer rien du tout et utiliser la version navigateur.

## Ce que fait l'application, exactement

- Lit les fichiers `.flac` du dossier que vous désignez.
- Écrit des `.wav` et des `.mp3` dans le dossier de destination que vous
  choisissez, en recréant l'arborescence.
- Télécharge `ffmpeg` **si vous cliquez sur le bouton prévu**, depuis GitHub ou
  gyan.dev, et le range dans votre profil utilisateur.
- Enregistre vos préférences (skin, langue, derniers dossiers) dans un fichier
  `config.json` de votre profil.

Elle n'ouvre aucune autre connexion réseau, ne collecte rien, ne s'installe pas
dans le système, n'écrit pas dans le registre Windows et ne se lance pas au
démarrage. Les fichiers FLAC d'origine ne sont jamais modifiés ni supprimés.

---

## Construire soi-même

### Windows

```bat
py -3.12 -m pip install pyinstaller
py -3.12 -m PyInstaller --noconfirm --onedir --console --name "Hi-Dump" ^
  --icon build\icone.ico --version-file build\version_info.txt ^
  --hidden-import hidump_engine --paths src ^
  --add-data "src\assets;assets" src\Hi-Dump.pyw
```

Le résultat se trouve dans `dist\Hi-Dump\`. La variante `--onefile` produit un
exécutable unique, plus pratique mais davantage sujet aux faux positifs.

### macOS

L'application macOS est un paquet `.app` classique dont le lanceur est le
script `build/mac-launcher.sh` : il choisit l'interpréteur Python embarqué
selon l'architecture (Apple Silicon ou Intel) et lance `src/Hi-Dump.pyw`.
`build/Info.plist` décrit le paquet. Voir `build/README-build.md`.

---

## Licence

Code **source visible**, tous droits réservés. Vous pouvez lire, auditer et
recompiler pour votre usage propre. La redistribution, la modification publiée
et la réutilisation de la marque, du logo ou de l'identité visuelle HiGRID
demandent une autorisation écrite. Voir `MENTIONS-LEGALES.md`.

Composants tiers conservés sans modification, sous leurs licences respectives :
FFmpeg et libmp3lame (LGPL/GPL), polices Anton, Archivo et Space Mono (SIL OFL
1.1), Python et Tcl/Tk (PSF, BSD).

## Contact

contact@higrid.eu · 334fredo
