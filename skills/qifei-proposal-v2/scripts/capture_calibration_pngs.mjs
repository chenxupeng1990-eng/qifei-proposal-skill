#!/usr/bin/env node
// Capture each design calibration sample as a 1920x1080 PNG so the Owner can box-comment on it in
// the studio's design review page (/design), the same way as formal pages.
//
// Every element marked data-design-sample="<type>" in deck/design-calibration.html is one sample.
// Its review id is data-slide-id when present, otherwise CAL-<type>. Output goes to
// deck/review/calibration/, which the design review page reads with the other review manifests.
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const projectArg = process.argv[2];
if (!projectArg) {
  console.error('Usage: node scripts/capture_calibration_pngs.mjs <project-directory>');
  process.exit(1);
}
const PROJECT = path.resolve(projectArg);
const STATE = path.join(PROJECT, 'project-state.json');
const state = existsSync(STATE) ? JSON.parse(readFileSync(STATE, 'utf8')) : {};
const htmlRelative = (state.design_calibration && state.design_calibration.path) || 'deck/design-calibration.html';
const HTML = path.resolve(PROJECT, ...htmlRelative.split('/'));
if (!HTML.startsWith(`${PROJECT}${path.sep}`) || !existsSync(HTML)) throw new Error(`Calibration HTML not found: ${htmlRelative}`);
const OUTPUT_DIR = path.join(PROJECT, 'deck', 'review', 'calibration');
const sha256 = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');

function browserPath() {
  const env = process.env;
  return [
    env.CHROME_PATH, env.EDGE_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome', '/usr/bin/chromium',
    env.LOCALAPPDATA && path.join(env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    env.PROGRAMFILES && path.join(env.PROGRAMFILES, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    env.PROGRAMFILES && path.join(env.PROGRAMFILES, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ].filter(Boolean).find(existsSync) || null;
}

const executablePath = browserPath();
if (!executablePath) throw new Error('Chrome/Edge/Chromium not found. Set CHROME_PATH or EDGE_PATH.');
mkdirSync(OUTPUT_DIR, {recursive: true});
const browser = await chromium.launch({executablePath, headless: true});
try {
  const page = await browser.newPage({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1});
  await page.goto(pathToFileURL(HTML).href, {waitUntil: 'load'});
  await page.evaluate(() => document.fonts && document.fonts.ready);
  const samples = page.locator('[data-design-sample]');
  const count = await samples.count();
  if (!count) throw new Error('No [data-design-sample] elements found in the calibration HTML.');
  const pages = [];
  const seen = new Set();
  for (let index = 0; index < count; index += 1) {
    const sample = samples.nth(index);
    const meta = await sample.evaluate((node) => ({type: node.dataset.designSample, id: node.dataset.slideId || ''}));
    let slideId = meta.id || `CAL-${meta.type}`;
    while (seen.has(slideId)) slideId = `${slideId}-${index + 1}`;
    seen.add(slideId);
    const out = path.join(OUTPUT_DIR, `${slideId.replace(/[^A-Za-z0-9_-]+/g, '-')}.png`);
    await sample.scrollIntoViewIfNeeded();
    await sample.screenshot({path: out, type: 'png', animations: 'disabled'});
    // Text blocks with their boxes in 1920x1080 page pixels, so a comment can name the text under its box.
    const textBoxes = await sample.evaluate((node) => {
      const frame = node.getBoundingClientRect();
      const sx = 1920 / frame.width, sy = 1080 / frame.height;
      return [...node.querySelectorAll('*')]
        .filter((el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
        .map((el) => {
          const r = el.getBoundingClientRect();
          return {text: el.innerText.trim().slice(0, 120), selector: el.tagName.toLowerCase() + (el.classList[0] ? `.${el.classList[0]}` : ''),
                  x: (r.left - frame.left) * sx, y: (r.top - frame.top) * sy, w: r.width * sx, h: r.height * sy};
        })
        .filter((b) => b.w > 0 && b.h > 0);
    });
    pages.push({slide_id: slideId, sample_type: meta.type, png_path: path.relative(PROJECT, out).replaceAll('\\', '/'),
                png_sha256: sha256(out), text_boxes: textBoxes});
  }
  const manifest = {
    schema_version: '1.0',
    kind: 'design_calibration',
    project_id: state.project_id || null,
    created_at: new Date().toISOString(),
    html_path: htmlRelative,
    html_sha256: sha256(HTML),
    pages,
  };
  writeFileSync(path.join(OUTPUT_DIR, 'review-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  console.log(`Captured ${count} calibration sample(s) into deck/review/calibration/. Open the studio's /design page to comment.`);
} finally {
  await browser.close();
}
