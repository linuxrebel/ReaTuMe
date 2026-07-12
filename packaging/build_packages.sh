#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build_packages.sh — Build RPM, DEB, and an installable tarball for ReaTuMe.
# Mirrors the DocuBrowse packaging pattern (native tools, no fpm).
#
# Usage (from repo root):
#   ./packaging/build_packages.sh [RELEASE]
#
#   RELEASE  Build number (default: 1). Increment for a rebuild of the same
#            version. Outputs to dist/.
#
# Deps declared in the packages: nodejs, espeak-ng, python3-pyside6, alsa-utils.
# NOT declared (install separately): piper-tts (pip), Playwright Firefox.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

NAME="reatume"
RELEASE="${1:-1}"
SPEC="packaging/reatume.spec"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="$(node -p "require('./package.json').version")"

if [[ ! -f "$SPEC" ]]; then
    echo "ERROR: $SPEC not found. Run from the repo root." >&2
    exit 1
fi
if [[ ! -d node_modules ]]; then
    echo "ERROR: node_modules missing. Run 'npm install' first." >&2
    exit 1
fi

echo "Building $NAME $VERSION-$RELEASE"

# ── Stage the application files ──────────────────────────────────────────────
APP_ITEMS=(bin src node_modules reatume reatume_ui.py assets package.json README.md)

STAGING="$(mktemp -d)"
STAGE_DIR="$STAGING/$NAME-$VERSION"
trap 'rm -rf "$STAGING"' EXIT
mkdir -p "$STAGE_DIR"
for item in "${APP_ITEMS[@]}"; do
    if [[ -e "$item" ]]; then
        cp -a "$item" "$STAGE_DIR/"
    else
        echo "WARNING: $item not found, skipping."
    fi
done

mkdir -p "$REPO_ROOT/dist"

# ── Source tarball (for rpmbuild %setup) ─────────────────────────────────────
TARBALL="$NAME-$VERSION.tar.gz"
(cd "$STAGING" && tar czf "$REPO_ROOT/$TARBALL" "$NAME-$VERSION")

# ── RPM ──────────────────────────────────────────────────────────────────────
if command -v rpmbuild >/dev/null 2>&1; then
    echo "==> Building RPM ..."
    RPM_TOPDIR="$(mktemp -d)"
    for d in BUILD RPMS SOURCES SPECS SRPMS; do mkdir -p "$RPM_TOPDIR/$d"; done
    cp "$TARBALL" "$RPM_TOPDIR/SOURCES/"
    cp "$SPEC" "$RPM_TOPDIR/SPECS/"
    rpmbuild -bb \
        --define "_topdir $RPM_TOPDIR" \
        --define "version $VERSION" \
        --define "release $RELEASE" \
        "$RPM_TOPDIR/SPECS/$(basename "$SPEC")"
    find "$RPM_TOPDIR/RPMS" -name '*.rpm' -exec cp {} "$REPO_ROOT/dist/" \;
    rm -rf "$RPM_TOPDIR"
else
    echo "SKIPPED RPM: rpmbuild not found (dnf install rpm-build)."
fi

# ── DEB ──────────────────────────────────────────────────────────────────────
if command -v dpkg-deb >/dev/null 2>&1; then
    echo "==> Building DEB ..."
    DEB_ROOT="$(mktemp -d)"
    DEB_PKG="$DEB_ROOT/$NAME-$VERSION"

    mkdir -p "$DEB_PKG/opt/reatume"
    cp -a "$STAGE_DIR"/* "$DEB_PKG/opt/reatume/"
    chmod 755 "$DEB_PKG/opt/reatume/reatume" "$DEB_PKG/opt/reatume/bin/reatume.js"

    mkdir -p "$DEB_PKG/usr/bin"
    cat > "$DEB_PKG/usr/bin/reatume" <<'WRAPPER'
#!/usr/bin/env bash
exec /opt/reatume/reatume "$@"
WRAPPER
    chmod 755 "$DEB_PKG/usr/bin/reatume"

    install -Dm644 "$STAGE_DIR/assets/reatume.svg" \
        "$DEB_PKG/usr/share/icons/hicolor/scalable/apps/reatume.svg"

    mkdir -p "$DEB_PKG/usr/share/applications"
    cat > "$DEB_PKG/usr/share/applications/reatume.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=ReaTuMe
GenericName=Web Page Reader
Comment=Read a web page aloud
Exec=/usr/bin/reatume
Icon=reatume
Terminal=false
Categories=Network;
Keywords=tts;reader;speech;article;
StartupWMClass=reatume
DESKTOP

    mkdir -p "$DEB_PKG/DEBIAN"
    cat > "$DEB_PKG/DEBIAN/control" <<EOF
Package: reatume
Version: ${VERSION}-${RELEASE}
Section: sound
Priority: optional
Architecture: all
Depends: nodejs, espeak-ng, python3-pyside6, alsa-utils
Maintainer: James Sparenberg <james@sparenbergs.us>
Description: Read a web page aloud (espeak or Piper neural TTS)
 ReaTuMe extracts the readable article from a URL and reads it aloud.
 Piper (pip: piper-tts) and the Playwright Firefox browser are not
 packaged dependencies; install them separately (see README).
EOF

    cat > "$DEB_PKG/DEBIAN/postinst" <<'SCRIPT'
#!/bin/bash
set -e
gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
echo "ReaTuMe installed. For the Piper voice: pip install --user piper-tts"
echo "and: cd /opt/reatume && npx playwright install firefox"
SCRIPT
    chmod 755 "$DEB_PKG/DEBIAN/postinst"

    cat > "$DEB_PKG/DEBIAN/postrm" <<'SCRIPT'
#!/bin/bash
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
SCRIPT
    chmod 755 "$DEB_PKG/DEBIAN/postrm"

    dpkg-deb --build "$DEB_PKG" "$REPO_ROOT/dist/${NAME}_${VERSION}-${RELEASE}_all.deb" >/dev/null
    rm -rf "$DEB_ROOT"
else
    echo "SKIPPED DEB: dpkg-deb not found (dnf install dpkg)."
fi

# ── Installable tarball (app + install/uninstall scripts) ────────────────────
echo "==> Building installable tarball ..."
TGZ_NAME="$NAME-$VERSION-$RELEASE"
TGZ_DIR="$(mktemp -d)"
TGZ_STAGE="$TGZ_DIR/$TGZ_NAME"
mkdir -p "$TGZ_STAGE"
cp -a "$STAGE_DIR"/* "$TGZ_STAGE/"
install -m 755 install.sh   "$TGZ_STAGE/"
install -m 755 uninstall.sh "$TGZ_STAGE/"
(cd "$TGZ_DIR" && tar czf "$REPO_ROOT/dist/${TGZ_NAME}.tar.gz" "$TGZ_NAME")
rm -rf "$TGZ_DIR"

rm -f "$REPO_ROOT/$TARBALL"

echo ""
echo "Done. Packages in dist/:"
ls -1 "$REPO_ROOT/dist/" 2>/dev/null
