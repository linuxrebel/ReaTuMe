const { JSDOM } = require('jsdom');
const { Readability } = require('@mozilla/readability');

// Run Readability against rendered HTML, return { title, text }.
// Falls back to raw body text if Readability can't find an article.
function extract(html, url) {
  const dom = new JSDOM(html, { url });
  const article = new Readability(dom.window.document).parse();
  if (article && article.textContent.trim()) {
    return { title: article.title || '', text: article.textContent.trim() };
  }
  const body = dom.window.document.body;
  return { title: dom.window.document.title || '', text: body ? body.textContent.trim() : '' };
}

module.exports = { extract };
