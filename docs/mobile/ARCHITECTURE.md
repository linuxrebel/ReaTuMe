# ReaTuMe Mobile — Architecture & Design

**Status:** Design. Target: a single Flutter codebase shipping **iOS + Android**.
**Relationship to desktop:** a *reimplementation of the concept*, not a port. The
desktop app's three heaviest dependencies (headless Firefox, Node, piper/espeak)
are all replaced by capabilities the phone already provides.

---

## 1. Vision

Give a URL (typed or shared from any app), and ReaTuMe reads the article aloud —
clean, no nav/ads — using the phone's built-in neural voices, with background
playback and lock-screen controls.

Same product promise as desktop; a leaner implementation.

## 2. Why a rewrite is *simpler* than a port

| Desktop dependency | Mobile replacement | Effect |
|--------------------|--------------------|--------|
| Playwright headless Firefox (~100 MB) | Native **WebView** (WKWebView / Android WebView) | Nothing to bundle; a real browser with the user's session |
| `@mozilla/readability` under jsdom (Node) | **Readability.js injected into the WebView** | Runs in its native browser environment; no jsdom |
| piper + espeak + model downloads (~60 MB) | **OS TTS** (AVSpeechSynthesizer / android TextToSpeech) | On-device neural voices, free, better quality |
| `aplay` audio routing | OS audio + media session | Background play + lock-screen controls for free |
| Node runtime | Dart / Flutter | One language, both platforms |

The desktop complexity largely evaporates. What remains is a small app.

## 3. Stack

- **Flutter** (Dart) — one codebase, iOS + Android.
- **`webview_flutter`** — load the URL, run JavaScript, read results via a JS channel.
- **`flutter_tts`** — wraps AVSpeechSynthesizer (iOS) and TextToSpeech (Android):
  voices, rate, pitch, speak/stop, word-boundary progress events.
- **`shared_preferences`** — settings persistence.
- **`receive_sharing_intent`** — accept URLs shared from other apps (share sheet).
- **`audio_service`** (phase 2) — background playback + lock-screen/media-notification controls.
- **Readability.js** — vendored as a bundled asset, injected at runtime.

No backend. No server-side extraction. Everything runs on device.

## 4. Core flow

```
 URL (typed or shared)
        │
        ▼
 ┌──────────────────┐   page loaded   ┌───────────────────────┐  {title,text}  ┌──────────────┐
 │  WebView (hidden)│ ───────────────▶│ inject Readability.js  │ ─────────────▶ │  TTS service │
 │  load(url)       │                 │ new Readability(doc)   │   JS channel   │  flutter_tts │
 │  wait: onPageEnd │                 │ .parse().textContent   │                │  speak(text) │
 └──────────────────┘                 └───────────────────────┘                └──────┬───────┘
        real browser session                fallback: document.body.innerText          │
        (SPAs render, less bot-blocking)                                               ▼
                                                                            🔊 speaker / lock screen
```

1. Load the URL in an **offscreen** WebView.
2. On page-finished, inject `readability.js` + a tiny runner that calls
   `new Readability(document.cloneNode(true)).parse()` and posts
   `{title, textContent}` back over a JS channel. Fallback: `document.body.innerText`.
3. Hand `textContent` to the TTS service; speak with the chosen voice + rate.
4. Controls: play / pause / stop, speed, voice, progress (via TTS word-boundary
   callbacks).

## 5. Modules (single codebase)

```
reatume_mobile/
  pubspec.yaml
  assets/readability.js              # vendored Mozilla Readability
  lib/
    main.dart                        # app entry, TTS + settings init
    app.dart                         # MaterialApp, theming, routes
    models/article.dart              # Article { title, text }
    services/extractor.dart          # WebView load + Readability injection -> Article
    services/tts_service.dart        # flutter_tts wrapper: voices, rate, speak, stop, progress
    services/settings.dart           # shared_preferences: voice, rate, pitch
    services/share_intake.dart       # receive_sharing_intent -> incoming URLs
    ui/home_page.dart                # URL field + Read button + controls
    ui/player_controls.dart          # play/pause/stop, speed slider, progress
    ui/voice_picker.dart             # list OS voices, sample, select
  ios/    Info.plist: UIBackgroundModes(audio); optional Share Extension
  android/ AndroidManifest: INTERNET, ACTION_SEND intent-filter, FGS for playback
```

Each service has one job and a clean interface, so they're testable in isolation:
- `extractor.dart`: `Future<Article> extract(String url)`
- `tts_service.dart`: `speak(text)`, `stop()`, `setVoice()`, `setRate()`, `Stream<progress>`
- `settings.dart`: typed getters/setters over shared_preferences

## 6. Feature parity with desktop

| Desktop feature | Mobile |
|-----------------|--------|
| URL → read aloud | ✅ WebView + Readability + OS TTS |
| Voice selection | ✅ OS voices (`getVoices`); many high-quality, downloadable in system settings |
| Speed slider | ✅ TTS rate |
| Word-gap slider | ➖ dropped (OS TTS has no equivalent); expose **pitch** instead |
| Sample a voice | ✅ speak a sample line |
| Engine radios (piper/espeak) | ➖ N/A — one OS engine, better than both |
| Get Voice / catalog download | ➖ N/A — the OS manages/downloads voices |
| Config file | ✅ shared_preferences |
| Loading indicator | ✅ spinner while WebView loads + extracts |
| Stop button | ✅ + system media controls |
| **New on mobile** | **Share-sheet intake, background playback, lock-screen controls, sleep timer** |

## 7. Platform specifics

**iOS**
- `WKWebView` (via webview_flutter), `AVSpeechSynthesizer` (via flutter_tts).
- `Info.plist`: `UIBackgroundModes = [audio]` for background reading.
- Optional **Share Extension** so Safari/any app can "Share → ReaTuMe".
- App Store review: frame as an **accessibility / reader** tool; ship real polish
  (utility-thin apps get scrutiny). A share extension materially strengthens the case.

**Android**
- `WebView`, `TextToSpeech` (via flutter_tts).
- Manifest: `INTERNET`; `<intent-filter>` for `ACTION_SEND text/plain` (share sheet).
- **Foreground service** + `MediaSession` for background playback and a media
  notification (via `audio_service`).

## 8. Permissions & privacy

- **Internet** only. No microphone, no contacts, no storage.
- Extraction is in-memory; nothing leaves the device (no backend).
- Optional: local reading history stored on-device (opt-in, phase 3).

## 9. Risks & mitigations

- **iOS App Store review** (thin utility) → accessibility framing + share extension + polish.
- **Extraction reliability** on heavy/lazy sites → wait for `onPageFinished`, optional
  short settle delay + one auto-scroll to trigger lazy content; Readability fallback to body text.
- **Paywalls / login** → the WebView uses the user's real session, so it renders
  *better* than desktop headless; truly paywalled bodies still limited.
- **Voice quality variance** across devices/OS versions → let the user pick; default
  to the highest-quality installed voice.
- **Long-article background playback** → `audio_service` foreground service (Android)
  and background audio mode (iOS); chunk very long text to keep TTS engines happy.

## 10. Roadmap

- **MVP (Phase 1–3):** URL field → load → extract → speak; play/stop; speed; voice picker.
- **v1 (Phase 4–5):** share-sheet intake; background playback + lock-screen controls; progress/scrubbing.
- **v2 (later):** reading history, save-for-offline (store extracted text), sleep timer,
  highlight-follow (using TTS word-boundary events), per-site tweaks.

## 11. Reuse from the desktop repo

- **Readability.js** — same library; vendor the browser build as an asset.
- **The concept + UX decisions** (clean text, voice/speed, sample, loading state).
- Nothing else transfers (Node/PySide6/piper/Playwright are desktop-only).

Effort estimate: a working MVP in a few days; a polished, store-ready v1 in ~1–2
weeks of focused work. See `IMPLEMENTATION-PLAN.md`.
