Name:           reatume
Version:        %{version}
Release:        %{release}
Summary:        Read a web page aloud (espeak or Piper neural TTS)
License:        MIT
URL:            https://github.com/linuxrebel/ReaTuMe
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       nodejs
Requires:       espeak-ng
Requires:       python3-pyside6
Requires:       alsa-utils

%description
ReaTuMe navigates to a URL, extracts the readable article with Mozilla's
Readability (headless Firefox via Playwright), and reads it aloud with either
espeak-ng or Piper neural TTS.

Piper (pip: piper-tts) and the Playwright Firefox browser are NOT packaged as
dependencies — install them separately (see README). espeak works out of the box.

%prep
%setup -q

%install
rm -rf %{buildroot}

# Application tree under /opt/reatume
install -d -m 755 %{buildroot}/opt/reatume
cp -a bin src node_modules reatume reatume_ui.py assets package.json README.md \
    %{buildroot}/opt/reatume/
chmod 755 %{buildroot}/opt/reatume/reatume %{buildroot}/opt/reatume/bin/reatume.js

# Launcher wrapper in /usr/bin
install -d -m 755 %{buildroot}/usr/bin
cat > %{buildroot}/usr/bin/reatume <<'WRAPPER'
#!/usr/bin/env bash
exec /opt/reatume/reatume "$@"
WRAPPER
chmod 755 %{buildroot}/usr/bin/reatume

# App icon (hicolor scalable theme)
install -Dm644 assets/reatume.svg \
    %{buildroot}/usr/share/icons/hicolor/scalable/apps/reatume.svg

# Desktop entry
install -d -m 755 %{buildroot}/usr/share/applications
cat > %{buildroot}/usr/share/applications/reatume.desktop <<'DESKTOP'
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

%files
/opt/reatume
/usr/bin/reatume
/usr/share/icons/hicolor/scalable/apps/reatume.svg
/usr/share/applications/reatume.desktop

%post
gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
echo ""
echo "ReaTuMe installed. espeak works now."
echo "For the Piper neural voice, install piper-tts and a Firefox browser:"
echo "  pip install --user piper-tts"
echo "  cd /opt/reatume && npx playwright install firefox"
echo "Then launch: reatume"

%postun
if [ "$1" = "0" ]; then
    gtk-update-icon-cache -q -t /usr/share/icons/hicolor 2>/dev/null || true
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

%changelog
* Sat Jul 11 2026 James Sparenberg <james@sparenbergs.us> - 0.1.0-1
- Initial package: espeak + Piper TTS, GUI, CLI.
