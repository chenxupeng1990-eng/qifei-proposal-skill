#!/usr/bin/env node
import {createHash} from 'node:crypto';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright-core';

const args = process.argv.slice(2);
const projectArg = args[0];
if (!projectArg) {
  console.error('Usage: node scripts/capture_editable_layout.mjs <project> [--html deck/proposal.html] [--out deck/editable-layout]');
  process.exit(2);
}
const valueAfter = flag => {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : null;
};
const project = path.resolve(projectArg);
const html = path.resolve(project, valueAfter('--html') || 'deck/proposal.html');
const outDir = path.resolve(project, valueAfter('--out') || 'deck/editable-layout');
const backgroundsDir = path.join(outDir, 'backgrounds');
const manifestPath = path.join(outDir, 'editable-layout-manifest.json');
const deckSpecPath = path.join(project, 'deck', 'deck-spec.json');

function browserPath() {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.EDGE_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  ].filter(Boolean);
  return candidates.find(existsSync) || null;
}

const sha256 = file => createHash('sha256').update(readFileSync(file)).digest('hex');
const executablePath = browserPath();
if (!existsSync(html)) throw new Error(`HTML not found: ${html}`);
if (!executablePath) throw new Error('Chrome/Edge/Chromium not found. Set CHROME_PATH or EDGE_PATH.');
mkdirSync(backgroundsDir, {recursive:true});
const deckSpec = existsSync(deckSpecPath) ? JSON.parse(readFileSync(deckSpecPath, 'utf8')) : null;
const slideSpecs = new Map((deckSpec?.slides || []).map(slide => [slide.slide_id, slide]));

const browser = await chromium.launch({executablePath, headless:true});
try {
  const page = await browser.newPage({viewport:{width:1920, height:1080}, deviceScaleFactor:1});
  await page.goto(`${pathToFileURL(html).href}?export=1`, {waitUntil:'load'});
  await page.waitForFunction(() => window.__qifeiReady === true, null, {timeout:30000});
  const qa = await page.evaluate(() => window.__qifeiQa);
  if (!qa?.ok) throw new Error(`HTML QA failed: ${JSON.stringify(qa?.errors || [])}`);

  const slides = page.locator('.slide-canvas');
  const count = await slides.count();
  const manifest = {
    schema_version: '0.2',
    deck_id: deckSpec?.deck_id || null,
    content_freeze_id: deckSpec?.content_freeze_id || null,
    design_version: deckSpec?.design_version || null,
    source_deck_spec: existsSync(deckSpecPath) ? path.relative(project, deckSpecPath).replaceAll(path.sep, '/') : null,
    source_deck_spec_sha256: existsSync(deckSpecPath) ? sha256(deckSpecPath) : null,
    source_html: path.relative(project, html).replaceAll(path.sep, '/'),
    source_html_sha256: sha256(html),
    canvas: {width:1920, height:1080},
    slides: [],
  };
  const textSelector = [
    '.topline', 'h1', '.subtitle', '.body-text', '.bullet-list li',
    '.card .index', '.card h2', '.card p', '.metric .value', '.metric .label',
    '.step .index', '.step h2', '.step p', '.quote',
    '.page-footer .source', '.page-footer .slide-id',
  ].join(',');
  await page.addStyleTag({content:'.qifei-editable-text-mask{color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important;}'});

  for (let index = 0; index < count; index += 1) {
    const slide = slides.nth(index);
    const slideId = await slide.getAttribute('data-slide-id') || `slide-${index + 1}`;
    const safeId = slideId.replace(/[^A-Za-z0-9_-]+/g, '-');
    const text = await slide.locator(textSelector).evaluateAll((nodes, selector) => {
      const canvas = document.querySelector(`.slide-canvas[data-slide-id="${CSS.escape(selector.slideId)}"]`);
      const origin = canvas.getBoundingClientRect();
      const rgb = value => {
        const match = String(value).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
        return match ? match.slice(1, 4).map(Number) : [0, 0, 0];
      };
      return nodes.map((node, nodeIndex) => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        const range = document.createRange();
        range.selectNodeContents(node);
        const rangeRect = range.getBoundingClientRect();
        const contentLeft = rangeRect.width > 0 ? Math.max(rect.left, rangeRect.left) : rect.left;
        return {
          id: `${selector.slideId}-text-${String(nodeIndex + 1).padStart(2, '0')}`,
          text: node.textContent.trim(),
          box: {
            x:contentLeft-origin.left,
            y:rect.top-origin.top,
            width:Math.max(1, rect.right-contentLeft),
            height:rect.height,
          },
          style: {
            fontFamily: style.fontFamily.split(',')[0].replaceAll('"', '').trim(),
            fontSizePx: parseFloat(style.fontSize),
            fontWeight: parseInt(style.fontWeight, 10) || 400,
            fontStyle: style.fontStyle,
            colorRgb: rgb(style.color),
            lineHeightPx: style.lineHeight === 'normal' ? null : parseFloat(style.lineHeight),
            letterSpacingPx: style.letterSpacing === 'normal' ? 0 : parseFloat(style.letterSpacing),
            textAlign: ['center', 'right', 'justify'].includes(style.textAlign) ? style.textAlign : 'left',
          },
        };
      }).filter(item => item.text && item.box.width > 0 && item.box.height > 0);
    }, {slideId});

    await slide.evaluate((node, selector) => {
      node.querySelectorAll(selector).forEach(item => item.classList.add('qifei-editable-text-mask'));
    }, textSelector);
    const background = path.join(backgroundsDir, `${safeId}.png`);
    await slide.screenshot({path:background});
    await slide.evaluate(node => node.querySelectorAll('.qifei-editable-text-mask').forEach(item => item.classList.remove('qifei-editable-text-mask')));

    const slideSpec = slideSpecs.get(slideId) || null;
    manifest.slides.push({
      slide_id: slideId,
      layout: slideSpec?.layout || null,
      role: slideSpec?.role || null,
      approved_content_hash: slideSpec?.approved_content_hash || null,
      speaker_doc_anchor: slideSpec?.speaker_doc_anchor || null,
      background: path.relative(project, background).replaceAll(path.sep, '/'),
      background_sha256: sha256(background),
      text,
    });
  }
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  console.log(`Captured ${manifest.slides.length} editable-layout slide(s)`);
  console.log(`Manifest: ${manifestPath}`);
} finally {
  await browser.close();
}
