// Measure low-level layout slips on rendered pages: orphan last lines, text running out of
// its box or the canvas, text sitting on busy texture, and near-miss left edges.
// Usage: node scripts/check_page_layout.mjs <project> <page.html> [more.html ...] [--out reviews/visual/LAYOUT-CHECK.json]
// A page file may hold several `.slide-canvas[data-slide-id]` slides or be a single 1920×1080 page.
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const args = process.argv.slice(2);
const outIndex = args.indexOf('--out');
const outRelative = outIndex >= 0 ? args.splice(outIndex, 2)[1] : 'reviews/visual/LAYOUT-CHECK.json';
const [project, ...files] = args;
if (!project || !files.length) {
  console.error('Usage: node scripts/check_page_layout.mjs <project> <page.html> [...] [--out <report.json>]');
  process.exit(2);
}

// Thresholds: an orphan is a last line of at most 3 characters (punctuation not counted);
// texture is the mean neighbour-pixel luminance change under a text block with the text hidden.
const ORPHAN_MAX_CHARS = 3;
const TEXTURE_MAX_BUSY = 4;
const ALIGN_NEAR_MISS = [3, 14];

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
  ];
  return candidates.find(candidate => candidate && existsSync(candidate));
}

// Runs in the page: text blocks of one slide with their geometry.
function measure(rootSelector) {
  const root = rootSelector ? document.querySelector(rootSelector) : document.body;
  const canvas = root.getBoundingClientRect();
  const ignored = el => el.closest('[data-screen-ignore]');
  const blocks = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  for (let el = walker.currentNode; el; el = walker.nextNode()) {
    if (ignored(el)) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    const ownText = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    if (!ownText) continue;
    const range = document.createRange();
    range.selectNodeContents(el);
    const lines = [];
    for (const r of range.getClientRects()) {
      const last = lines[lines.length - 1];
      if (last && Math.abs(last.top - r.top) < r.height / 2) { last.right = Math.max(last.right, r.right); last.left = Math.min(last.left, r.left); }
      else lines.push({top: r.top, left: r.left, right: r.right, height: r.height});
    }
    const rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height) continue;
    // Characters on the last visual line, measured by walking text from the end.
    let lastLineChars = 0;
    if (lines.length > 1) {
      const lastTop = lines[lines.length - 1].top;
      const text = el.textContent;
      const node = [...el.childNodes].reverse().find(n => n.nodeType === 3 && n.textContent.trim());
      if (node) {
        const r = document.createRange();
        for (let i = node.textContent.length - 1; i >= 0; i -= 1) {
          r.setStart(node, i); r.setEnd(node, i + 1);
          const box = r.getClientRects()[0];
          if (!box || Math.abs(box.top - lastTop) > lines[lines.length - 1].height / 2) break;
          if (node.textContent[i].trim() && !/[，。、；：！？,.;:!?”’」）)]/.test(node.textContent[i])) lastLineChars += 1;
        }
      }
      void text;
    }
    const overflowX = el.scrollWidth - el.clientWidth > 2 && /hidden|clip/.test(style.overflow + style.overflowX);
    const overflowY = el.scrollHeight - el.clientHeight > 2 && /hidden|clip/.test(style.overflow + style.overflowY);
    blocks.push({
      text: ownText.slice(0, 40),
      x: rect.left - canvas.left, y: rect.top - canvas.top, w: rect.width, h: rect.height,
      lines: lines.length, lastLineChars,
      outsideCanvas: rect.left < canvas.left - 1 || rect.top < canvas.top - 1 || rect.right > canvas.right + 1 || rect.bottom > canvas.bottom + 1,
      clipped: overflowX || overflowY,
    });
  }
  return {width: canvas.width, height: canvas.height, blocks};
}

function setTextHidden({rootSelector, hidden}) {
  const root = rootSelector ? document.querySelector(rootSelector) : document.body;
  let style = document.getElementById('__layout_check_hide');
  if (!style) { style = document.createElement('style'); style.id = '__layout_check_hide'; document.head.append(style); }
  root.classList.toggle('__layout_check_hidden', hidden);
  style.textContent = '.__layout_check_hidden, .__layout_check_hidden * { color: transparent !important; text-shadow: none !important; }';
}

// Runs in the page: luminance standard deviation per block from a text-free screenshot.
async function textureStats({png, boxes, scale}) {
  const image = new Image();
  image.src = `data:image/png;base64,${png}`;
  await image.decode();
  const c = document.createElement('canvas');
  c.width = image.width; c.height = image.height;
  const ctx = c.getContext('2d', {willReadFrequently: true});
  ctx.drawImage(image, 0, 0);
  return boxes.map(b => {
    const x = Math.max(0, Math.floor(b.x * scale)), y = Math.max(0, Math.floor(b.y * scale));
    const w = Math.max(1, Math.min(c.width - x, Math.floor(b.w * scale))), h = Math.max(1, Math.min(c.height - y, Math.floor(b.h * scale)));
    const data = ctx.getImageData(x, y, w, h).data;
    // Local busyness: mean luminance change between neighbouring pixels (4px apart). A smooth
    // light falloff scores low even across a large box; stone grain, leaves and furniture score high.
    const lum = (px, py) => { const i = (py * w + px) * 4; return 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]; };
    let total = 0, n = 0;
    for (let py = 0; py + 4 < h; py += 4) {
      for (let px = 0; px + 4 < w; px += 4) {
        const l = lum(px, py);
        total += Math.abs(l - lum(px + 4, py)) + Math.abs(l - lum(px, py + 4));
        n += 2;
      }
    }
    return n ? total / n : 0;
  });
}

function problemsFor(slide, stds) {
  const problems = [];
  slide.blocks.forEach((b, i) => {
    if (b.lines > 1 && b.lastLineChars > 0 && b.lastLineChars <= ORPHAN_MAX_CHARS) problems.push(`孤字尾行：「${b.text}」最后一行只有 ${b.lastLineChars} 个字`);
    if (b.outsideCanvas) problems.push(`越界：「${b.text}」超出画布`);
    if (b.clipped) problems.push(`溢出：「${b.text}」超出所在容器被裁切`);
    if (stds[i] > TEXTURE_MAX_BUSY && !/^\d{1,3}$/.test(b.text))  // page numbers excepted
      problems.push(`压纹理：「${b.text}」下方底图纹理杂（${stds[i].toFixed(1)}），文字区不干净`);
  });
  const lefts = slide.blocks.map(b => Math.round(b.x));
  const seen = new Set();
  for (let i = 0; i < lefts.length; i += 1) {
    for (let j = i + 1; j < lefts.length; j += 1) {
      const d = Math.abs(lefts[i] - lefts[j]);
      const key = [Math.min(lefts[i], lefts[j]), Math.max(lefts[i], lefts[j])].join('-');
      if (d >= ALIGN_NEAR_MISS[0] && d <= ALIGN_NEAR_MISS[1] && !seen.has(key)) {
        seen.add(key);
        problems.push(`左缘没对齐：「${slide.blocks[i].text}」与「${slide.blocks[j].text}」相差 ${d}px`);
      }
    }
  }
  return problems;
}

const executablePath = browserPath();
if (!executablePath) throw new Error('Chrome/Edge/Chromium not found. Set CHROME_PATH or EDGE_PATH.');
const browser = await chromium.launch({executablePath, headless:true});
const report = {at: new Date().toISOString(), thresholds: {ORPHAN_MAX_CHARS, TEXTURE_MAX_BUSY, ALIGN_NEAR_MISS}, pages: {}};
try {
  const page = await browser.newPage({viewport:{width:1920, height:1080}, deviceScaleFactor:1});
  for (const file of files) {
    const full = path.isAbsolute(file) ? file : path.join(project, file);
    await page.goto(`${pathToFileURL(full).href}?export=1&review=1`, {waitUntil:'load'});
    await page.waitForFunction(() => window.__qifeiReady !== false, null, {timeout:30000}).catch(() => {});
    await page.evaluate(() => document.fonts && document.fonts.ready);
    const ids = await page.evaluate(() => [...document.querySelectorAll('.slide-canvas[data-slide-id], [data-slide-id].slide')].map(n => n.dataset.slideId));
    const targets = ids.length ? ids.map(id => ({id, selector: `[data-slide-id="${id}"]`})) : [{id: path.basename(file, path.extname(file)), selector: null}];
    for (const target of targets) {
      const slide = await page.evaluate(measure, target.selector);
      await page.evaluate(setTextHidden, {rootSelector: target.selector, hidden: true});
      const locator = target.selector ? page.locator(target.selector).first() : page;
      const shot = await locator.screenshot({type:'png', animations:'disabled'});
      await page.evaluate(setTextHidden, {rootSelector: target.selector, hidden: false});
      const stds = await page.evaluate(textureStats, {png: shot.toString('base64'), boxes: slide.blocks, scale: 1});
      report.pages[target.id] = {file, problems: problemsFor(slide, stds), blocks: slide.blocks.length};
    }
  }
} finally {
  await browser.close();
}
const out = path.isAbsolute(outRelative) ? outRelative : path.join(project, outRelative);
mkdirSync(path.dirname(out), {recursive:true});
writeFileSync(out, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
const total = Object.values(report.pages).reduce((n, p) => n + p.problems.length, 0);
for (const [id, p] of Object.entries(report.pages)) for (const problem of p.problems) console.log(`${id}: ${problem}`);
console.log(`${total ? 'FAIL' : 'PASS'}: ${Object.keys(report.pages).length} page(s), ${total} layout problem(s) → ${outRelative}`);
process.exit(total ? 1 : 0);
