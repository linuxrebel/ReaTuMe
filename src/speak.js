const { spawn } = require('child_process');

// Speak text aloud via espeak-ng. Optionally also save WAV to outFile.
// Resolves when playback finishes.
function speak(text, { speed, voice, outFile } = {}) {
  const args = [];
  if (speed) args.push('-s', String(speed));
  if (voice) args.push('-v', voice);
  if (outFile) args.push('-w', outFile);

  return new Promise((resolve, reject) => {
    const child = spawn('espeak-ng', args, { stdio: ['pipe', 'inherit', 'inherit'] });
    child.on('error', (err) => {
      if (err.code === 'ENOENT') {
        reject(new Error('espeak-ng not found. Install it (e.g. dnf install espeak-ng).'));
      } else {
        reject(err);
      }
    });
    child.on('close', (code) => {
      code === 0 ? resolve() : reject(new Error(`espeak-ng exited with code ${code}`));
    });
    child.stdin.write(text);
    child.stdin.end();
  });
}

module.exports = { speak };
