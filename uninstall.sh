#!/usr/bin/env bash
#
# uninstall.sh — remove ReaTuMe: app, command, and per-user config.

set -euo pipefail

DEST="/opt/reatume"
BIN="/usr/local/bin/reatume"
ICON="/usr/share/icons/hicolor/scalable/apps/reatume.svg"
DESKTOP="/usr/share/applications/reatume.desktop"

# Must be root to remove from /opt and /usr/local/bin.
if [ "$(id -u)" -ne 0 ]; then
  echo "This uninstaller must run as root." >&2
  echo "Run it with: sudo ./uninstall.sh" >&2
  exit 1
fi

echo "Removing $BIN"
rm -f "$BIN"

echo "Removing $DEST"
rm -rf "$DEST"

echo "Removing icon + desktop entry"
rm -f "$ICON" "$DESKTOP"
gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

# Config + voices live in the invoking user's home, not root's. Resolve via SUDO_USER.
if [ -n "${SUDO_USER:-}" ]; then
  USER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
else
  USER_HOME="$HOME"
fi

for d in "$USER_HOME/.config/reatume" "$USER_HOME/.local/share/reatume"; do
  if [ -d "$d" ]; then
    echo "Removing $d"
    rm -rf "$d"
  fi
done

echo "Done. ReaTuMe removed."
