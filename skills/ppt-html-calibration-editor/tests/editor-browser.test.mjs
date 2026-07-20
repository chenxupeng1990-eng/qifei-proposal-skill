import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright-core'));
} catch {
  const bundled = process.env.CODEX_NODE_MODULES;
  if (!bundled) throw new Error('Install playwright-core or set CODEX_NODE_MODULES to its package directory');
  ({ chromium } = require(join(bundled, 'playwright-core')));
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
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });

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
