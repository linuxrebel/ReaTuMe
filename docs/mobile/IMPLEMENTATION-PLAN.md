# ReaTuMe Mobile — Implementation Plan (Flutter, iOS + Android)

**Goal:** One Flutter app that loads a URL, extracts the article with Readability.js
in a WebView, and reads it aloud with the OS TTS engine — plus share-sheet intake and
background playback.

**Architecture:** See `ARCHITECTURE.md`. Offscreen WebView → inject Readability →
`{title, text}` over a JS channel → `flutter_tts`. No backend.

**Tech stack:** Flutter/Dart, `webview_flutter`, `flutter_tts`, `shared_preferences`,
`receive_sharing_intent`, `audio_service`, `speech_to_text` (Phase 7), vendored
`readability.js`. Accessibility via Flutter `Semantics` + VoiceOver/TalkBack.

## Global constraints

- One codebase targets both platforms; avoid platform-specific Dart except in the
  thin iOS/android config (Info.plist, AndroidManifest).
- No backend, no network calls except the WebView loading the user's URL.
- Internet permission only; no mic/contacts/storage.
- Each service (`extractor`, `tts_service`, `settings`) has one responsibility and a
  typed interface, testable in isolation.
- Dart null-safety on; `flutter analyze` clean; `flutter test` green before each phase closes.
- Minimum targets: iOS 14+, Android 8 (API 26)+ (TextToSpeech + WebView baseline).

---

## Phase 0 — Project scaffold

**Deliverable:** a running empty Flutter app on both simulators.

- [ ] `flutter create --org com.sparenbergs --platforms ios,android reatume_mobile`
- [ ] Add deps to `pubspec.yaml`: `webview_flutter`, `flutter_tts`,
      `shared_preferences`, `receive_sharing_intent`, `audio_service`.
- [ ] Vendor Readability: download the browser build to `assets/readability.js`;
      register it under `flutter: assets:` in `pubspec.yaml`.
- [ ] iOS `Info.plist`: `UIBackgroundModes = [audio]`; `NSAppTransportSecurity`
      allow arbitrary loads (arbitrary user URLs).
- [ ] Android `AndroidManifest.xml`: `<uses-permission INTERNET>`.
- [ ] Verify: `flutter run` shows the default app on an iOS simulator and an Android emulator.

---

## Phase 1 — Extractor service (WebView + Readability)

**Deliverable:** `extract(url) -> Article` returns clean title + text for a real URL.

**Files:** `lib/models/article.dart`, `lib/services/extractor.dart`

- [ ] `Article` model: `class Article { final String title; final String text; }`.
- [ ] `extractor.dart`: a headless/offscreen `WebViewController`:
  - `loadRequest(Uri.parse(url))`
  - on `onPageFinished`: inject the asset `readability.js`, then run a runner script:
    ```js
    (function(){
      try {
        var doc = document.cloneNode(true);
        var a = new Readability(doc).parse();
        var out = a && a.textContent && a.textContent.trim()
          ? {title: a.title||'', text: a.textContent.trim()}
          : {title: document.title||'', text: (document.body?document.body.innerText:'').trim()};
        ReatumeChannel.postMessage(JSON.stringify(out));
      } catch(e){ ReatumeChannel.postMessage(JSON.stringify({title:'',text:'',error:String(e)})); }
    })();
    ```
  - a `JavaScriptChannel('ReatumeChannel')` completes a `Completer<Article>`.
  - timeout (e.g. 30 s) → error; optional 1 auto-scroll + short delay before extract
    to trigger lazy content.
- [ ] Verify (manual, device/emulator): a tiny debug button calls
      `extract('https://en.wikipedia.org/wiki/Coffee')` and prints title + text length
      (> 1000 chars) to the console. Try one SPA (e.g. a Vercel blog post) too.

---

## Phase 2 — TTS service

**Deliverable:** speak arbitrary text with selectable voice + rate; stop; progress.

**Files:** `lib/services/tts_service.dart`

- [ ] Wrap `flutter_tts`:
  - `init()` — set language, await engine.
  - `Future<List<Voice>> voices()` — from `getVoices`, filtered to the UI language(s).
  - `setVoice(voice)`, `setRate(double)`, `setPitch(double)`.
  - `speak(String text)`, `stop()`.
  - expose a progress stream from `setProgressHandler` (word ranges) for a progress bar.
  - chunk very long text into sentence batches to avoid engine limits; speak sequentially.
- [ ] Verify (manual): a debug button speaks "The quick brown fox…" on both platforms;
      changing rate audibly changes speed; `stop()` halts immediately.

---

## Phase 3 — Home UI wiring (MVP)

**Deliverable:** type a URL → Read → hear the article; Stop; speed slider. This is the
shippable MVP.

**Files:** `lib/ui/home_page.dart`, `lib/ui/player_controls.dart`, `lib/services/settings.dart`, `lib/app.dart`, `lib/main.dart`

- [ ] `settings.dart` over `shared_preferences`: `voiceId`, `rate`, `pitch` with defaults.
- [ ] `home_page.dart`: URL `TextField` + **Read** button; a loading spinner while
      `extract()` runs; on success call `tts.speak(article.text)`.
- [ ] `player_controls.dart`: Play/Pause/Stop, speed `Slider` (bound to `tts.setRate`
      + settings), a progress indicator from the TTS progress stream, current title.
- [ ] Error handling: extraction failure or empty text → a `SnackBar`/inline message
      ("Couldn't read this page") — never silent (lesson from desktop).
- [ ] **Accessibility (from the start):** wrap every control in `Semantics` with clear
      labels; sensible focus order; announce state changes ("Reading", "Paused",
      "No article found") via `SemanticsService.announce`. Verify with VoiceOver
      (iOS) and TalkBack (Android) that the whole MVP is operable eyes-free.
- [ ] `main.dart`: init TTS + settings before `runApp`.
- [ ] Verify (manual): read a real article end-to-end on iOS and Android; Stop works;
      speed persists across relaunch; a blank page shows the error message.

---

## Phase 4 — Share-sheet intake

**Deliverable:** "Share → ReaTuMe" from any app starts reading that URL.

**Files:** `lib/services/share_intake.dart`, iOS Share Extension, Android intent-filter

- [ ] Android: `AndroidManifest` `<intent-filter>` for `ACTION_SEND` `text/plain`.
- [ ] iOS: add a Share Extension target; configure `receive_sharing_intent`.
- [ ] `share_intake.dart`: listen for initial + streamed shared text; extract a URL from
      it; route to home and auto-start reading.
- [ ] Verify (manual): from the mobile browser, Share a page to ReaTuMe → it opens and
      reads. Test cold start (initial share) and warm (streamed share).

---

## Phase 5 — Background playback + lock-screen controls

**Deliverable:** reading continues with the screen off; play/pause/stop on the lock screen.

**Files:** integrate `audio_service` around `tts_service`

- [ ] Wrap the TTS session in an `audio_service` `BackgroundAudioTask`/handler exposing
      play/pause/stop + metadata (title).
- [ ] Android: foreground service + `MediaSession` notification.
- [ ] iOS: confirm `UIBackgroundModes audio`; map remote-control events to TTS.
- [ ] Verify (manual): start reading, lock the phone → audio continues; lock-screen
      pause/resume/stop work on both platforms.

---

## Phase 6 — Voice picker + sample + polish

**Deliverable:** choose among OS voices, hear a sample, set as default.

**Files:** `lib/ui/voice_picker.dart`

- [ ] List `tts.voices()`; show name/locale; **Sample** speaks a line in that voice;
      **Use** persists it via settings.
- [ ] Pitch control (replaces desktop word-gap).
- [ ] App icon (reuse `assets/reatume.svg`, export to the required raster sizes),
      splash, light/dark theme.
- [ ] `flutter analyze` clean; basic widget tests for `home_page` (renders, Read button
      disabled when URL empty) and a unit test for the URL-extraction-from-shared-text helper.
- [ ] Verify: full pass on a physical iPhone and Android phone; voices switch and persist.

---

## Phase 7 — Eyes-free voice control

**Deliverable:** the app can be driven hands-free by spoken commands, with spoken
confirmations. (Screen-reader support from Phase 3 + media controls from Phase 5 are
prerequisites and already give a large amount of eyes-free capability.)

**Files:** `lib/services/voice_control.dart`, `lib/services/command_parser.dart`, plus
platform assistant config

- [ ] Add `speech_to_text`. `voice_control.dart`: **push-to-talk** — a large button
      (and double-tap-anywhere gesture) starts listening; on result, pass the transcript
      to the parser. On-device recognition where available; request mic permission with
      a clear rationale (opt-in).
- [ ] `command_parser.dart`: keyword → action map (no LLM). Commands: `read that`,
      `pause`, `resume`/`play`, `stop`, `faster`, `slower`, `restart`, `next`/`skip`,
      `what is this` (announce title). Unknown → spoken "Sorry, I didn't catch that."
- [ ] **Spoken confirmation** for every action via the TTS service
      ("Paused.", "Reading from <site>.", "No article found."); optional haptic.
- [ ] Platform assistant hooks: iOS **App Intents** (Siri) and Android **Assistant
      App Actions** for "read this / read that in ReaTuMe" so the OS wake word launches
      the action. (Custom "Hey ReaTuMe" wake word is explicitly out of scope for v1.)
- [ ] **Never require URL dictation** — voice intake routes through share/clipboard/
      "read that", not spelled-out URLs.
- [ ] Verify (manual, eyes-closed test): complete a full session — trigger, "read that"
      on a shared page, "faster", "pause", "resume", "stop" — without looking at the
      screen, on both platforms. Unit-test `command_parser` (transcript → action) with
      a table of phrasings.

## Testing strategy

Flutter unit/widget tests (`flutter test`) cover the pure logic — the URL parser, the
settings layer, widget states. The WebView-extraction and TTS-audio paths are integration
concerns verified on device/emulator per phase (they need a real browser + audio engine),
mirroring how the desktop app was verified by driving the real pipeline.

## Release checklist (later, per store)

- **Android:** signed AAB, Play Console listing, data-safety form (no data collected),
  target API level current.
- **iOS:** App Store Connect, privacy nutrition label (no data collected), accessibility
  framing in the description, Share Extension reviewed, TestFlight beta first.

## Effort

- MVP (Phases 0–3): a few focused days.
- Store-ready v1 (Phases 0–6): ~1–2 weeks.
