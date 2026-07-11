# ReaTuMe

CLI that navigates to a URL, strips the clutter (nav, ads, cookie banners) using
Mozilla's Readability — the same engine behind Firefox Reader View — and **reads
the article aloud** via text-to-speech.

## How it works

Firefox Reader View has no CLI hook, so ReaTuMe doesn't automate the Firefox UI.
Instead it loads the page in headless Firefox (Playwright), runs Readability
against the rendered DOM to get clean article text, and pipes that text to
`espeak-ng` to speak it.

```
  URL
   │
   ▼
┌──────────────┐   rendered HTML   ┌──────────────┐   clean text   ┌──────────────┐
│  fetch.js    │ ────────────────▶ │  extract.js  │ ─────────────▶ │  speak.js    │
│  Playwright  │                   │  jsdom +     │                │  espeak-ng   │
│  headless FF │                   │  Readability │                │  (aloud)     │
└──────────────┘                   └──────────────┘                └──────┬───────┘
   goto(url)                        Readability.parse()             spawn, pipe stdin
   waitUntil: load                  fallback: <body> text                  │
                                                                           ▼
                                                                     🔊 speakers
                                                                     (+ optional WAV)
```

`bin/reatume.js` → `src/cli.js` (commander) orchestrates the three stages.

## Requirements

**System binaries** (must be on PATH):

| Binary      | Purpose                        | Install (Fedora)          |
|-------------|--------------------------------|---------------------------|
| `node`      | runtime (v18+; tested v24)     | `dnf install nodejs`      |
| `espeak-ng` | text-to-speech engine          | `dnf install espeak-ng`   |

**Firefox** for Playwright is fetched separately (not a system package):

```
npx playwright install firefox
```

**npm dependencies** (installed by `npm install`):

| Package                 | Role                                      |
|-------------------------|-------------------------------------------|
| `playwright`            | headless Firefox, JS rendering            |
| `@mozilla/readability`  | article extraction                        |
| `jsdom`                 | DOM for Readability to parse              |
| `commander`             | CLI argument parsing                      |

## Setup

```
git clone <repo> ReaTuMe
cd ReaTuMe
npm install
npx playwright install firefox   # one-time, ~105 MB
```

## Usage

```
node bin/reatume.js <url> [options]
```

| Option              | Description                                  | Default |
|---------------------|----------------------------------------------|---------|
| `-s, --speed <wpm>` | speech rate, words per minute                | 175     |
| `-v, --voice <name>`| espeak-ng voice (e.g. `en-us`, `en-gb`)      | default |
| `-o, --out <file>`  | also save spoken audio to a WAV file         | —       |
| `--timeout <ms>`    | page load timeout                            | 30000   |

### Examples

```
# Read an article aloud
node bin/reatume.js https://en.wikipedia.org/wiki/Espeak

# Faster, British voice
node bin/reatume.js https://example.com/post -s 220 -v en-gb

# Save narration to a file (also plays live)
node bin/reatume.js https://example.com/post -o article.wav
```

List available voices: `espeak-ng --voices`

## Behavior notes

- **Non-article pages** (homepages, search results): Readability may find no
  article; ReaTuMe falls back to the raw `<body>` text.
- **Error pages** are read verbatim — a 404 page is spoken as-is (no HTTP-status
  check).
- **Voice quality**: espeak-ng is clear but robotic. To upgrade, swap `speak.js`
  to pipe into `piper` (neural TTS).

## Exit codes

`0` success · `1` load failure, no readable text, or `espeak-ng` missing.
