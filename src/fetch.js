const { firefox } = require('playwright');

// Load a URL in headless Firefox, wait for JS to settle, return rendered HTML.
async function fetchHtml(url, { timeout = 30000 } = {}) {
  const browser = await firefox.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout });
    return await page.content();
  } finally {
    await browser.close();
  }
}

module.exports = { fetchHtml };
