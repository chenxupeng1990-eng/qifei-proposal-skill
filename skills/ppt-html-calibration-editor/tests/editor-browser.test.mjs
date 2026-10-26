import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
// playwright-core is only a devDependency here, so it is often absent (npm omit=dev, or an installed copy).
// Fall back to CODEX_NODE_MODULES, then to the copy qifei-proposal-v2 already installs next door.
let chromium;
const sibling = fileURLToPath(new URL('../../qifei-proposal-v2/node_modules/', import.meta.url));
for (const where of [null, process.env.CODEX_NODE_MODULES, sibling]) {
  if (where === undefined || (where !== null && !existsSync(join(where, 'playwright-core')))) continue;
  try {
    ({ chromium } = require(where === null ? 'playwright-core' : join(where, 'playwright-core')));
    break;
  } catch { /* try the next location */ }
}
if (!chromium) {
  throw new Error('playwright-core not found. Run `python3 scripts/bootstrap.py --suite v2` from the repository root, '
    + 'or set CODEX_NODE_MODULES to a node_modules folder that contains it.');
}
const root = fileURLToPath(new URL('../assets/browser-editor/', import.meta.url));
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.ttf': 'font/ttf' };
const server = createServer(async (req, res) => {
  try {
    const relative = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).replace(/^\/+/, '') || 'demo/index.html';
    const file = normalize(join(root, relative));
    if (!file.startsWith(root) || !(await stat(file)).isFile()) throw new Error('not found');
    res.writeHead(200, { 'content-type': mime[extname(file)] || 'application/octet-stream' });
    res.end(await readFile(file));
  } catch {
    res.writeHead(404); res.end('not found');
  }
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const { port } = server.address();
const base = `http://127.0.0.1:${port}/demo/index.html`;
const browserCandidates = [
  process.env.CHROME_PATH,
  process.env.EDGE_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  process.env.PROGRAMFILES && join(process.env.PROGRAMFILES, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  process.env.PROGRAMFILES && join(process.env.PROGRAMFILES, 'Google', 'Chrome', 'Application', 'chrome.exe'),
].filter(Boolean);
const executablePath = browserCandidates.find(existsSync);
if (!executablePath) throw new Error('Chrome/Edge/Chromium not found. Set CHROME_PATH or EDGE_PATH.');
const browser = await chromium.launch({ executablePath, headless: true });

try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto(base);
  assert.equal(await page.locator('.ppt-editor-root').count(), 1, 'dedicated auto review page should mount');

  await page.goto(`${base}?capture=demo-slide`);
  assert.equal(await page.locator('.ppt-editor-root').count(), 0, 'capture mode must stay clean even on auto review page');

  await page.goto(`${base}?edit=1&capture=demo-slide`);
  assert.equal(await page.locator('.ppt-editor-root').count(), 1, 'edit mode should mount');
  await page.locator('[data-edit-id="demo.title"]').dblclick();
  assert.equal(await page.locator('[data-edit-id="demo.title"]').getAttribute('contenteditable'), 'true');

  const exported = JSON.parse(await page.evaluate(() => window.__PPT_EDITOR__.exportJSON()));
  assert.equal(exported.elements['demo.title'].text, 'Double-click to edit this title');
  assert.equal('html' in exported.elements['demo.title'], false, 'new states must not export HTML');

  await page.goto(`${base}?capture=demo-slide`);
  await page.evaluate(() => {
    localStorage.setItem('ppt-editor:editor-demo:demo-slide:v1', JSON.stringify({
      schemaVersion: 1,
      documentId: 'editor-demo',
      slideId: 'demo-slide',
      elements: {
        'demo.title': { type: 'text', html: '<img src=x onerror="window.__unsafe=1">Legacy <b>text</b>', x: 110, y: 130, width: 900, height: 100, opacity: 1, zIndex: 1, fontSize: 72, fontWeight: 700, lineHeight: 1.12, color: 'rgb(6, 41, 87)', textAlign: 'left' }
      }
    }));
  });
  await page.goto(`${base}?edit=1&capture=demo-slide`);
  assert.equal(await page.evaluate(() => window.__unsafe || 0), 0, 'legacy imported markup must not execute');
  assert.match(await page.locator('[data-edit-id="demo.title"]').innerText(), /Legacy text/);
  console.log('PASS editor browser contract');
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
