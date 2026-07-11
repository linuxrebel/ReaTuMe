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

        # 2) Voice dropdown + Sample + Use
        voice_row = QHBoxLayout()
        self.voice = QComboBox()
        self.voice.addItems(list_voices())
        self._select_voice(self.cfg["voice"])
        sample_btn = QPushButton("Sample")
        sample_btn.clicked.connect(self.on_sample)
        use_btn = QPushButton("Use")
        use_btn.clicked.connect(self.on_use)
        voice_row.addWidget(QLabel("Voice:"))
        voice_row.addWidget(self.voice, 1)
        voice_row.addWidget(sample_btn)
        voice_row.addWidget(use_btn)
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

    # --- helpers ---
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
        self.cfg["voice"] = self.voice.currentText()
        self._save()
        self.status.setText(f"Voice set: {self.cfg['voice']}")

    def on_sample(self):
        """Play a short sample in the currently highlighted voice + settings."""
        subprocess.Popen([
            "espeak-ng",
            "-v", self.voice.currentText(),
            "-s", str(self.cfg["speed"]),
            "-g", str(self.cfg["wordGap"]),
            SAMPLE_TEXT,
        ])

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
        self.reader.start("node", [
            str(CLI), url,
            "-v", self.cfg["voice"],
            "-s", str(self.cfg["speed"]),
            "-g", str(self.cfg["wordGap"]),
        ])

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
