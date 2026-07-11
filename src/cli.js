const { program } = require('commander');
const { fetchHtml } = require('./fetch');
const { extract } = require('./extract');
const { speak } = require('./speak');

async function run() {
  program
    .name('reatume')
    .description('Navigate to a URL, extract the article, and read it aloud.')
    .argument('<url>', 'page URL to read')
    .option('-s, --speed <wpm>', 'words per minute', (v) => parseInt(v, 10))
    .option('-v, --voice <name>', 'espeak-ng voice (e.g. en-us)')
    .option('-e, --engine <name>', 'TTS engine: espeak (default) or piper', 'espeak')
    .option('-m, --model <path>', 'Piper voice model .onnx path (engine=piper)')
    .option('-g, --gap <n>', 'word gap in 10ms units', (v) => parseInt(v, 10))
    .option('-o, --out <file>', 'also save spoken audio to a WAV file')
    .option('--timeout <ms>', 'page load timeout in ms', (v) => parseInt(v, 10), 30000)
    .parse();

  const url = program.args[0];
  const opts = program.opts();

  process.stderr.write(`Loading ${url} ...\n`);
  const html = await fetchHtml(url, { timeout: opts.timeout });
  const { title, text } = extract(html, url);

  if (!text) {
    throw new Error('No readable text found on the page.');
  }
  if (title) process.stderr.write(`Reading: ${title}\n`);

  await speak(text, { engine: opts.engine, voice: opts.voice, model: opts.model, speed: opts.speed, gap: opts.gap, outFile: opts.out });
}

module.exports = { run };
