const { spawn, spawnSync } = require('child_process');
const fs = require('fs');

// Read sample rate from a Piper model's JSON sidecar (default 22050).
function piperSampleRate(modelPath) {
  try {
    const cfg = JSON.parse(fs.readFileSync(`${modelPath}.json`, 'utf8'));
    return cfg.audio && cfg.audio.sample_rate ? cfg.audio.sample_rate : 22050;
  } catch {
    return 22050;
  }
}

function piperAvailable() {
  return spawnSync('piper', ['--help']).error == null;
}

// Speak via Piper: text -> piper stdin, raw PCM -> aplay. Resolves on finish or
// signal. Kills BOTH children on SIGTERM/SIGINT so Stop leaves no orphans.
function speakPiper(text, { model, speed }) {
  const rate = piperSampleRate(model);
  const args = ['-m', model, '--output-raw'];
  if (speed) {
    const scale = Math.min(2.0, Math.max(0.5, 175 / speed)); // wpm -> length_scale
    args.push('--length-scale', String(scale));
  }
  return new Promise((resolve, reject) => {
    // Connect piper's stdout straight into aplay's stdin at the fd level — node
    // must NOT sit in the audio byte path, or a stalled event loop / backpressured
    // stderr would underrun aplay and garble the PCM. Child logs are dropped
    // ('ignore') so nothing can backpressure through the parent.
    const piper = spawn('piper', args, { stdio: ['pipe', 'pipe', 'ignore'] });
    const player = spawn('aplay', ['-t', 'raw', '-f', 'S16_LE', '-r', String(rate), '-c', '1', '-'],
      { stdio: [piper.stdout, 'ignore', 'ignore'] });

    const killAll = () => { piper.kill('SIGKILL'); player.kill('SIGKILL'); };
    const onSignal = () => killAll();
    process.once('SIGTERM', onSignal);
    process.once('SIGINT', onSignal);
    const cleanup = () => {
      process.removeListener('SIGTERM', onSignal);
      process.removeListener('SIGINT', onSignal);
    };

    let settled = false;
    const done = (fn, arg) => { if (!settled) { settled = true; cleanup(); fn(arg); } };
    piper.on('error', (e) => { killAll(); done(reject, e); });
    player.on('error', (e) => { killAll(); done(reject, e); });
    // Resolve when the player finishes (audio fully played), or on purposeful signal.
    player.on('close', (code, signal) => { killAll(); (code === 0 || signal) ? done(resolve) : done(reject, new Error(`aplay exited ${code}`)); });

    piper.stdin.write(text);
    piper.stdin.end();
  });
}

// Speak text aloud. engine: "espeak" (default) or "piper". Piper falls back to
// espeak (with a notice) when its binary or model is missing.
function speak(text, { engine, voice, model, speed, gap, outFile } = {}) {
  if (engine === 'piper') {
    if (piperAvailable() && model && fs.existsSync(model)) {
      return speakPiper(text, { model, speed });
    }
    process.stderr.write('Piper unavailable (binary or model missing); using espeak.\n');
  }
  const args = [];
  if (speed) args.push('-s', String(speed));
  if (voice) args.push('-v', voice);
  if (gap != null) args.push('-g', String(gap));
  if (outFile) args.push('-w', outFile);

  return new Promise((resolve, reject) => {
    const child = spawn('espeak-ng', args, { stdio: ['pipe', 'inherit', 'inherit'] });

    // espeak buffers the whole article, so killing node alone leaves it
    // reading to the end (orphaned). Reap the child when we're terminated.
    const onSignal = () => child.kill('SIGKILL');
    process.once('SIGTERM', onSignal);
    process.once('SIGINT', onSignal);
    const cleanup = () => {
      process.removeListener('SIGTERM', onSignal);
      process.removeListener('SIGINT', onSignal);
    };

    child.on('error', (err) => {
      cleanup();
      if (err.code === 'ENOENT') {
        reject(new Error('espeak-ng not found. Install it (e.g. dnf install espeak-ng).'));
      } else {
        reject(err);
      }
    });
    child.on('close', (code, signal) => {
      cleanup();
      if (code === 0 || signal) resolve();  // signal => we killed it on purpose
      else reject(new Error(`espeak-ng exited with code ${code}`));
    });
    child.stdin.write(text);
    child.stdin.end();
  });
}

module.exports = { speak };
