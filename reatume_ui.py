#!/usr/bin/env python3
"""ReaTuMe GUI — read a web article aloud (PySide6 front-end over the node CLI).

Thin native window. The Node CLI (bin/reatume.js) does fetch + extract + speak;
this window just collects a URL and espeak-ng settings and launches it. Voice
samples are played directly through espeak-ng.

Portable: to move to PyQt6, change the three PySide6 imports to PyQt6 (identical
API). Config location is chosen per-OS via QStandardPaths.
"""
import json
import subprocess
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QStandardPaths, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QLineEdit, QPushButton, QComboBox, QSlider,
    QLabel, QHBoxLayout, QVBoxLayout, QFormLayout,
)

SCRIPT_DIR = Path(__file__).resolve().parent
CLI = SCRIPT_DIR / "bin" / "reatume.js"
SAMPLE_TEXT = "The quick brown fox reads this article aloud."

# espeak defaults, written to config.json on first run.
DEFAULTS = {"engine": "espeak", "voice": "en-us", "piperModel": "", "speed": 175, "wordGap": 0}


def config_path() -> Path:
    """Per-OS config file. Linux: ~/.local/reatume/config.json (as specified);
    Windows/macOS: the platform AppConfig dir via QStandardPaths."""
    home = Path.home()
    linux_path = home / ".local" / "reatume" / "config.json"
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    # On Linux AppConfigLocation is ~/.config/...; honor the requested ~/.local path there.
    if base.startswith(str(home / ".config")):
        return linux_path
    return Path(base) / "reatume" / "config.json"


def load_config() -> dict:
    path = config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return {**DEFAULTS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    # First run: create with espeak defaults.
    save_config(DEFAULTS)
    return dict(DEFAULTS)


def save_config(cfg: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")


def list_voices() -> list[str]:
    """English base voices + all espeak variants applied to en-us.
    Each entry is a usable espeak -v string."""
    voices = []
    try:
        out = subprocess.run(
            ["espeak-ng", "--voices"], capture_output=True, text=True, check=True
        ).stdout
        for line in out.splitlines()[1:]:
            cols = line.split()
            if len(cols) >= 4 and cols[1].startswith("en"):
                voices.append(cols[1])
    except (OSError, subprocess.CalledProcessError):
        voices = ["en-us", "en-gb"]

    variants = []
    try:
        out = subprocess.run(
            ["espeak-ng", "--voices=variant"], capture_output=True, text=True, check=True
        ).stdout
        for line in out.splitlines()[1:]:
            cols = line.split()
            if len(cols) >= 4:
                variants.append(cols[3])  # variant identifier column
    except (OSError, subprocess.CalledProcessError):
        pass

    voices += [f"en-us+{v}" for v in variants]
    return voices


CURATED_PIPER = [
    "en_US-amy-medium", "en_US-lessac-medium", "en_US-ryan-high",
    "en_US-kristin-medium", "en_GB-alba-medium", "en_GB-cori-high",
]
VOICES_JSON = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json?download=true"


def voices_dir() -> Path:
    d = Path.home() / ".local" / "reatume" / "voices"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_piper_models() -> list[str]:
    return sorted(p.stem for p in voices_dir().glob("*.onnx"))


def download_piper_voice(name: str) -> bool:
    r = subprocess.run(
        ["python3", "-m", "piper.download_voices", name, "--download-dir", str(voices_dir())],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def fetch_piper_catalog() -> dict:
    """Return {language_name: [voice_key, ...]} from Piper's voices.json."""
    with urllib.request.urlopen(VOICES_JSON, timeout=20) as resp:
        data = json.load(resp)
    langs: dict[str, list[str]] = {}
    for key, meta in data.items():
        lang = meta.get("language", {})
        name = lang.get("name_native") or lang.get("name_english") or lang.get("code", "?")
        langs.setdefault(name, []).append(key)
    for v in langs.values():
        v.sort()
    return dict(sorted(langs.items()))


class ReaTuMe(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ReaTuMe — read a page aloud")
        self.cfg = load_config()
        self.reader = None  # QProcess for the Go/read action
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)

        # 1) URL field + Go button
        url_row = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://example.com/article")
        self.url.returnPressed.connect(self.on_go)
        self.go_btn = QPushButton("Go")
        self.go_btn.clicked.connect(self.on_go)
        url_row.addWidget(self.url)
        url_row.addWidget(self.go_btn)
        outer.addLayout(url_row)

        # Engine radios (signal connected last, after all widgets exist).
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        engine_row = QHBoxLayout()
        self.rb_piper = QRadioButton("Piper (recommended)")
        self.rb_espeak = QRadioButton("espeak")
        grp = QButtonGroup(self)
        grp.addButton(self.rb_piper)
        grp.addButton(self.rb_espeak)
        (self.rb_piper if self.cfg["engine"] == "piper" else self.rb_espeak).setChecked(True)
        engine_row.addWidget(QLabel("Engine:"))
        engine_row.addWidget(self.rb_piper)
        engine_row.addWidget(self.rb_espeak)
        engine_row.addStretch()
        outer.addLayout(engine_row)

        # 2) Voice dropdown + Sample + Use (populated by _reload_voices below)
        voice_row = QHBoxLayout()
        self.voice = QComboBox()
        sample_btn = QPushButton("Sample")
        sample_btn.clicked.connect(self.on_sample)
        use_btn = QPushButton("Use")
        use_btn.clicked.connect(self.on_use)
        self.dl_btn = QPushButton("Download voice…")
        self.dl_btn.clicked.connect(self.on_download_curated)
        self.more_btn = QPushButton("More languages…")
        self.more_btn.clicked.connect(self.on_more_languages)
        voice_row.addWidget(QLabel("Voice:"))
        voice_row.addWidget(self.voice, 1)
        voice_row.addWidget(sample_btn)
        voice_row.addWidget(use_btn)
        voice_row.addWidget(self.dl_btn)
        voice_row.addWidget(self.more_btn)
        outer.addLayout(voice_row)

        # 3) Speed slider + 4) Word-gap slider
        form = QFormLayout()
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(80, 350)
        self.speed.setValue(self.cfg["speed"])
        self.speed_lbl = QLabel()
        self.speed.valueChanged.connect(self._on_speed)
        self.speed.sliderReleased.connect(self._save)
        self._on_speed(self.cfg["speed"])
        form.addRow(self.speed_lbl, self.speed)

        self.gap = QSlider(Qt.Orientation.Horizontal)
        self.gap.setRange(0, 25)
        self.gap.setValue(self.cfg["wordGap"])
        self.gap_lbl = QLabel()
        self.gap.valueChanged.connect(self._on_gap)
        self.gap.sliderReleased.connect(self._save)
        self._on_gap(self.cfg["wordGap"])
        form.addRow(self.gap_lbl, self.gap)
        outer.addLayout(form)

        self.status = QLabel(f"Voice: {self.cfg['voice']}")
        outer.addWidget(self.status)

        # Populate voices for the current engine, set gap state, then connect the
        # engine signal (now that self.voice and self.gap exist).
        self._reload_voices()
        self.gap.setEnabled(self.cfg["engine"] == "espeak")
        self._update_piper_buttons()
        self.rb_piper.toggled.connect(self._on_engine)

    # --- helpers ---
    def _update_piper_buttons(self):
        for b in (self.dl_btn, self.more_btn):
            b.setVisible(self.cfg["engine"] == "piper")

    def _on_engine(self, _checked=False):
        self.cfg["engine"] = "piper" if self.rb_piper.isChecked() else "espeak"
        self._reload_voices()
        self.gap.setEnabled(self.cfg["engine"] == "espeak")  # word-gap: espeak only
        self._update_piper_buttons()
        self._save()

    def _reload_voices(self):
        self.voice.clear()
        if self.cfg["engine"] == "piper":
            self.voice.addItems(list_piper_models())
            if self.cfg["piperModel"]:
                self._select_voice(self.cfg["piperModel"])
        else:
            self.voice.addItems(list_voices())
            self._select_voice(self.cfg["voice"])

    def _select_voice(self, name: str):
        i = self.voice.findText(name)
        if i < 0:
            self.voice.addItem(name)
            i = self.voice.findText(name)
        self.voice.setCurrentIndex(i)

    def _on_speed(self, v):
        self.cfg["speed"] = v
        self.speed_lbl.setText(f"Speed: {v} wpm")

    def _on_gap(self, v):
        self.cfg["wordGap"] = v
        self.gap_lbl.setText(f"Word gap: {v}")

    def _save(self):
        save_config(self.cfg)
        self.status.setText("Saved.")

    # --- actions ---
    def on_use(self):
        if self.cfg["engine"] == "piper":
            self.cfg["piperModel"] = self.voice.currentText()
        else:
            self.cfg["voice"] = self.voice.currentText()
        self._save()
        self.status.setText(f"Voice set: {self.voice.currentText()}")

    def on_sample(self):
        """Play a short sample in the currently highlighted voice + settings."""
        if self.cfg["engine"] == "piper":
            model = voices_dir() / f"{self.voice.currentText()}.onnx"
            if not model.exists():
                self.status.setText("Download this voice first.")
                return
            p = subprocess.Popen(["piper", "-m", str(model), "--output-raw"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            subprocess.Popen(["aplay", "-t", "raw", "-f", "S16_LE", "-r", "22050", "-c", "1", "-"],
                             stdin=p.stdout)
            p.stdin.write(SAMPLE_TEXT.encode())
            p.stdin.close()
        else:
            subprocess.Popen([
                "espeak-ng",
                "-v", self.voice.currentText(),
                "-s", str(self.cfg["speed"]),
                "-g", str(self.cfg["wordGap"]),
                SAMPLE_TEXT,
            ])

    def _download_and_refresh(self, name):
        from PySide6.QtWidgets import QMessageBox
        self.status.setText(f"Downloading {name}…")
        QApplication.processEvents()
        ok = download_piper_voice(name)
        if ok:
            self._reload_voices()
            self._select_voice(name)
            self.status.setText(f"Downloaded {name}")
        else:
            QMessageBox.warning(self, "Download failed", f"Could not download {name}.")
            self.status.setText("Download failed.")

    def on_download_curated(self):
        from PySide6.QtWidgets import QInputDialog
        have = set(list_piper_models())
        choices = [v for v in CURATED_PIPER if v not in have]
        if not choices:
            self.status.setText("All curated voices already downloaded.")
            return
        name, ok = QInputDialog.getItem(self, "Download voice", "Voice:", choices, 0, False)
        if ok and name:
            self._download_and_refresh(name)

    def on_more_languages(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        self.status.setText("Fetching catalog…")
        QApplication.processEvents()
        try:
            cat = fetch_piper_catalog()
        except Exception as e:
            QMessageBox.warning(self, "Catalog error", str(e))
            self.status.setText("Catalog fetch failed.")
            return
        lang, ok = QInputDialog.getItem(self, "Language", "Language:", list(cat), 0, False)
        if not (ok and lang):
            return
        name, ok = QInputDialog.getItem(self, "Voice", "Voice:", cat[lang], 0, False)
        if ok and name:
            self._download_and_refresh(name)

    def on_go(self):
        # Toggle: if reading, stop.
        if self.reader is not None:
            self._stop_reader()
            return
        url = self.url.text().strip()
        if not url:
            self.status.setText("Enter a URL first.")
            return
        self._save()
        self.reader = QProcess(self)
        self.reader.finished.connect(self._reader_done)
        self.go_btn.setText("Stop")
        self.status.setText(f"Reading: {url}")
        args = [str(CLI), url, "-s", str(self.cfg["speed"]), "-e", self.cfg["engine"]]
        if self.cfg["engine"] == "piper":
            args += ["-m", str(voices_dir() / f"{self.cfg['piperModel']}.onnx")]
        else:
            args += ["-v", self.cfg["voice"], "-g", str(self.cfg["wordGap"])]
        self.reader.start("node", args)

    def _stop_reader(self):
        """SIGTERM the node reader; it reaps its espeak child. Hard-kill if it
        somehow ignores the signal (should not happen)."""
        r = self.reader
        if r is None:
            return
        self.status.setText("Stopping...")
        r.terminate()  # SIGTERM — node's handler kills espeak
        QTimer.singleShot(2000, lambda: r.kill() if r.state() != QProcess.ProcessState.NotRunning else None)

    def _reader_done(self):
        self.reader = None
        self.go_btn.setText("Go")
        self.status.setText("Done.")

    def closeEvent(self, event):
        # Don't leave a reader (and its espeak child) running after the window closes.
        self._stop_reader()
        super().closeEvent(event)


def main():
    app = QApplication([])
    win = ReaTuMe()
    win.resize(560, 200)
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
