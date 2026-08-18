# Hi-Dump - Mentions légales et propriété intellectuelle

## 1. Titularité des droits

**© 2026 HiGRID - Tous droits réservés.**

Le logiciel **Hi-Dump**, son code source, son architecture de conversion, son
interface, ses habillages (« skins ») et sa documentation sont la propriété
exclusive de **HiGRID**.

Sont également la propriété exclusive de HiGRID, à titre de marque et
d'éléments d'identité visuelle :

- la dénomination **HiGRID** et la dénomination **Hi-Dump** ;
- le **logo** HiGRID (badge « Hi / GRiD » et enceinte) ;
- l'alphabet de glyphes de la barre de progression et son mode de génération ;
- la **mascotte** (personnage au casque vinyle et à la pioche) et le lockup
  associé ;
- la **charte chromatique** `#0B0B0B` · `#EFEBE3` · `#E11D17` · `#8E0F0B` ·
  `#807A6F` telle qu'appliquée dans l'interface ;
- le système d'habillage - **HIGRID**, **CYBERPUNK**, **OFFGRID** - et la
  composition de l'écran (« HUD »).

## 2. Utilisation

Le logiciel est fourni pour l'usage propre de son titulaire et des personnes
qu'il autorise expressément.

Sont interdits, sans autorisation écrite préalable de HiGRID :

- la reproduction, la diffusion, la mise à disposition ou la revente, totale
  ou partielle, du logiciel ;
- la modification, la décompilation ou la rétro-ingénierie, sauf dans les
  limites impératives prévues par la loi ;
- la réutilisation du nom, du logo, de la mascotte ou de la charte graphique
  dans un autre produit, service, support ou communication ;
- le retrait ou l'altération des mentions de propriété figurant dans le code,
  dans l'interface ou dans les métadonnées de l'exécutable.

## 3. Absence de garantie

Le logiciel est fourni « en l'état ». HiGRID ne garantit pas qu'il soit exempt
d'erreurs et ne pourra être tenu responsable d'une perte de données, d'un
dommage direct ou indirect résultant de son utilisation. Il appartient à
l'utilisateur de conserver ses fichiers sources originaux - Hi-Dump ne modifie
ni ne supprime jamais les fichiers FLAC d'entrée.

## 4. Composants tiers

Hi-Dump s'appuie sur des composants tiers, utilisés **sans modification**, qui
demeurent soumis à leurs licences propres. Ces licences ne s'étendent pas au
code, à la marque ni à l'identité visuelle de HiGRID.

| Composant | Rôle | Licence |
|---|---|---|
| **FFmpeg / FFprobe** | décodage FLAC, écriture WAV, encodage MP3 | LGPL v2.1+ / GPL v2+ selon le build |
| **LAME** | encodeur MP3 (via `libmp3lame`) | LGPL v2 |
| **SoXR** | rééchantillonnage haute précision | LGPL v2.1 |
| **Python** | environnement d'exécution | PSF License |
| **Tcl/Tk** | bibliothèque d'interface | BSD |
| **PyInstaller** | mise en exécutable | GPL v2 avec exception de liaison |
| **Anton** | police d'affichage | SIL Open Font License 1.1 |
| **Archivo** | police de texte courant | SIL Open Font License 1.1 |
| **Space Mono** | police technique / étiquettes | SIL Open Font License 1.1 |

FFmpeg n'est pas distribué avec l'exécutable : il est téléchargé par
l'application depuis sa source officielle, à la demande de l'utilisateur, et
installé dans son profil (`%LOCALAPPDATA%\Hi-Dump\bin`). Les textes complets des
licences OFL et LGPL sont disponibles auprès de leurs éditeurs respectifs
(scripts.sil.org/OFL, www.gnu.org/licenses).

Les polices Anton, Archivo et Space Mono sont embarquées dans l'exécutable
conformément à l'OFL, qui autorise l'incorporation d'une police dans un
document ou un logiciel, sans que cela n'affecte la licence de ce dernier.

## 5. Contact

Pour toute demande d'autorisation, de licence ou de partenariat :
**HiGRID** - contact@higrid.eu   ·   334fredo

---

*Ces mentions figurent également dans l'en-tête du code source, dans la fenêtre
« À PROPOS » de l'application, en pied d'interface et dans les propriétés de
`Hi-Dump.exe` (onglet Détails, clic droit → Propriétés).*
