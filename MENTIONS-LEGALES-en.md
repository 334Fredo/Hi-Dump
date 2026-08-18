# Hi-Dump - Legal Notices and Intellectual Property

## 1. Ownership of Rights

**© 2026 HiGRID - All rights reserved.**

The **Hi-Dump** software, its source code, conversion architecture, interface, visual themes ("skins"), and documentation are the exclusive property of **HiGRID**.

The following are also the exclusive property of HiGRID, as trademarks and visual identity elements:

- the names **HiGRID** and **Hi-Dump**;
- the HiGRID **logo** (the "Hi / GRiD" badge and speaker);
- the progress bar glyph alphabet and its generation method;
- the **mascot** (character wearing a vinyl helmet and carrying a pickaxe) and its associated lockup;
- the **color scheme** `#0B0B0B` · `#EFEBE3` · `#E11D17` · `#8E0F0B` · `#807A6F` as applied in the interface;
- the visual theme system - **HIGRID**, **CYBERPUNK**, **OFFGRID** - and the screen composition ("HUD").

## 2. Use

The software is provided for the personal use of its owner and persons expressly authorized by the owner.

The following are prohibited without prior written authorization from HiGRID:

- reproduction, distribution, making available, or resale, in whole or in part, of the software;
- modification, decompilation, or reverse engineering, except to the extent mandatorily permitted by law;
- reuse of the name, logo, mascot, or visual identity in another product, service, medium, or communication;
- removal or alteration of ownership notices appearing in the code, interface, or executable metadata.

## 3. Disclaimer of Warranty

The software is provided "as is". HiGRID does not warrant that it is free of errors and shall not be held liable for any data loss or any direct or indirect damage resulting from its use. Users are responsible for keeping their original source files - Hi-Dump never modifies or deletes input FLAC files.

## 4. Third-Party Components

Hi-Dump relies on third-party components, used **without modification**, which remain subject to their respective licenses. These licenses do not extend to HiGRID's code, trademarks, or visual identity.

| Component | Role | License |
|---|---|---|
| **FFmpeg / FFprobe** | FLAC decoding, WAV writing, MP3 encoding | LGPL v2.1+ / GPL v2+ depending on the build |
| **LAME** | MP3 encoder (via `libmp3lame`) | LGPL v2 |
| **SoXR** | High-precision resampling | LGPL v2.1 |
| **Python** | Runtime environment | PSF License |
| **Tcl/Tk** | Interface library | BSD |
| **PyInstaller** | Executable packaging | GPL v2 with linking exception |
| **Anton** | Display font | SIL Open Font License 1.1 |
| **Archivo** | Body text font | SIL Open Font License 1.1 |
| **Space Mono** | Technical font / labels | SIL Open Font License 1.1 |

FFmpeg is not distributed with the executable: it is downloaded by the application from its official source, at the user's request, and installed in their profile (`%LOCALAPPDATA%\Hi-Dump\bin`). The full OFL and LGPL license texts are available from their respective publishers (scripts.sil.org/OFL, www.gnu.org/licenses).

The Anton, Archivo, and Space Mono fonts are embedded in the executable in accordance with the OFL, which permits embedding a font in a document or software without affecting the license of that document or software.

## 5. Contact

For any request regarding authorization, licensing, or partnership:
**HiGRID** - contact@higrid.eu   ·   334fredo

---

*These notices also appear in the source code header, in the application's "ABOUT" window, in the interface footer, and in the properties of `Hi-Dump.exe` (Details tab, right-click → Properties).*
