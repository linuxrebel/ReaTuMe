# ReaTuMe — CLI Read-Aloud Tool

CLI that navigates to a URL, strips clutter via Mozilla's Readability (the same
lib Firefox Reader View uses), then **reads the article aloud** via TTS.

## Design decision

Don't automate Firefox's Reader View UI (no CLI hook exists for it). Instead:
load the page in headless Firefox via Playwright, run `@mozilla/readability`
against the rendered DOM to get clean article text (no nav/ads/junk), then pipe
that text to `espeak-ng` to speak it aloud.

Readability stage matters even for audio: without it, TTS would read menus,
cookie banners, and ad copy.

## Stack

- Node.js CLI
- `playwright` — headless Firefox, full JS rendering (SPA support)
- `@mozilla/readability` — article extraction (official Mozilla package)
- `jsdom` — DOM for Readability to parse
- `commander` — CLI arg parsing
- `espeak-ng` — TTS, spoken aloud (system binary, already installed, no npm dep)

## Layout

```
ReaTuMe/
  package.json
  bin/reatume.js    # entry point
  src/cli.js        # commander: url, --speed, --voice, --out
  src/fetch.js       # Playwright: launch firefox headless, goto(url, waitUntil: networkidle), return page.content()
  src/extract.js     # jsdom(html) -> new Readability(doc).parse() -> textContent
  src/speak.js        # spawn espeak-ng, pipe article text to stdin
```

## Flow

1. `reatume <url> [--speed wpm] [--voice name] [--out file.wav]`
2. Launch Playwright Firefox headless, goto(url), wait networkidle
3. Grab rendered HTML via `page.content()`
4. Parse with jsdom, run Readability -> clean `textContent`
5. Spawn `espeak-ng`, pipe text to stdin -> speaks aloud
   - `--speed` -> espeak `-s <wpm>` (default ~175)
   - `--voice` -> espeak `-v <name>`
   - `--out file.wav` -> espeak `-w <file>` (also saves audio)

## Error handling

- Readability returns `null` (non-article page) -> warn to stderr, fall back to raw body textContent
- Playwright timeout -> clear error, exit 1
- Browser context always closed in `finally`
- `espeak-ng` missing -> clear error pointing at install

## Setup

None needed — Playwright + Firefox binary and `espeak-ng` all already installed.

## Notes / future

- `turndown` npm dep no longer needed (was for markdown output) — dropped.
- Auth/paywall pages: out of scope, fail cleanly.

---

# v0.2 — Piper neural TTS with espeak fallback

## Goal

espeak-ng is clear but robotic, hard to follow for long articles. Add **Piper**
(neural, offline, CPU-fast) as a second engine, selectable in the GUI, with
espeak-ng retained as an always-available fallback.

## Decisions (from brainstorming)

- **Engine model:** user-selectable via two radio buttons — **Piper
  (recommended)** and **espeak**. If Piper is selected but its binary or the
  chosen model is missing, auto-fall-back to espeak with a notice.
- **Voice acquisition:** in-app downloader. A **curated** shortlist of ~6 good
  English Piper voices, one click downloads a voice. A **"More languages…"**
  button at the bottom opens a modal that fetches Piper's live catalog for any
  language (e.g. Korean).
- Downloaded voices live in `~/.local/reatume/voices/` as
  `<name>.onnx` + `<name>.onnx.json` (Piper needs both).

## New dependencies

- **piper-tts** (`pip install piper-tts`) — user-installed; provides the `piper`
  command. `onnxruntime` (its dependency) already present.
- Piper voice model(s) — downloaded by the app into the voices dir.
- Audio player for live playback — Fedora has `pw-play`, `paplay`, `aplay`,
  `ffplay`. Use `aplay` for raw PCM (portable ALSA), pick first available.

## Audio pipeline (speak.js)

espeak plays its own audio; Piper does not — it emits samples, so we pipe them
to a player.

- **espeak branch (unchanged):** `spawn espeak-ng`, pipe text to stdin.
- **Piper branch:** `spawn piper --model <voices>/<name>.onnx --output-raw`,
  write article text to piper stdin; pipe piper stdout (raw 16-bit mono PCM) into
  `aplay -t raw -f S16_LE -r <sample_rate> -c 1 -`. Sample rate is read from the
  model's `.onnx.json` (`audio.sample_rate`). Streaming: Piper emits per
  sentence, so audio starts within a second or two, not after full synthesis.

Piper spawns **two** child processes (piper + player). The existing
SIGTERM/SIGINT reaping (v0.1 Stop fix) is extended to kill **both** children, so
Stop / window-close still leaves nothing orphaned.

## Speed / word-gap mapping

- Speed slider stays; interpretation is engine-aware:
  - espeak: `-s <wpm>` (current).
  - Piper: `--length-scale <s>`, mapped `length_scale = 175 / wpm` (higher wpm =
    shorter = faster), clamped to a sane range (~0.5–2.0).
- Word-gap slider is espeak-only; disabled (greyed) when Piper is selected.

## Config schema (`~/.local/reatume/config.json`)

```json
{
  "engine": "piper",          // "piper" | "espeak"
  "voice": "en-us",            // espeak voice
  "piperModel": "en_US-amy-medium",  // stem of the selected .onnx in voices dir
  "speed": 175,
  "wordGap": 0
}
```

First-run defaults: `engine: "espeak"` (works with zero setup) until a Piper
voice is downloaded, then the app may switch the default to Piper.

## CLI (node) changes

- `src/cli.js`: add `--engine <piper|espeak>` and `--model <path>` options.
- `src/speak.js`: dispatch on engine; Piper pipeline as above; auto-fallback to
  espeak (with stderr notice) if piper binary or model file is absent.

## GUI (reatume_ui.py) changes

- **Engine radios:** ( ) Piper (recommended)  ( ) espeak.
- **Engine-aware voice panel:**
  - Piper: dropdown of downloaded models (`*.onnx` in voices dir) +
    **"Download voice…"** (curated dialog) + **"More languages…"** (catalog modal).
  - espeak: existing voice dropdown (bases + variants).
- Word-gap slider greyed when Piper selected.
- Sample / Use / Go all route through the selected engine.

## Downloader design

- **Curated dialog:** hardcoded list of ~6 English voices with their HuggingFace
  `resolve/main/...` URLs; Download fetches the `.onnx` + `.onnx.json` pair into
  the voices dir (Python `urllib`, no new dep). Progress + error notice.
- **"More languages…" modal:** on open, fetch `voices.json` catalog from
  HuggingFace; language dropdown → voice dropdown → Download. Isolated: this is
  the only path that touches the live catalog/network; the curated path never does.

## New/changed files

```
src/cli.js          # + --engine, --model
src/speak.js         # engine dispatch, Piper pipeline, reap both children
reatume_ui.py         # engine radios, engine-aware voice panel, disable gap for piper
  (voices logic)       # list local models, curated catalog, download, remote catalog fetch
                       #   — kept in reatume_ui.py or a small voices.py helper
```

## Error handling

- Piper binary missing → fallback to espeak + notice.
- Selected model file missing → fallback to espeak + notice.
- Download failure (network/404) → error dialog, voices dir left clean (no
  half-written files).
- Player missing → error pointing at install.
- Stop/close kills piper + player (no orphans), same guarantee as v0.1.

## Out of scope (YAGNI)

- No GPU/onnxruntime-gpu path (CPU is fine for Piper).
- No per-sentence highlighting / follow-along UI.
- No voice deletion UI (delete files manually for now).
- Windows/macOS player selection (Linux `aplay` now; revisit at packaging).
