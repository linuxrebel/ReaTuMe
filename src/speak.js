const { spawn } = require('child_process');

// Speak text aloud via espeak-ng. Optionally also save WAV to outFile.
// Resolves when playback finishes.
function speak(text, { speed, voice, gap, outFile } = {}) {
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
