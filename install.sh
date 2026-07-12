#!/usr/bin/env bash
#
# install.sh — install ReaTuMe system-wide.
#   app  -> /opt/reatume
#   cmd  -> /usr/local/bin/reatume (symlink)
# Re-running overwrites an existing install (use it to update).

set -euo pipefail

DEST="/opt/reatume"
BIN="/usr/local/bin/reatume"
ICON="/usr/share/icons/hicolor/scalable/apps/reatume.svg"
DESKTOP="/usr/share/applications/reatume.desktop"
SRC="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1) must be root to write /opt and /usr/local/bin.
if [ "$(id -u)" -ne 0 ]; then
  echo "This installer writes to /opt and /usr/local/bin and must run as root." >&2
  echo "Run it with: sudo ./install.sh" >&2
  exit 1
fi

# Files needed at runtime.
ITEMS=(bin src node_modules reatume reatume_ui.py package.json README.md assets)
for item in "${ITEMS[@]}"; do
  if [ ! -e "$SRC/$item" ]; then
    echo "Missing '$item' in $SRC. Run 'npm install' first, then re-run installer." >&2
    exit 1
  fi
done

# Light dependency check (warn only — install still proceeds).
for dep in node espeak-ng python3; do
  command -v "$dep" >/dev/null 2>&1 || echo "Warning: '$dep' not found on PATH; ReaTuMe needs it to run." >&2
done

# 4) overwrite any previous install for a clean update.
echo "Installing to $DEST ..."
rm -rf "$DEST"
mkdir -p "$DEST"
for item in "${ITEMS[@]}"; do
  cp -a "$SRC/$item" "$DEST/"
done

chmod +x "$DEST/reatume" "$DEST/bin/reatume.js"

# 2) command in /usr/local/bin (symlink, -f to overwrite on update).
ln -sf "$DEST/reatume" "$BIN"

# App icon (hicolor scalable theme) + desktop entry so it shows in menus.
install -Dm644 "$SRC/assets/reatume.svg" "$ICON"
mkdir -p "$(dirname "$DESKTOP")"
cat > "$DESKTOP" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=ReaTuMe
GenericName=Web Page Reader
Comment=Read a web page aloud
Exec=$BIN
Icon=reatume
Terminal=false
Categories=Network;
Keywords=tts;reader;speech;article;
StartupWMClass=reatume
DESKTOP_EOF
chmod 644 "$DESKTOP"

# Refresh desktop/icon caches (best-effort; harmless if the tools are absent).
gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

echo "Done. Run 'reatume' for the GUI, or 'reatume <url>' for the CLI."
