#!/usr/bin/env bash
#
# uninstall.sh — remove ReaTuMe: app, command, and per-user config.

set -euo pipefail

DEST="/opt/reatume"
BIN="/usr/local/bin/reatume"

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

# Config lives in the invoking user's home, not root's. Resolve via SUDO_USER.
if [ -n "${SUDO_USER:-}" ]; then
  USER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
else
  USER_HOME="$HOME"
fi
CONFIG_DIR="$USER_HOME/.local/reatume"

if [ -d "$CONFIG_DIR" ]; then
  echo "Removing config $CONFIG_DIR"
  rm -rf "$CONFIG_DIR"
fi

echo "Done. ReaTuMe removed."
