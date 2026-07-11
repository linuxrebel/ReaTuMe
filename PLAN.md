# ReaTuMe — CLI Reader-View Tool

CLI that navigates to a URL, renders it, strips clutter via Mozilla's
Readability (the same lib Firefox Reader View uses), prints clean article text.

## Design decision

Don't automate Firefox's Reader View UI (no CLI hook exists for it). Instead:
load the page in headless Firefox via Playwright, then run `@mozilla/readability`
against the rendered DOM — same extraction algorithm, no UI automation needed.

## Stack

- Node.js CLI
- `playwright` — headless Firefox, full JS rendering (SPA support)
- `@mozilla/readability` — article extraction (official Mozilla package)
- `jsdom` — DOM for Readability to parse
- `turndown` — HTML → Markdown (for `--format md`)
- `commander` — CLI arg parsing

## Layout

```
ReaTuMe/
  package.json
  bin/reatume.js    # entry point
  src/cli.js        # commander: url, --format text|md|json, --out, --timeout, --browser
  src/fetch.js       # Playwright: launch firefox headless, goto(url, waitUntil: networkidle), return page.content()
  src/extract.js     # jsdom(html) -> new Readability(doc).parse()
  src/format.js       # text/md/json formatting
```

## Flow

1. `reatume <url> [--format text|md|json] [--out file]`
2. Launch Playwright Firefox headless, goto(url), wait networkidle
3. Grab rendered HTML via `page.content()`
4. Parse with jsdom, run Readability -> `{title, byline, content, textContent, excerpt}`
5. Format:
   - `text` (default): title + `textContent`, printed to stdout
   - `md`: turndown on `content` (keeps headings/links/lists)
   - `json`: full object, for piping into other tools
6. `--out file` writes instead of stdout

## Error handling

- Readability returns `null` (non-article page) -> warn to stderr, fall back to raw body textContent
- Playwright timeout -> clear error, exit 1
- Browser context always closed in `finally`

## Setup

None needed — Playwright + Firefox binary already installed system-wide
(global `playwright` npm package, `~/.cache/ms-playwright/firefox-*`).

## Open items / future

- Auth/paywall pages: out of scope, fail cleanly
- UA/viewport spoofing if sites block headless browsers
