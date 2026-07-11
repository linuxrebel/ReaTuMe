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

- Voice quality: espeak-ng is robotic but clear. Upgrade path: swap `speak.js`
  to pipe into `piper` (neural TTS) if natural voice wanted later.
- `turndown` npm dep no longer needed (was for markdown output) — can drop.
- Auth/paywall pages: out of scope, fail cleanly.
