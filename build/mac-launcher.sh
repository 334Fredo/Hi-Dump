#!/bin/bash
# ---------------------------------------------------------------------------
#  Hi-Dump - lanceur macOS
#  (c) 2026 HiGRID - Tous droits reserves - contact@higrid.eu
#
#  L'application embarque son propre interpreteur : rien a installer.
#  Le lanceur choisit la version Apple Silicon ou Intel selon la machine.
# ---------------------------------------------------------------------------

HERE="$(cd "$(dirname "$0")" && pwd)"
RES="$HERE/../Resources"
BUNDLE="$(cd "$HERE/../.." && pwd)"

# etiquette posee par le navigateur sur tout fichier telecharge
xattr -dr com.apple.quarantine "$BUNDLE" 2>/dev/null

case "$(uname -m)" in
  arm64)  RUNTIME="$RES/runtime-arm64" ;;
  *)      RUNTIME="$RES/runtime-x86_64" ;;
esac

PY="$RUNTIME/bin/python3.12"
[ -x "$PY" ] || PY="$RES/runtime-x86_64/bin/python3.12"

if [ ! -x "$PY" ]; then
  osascript -e 'display alert "Hi-Dump" message "Le moteur embarque est introuvable. Retelechargez l application." as critical' >/dev/null 2>&1
  exit 1
fi

exec "$PY" "$RES/app/Hi-Dump.py" "$@"
