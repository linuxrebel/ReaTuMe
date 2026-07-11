#!/usr/bin/env bash
#
# install.sh — install ReaTuMe system-wide.
#   app  -> /opt/reatume
#   cmd  -> /usr/local/bin/reatume (symlink)
# Re-running overwrites an existing install (use it to update).

set -euo pipefail

DEST="/opt/reatume"
BIN="/usr/local/bin/reatume"
SRC="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1) must be root to write /opt and /usr/local/bin.
if [ "$(id -u)" -ne 0 ]; then
  echo "This installer writes to /opt and /usr/local/bin and must run as root." >&2
  echo "Run it with: sudo ./install.sh" >&2
  exit 1
fi

# Files needed at runtime.
ITEMS=(bin src node_modules reatume reatume_ui.py package.json README.md)
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

echo "Done. Run 'reatume' for the GUI, or 'reatume <url>' for the CLI."
