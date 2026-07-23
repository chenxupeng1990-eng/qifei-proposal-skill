#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const argv = process.argv.slice(2);
const projectArg = argv[0];
if (!projectArg) {
  console.error('Usage: node scripts/capture_review_pngs.mjs <project-directory> [--chapter-id <chapter-id>]');
  process.exit(1);
}
const chapterIndex = argv.indexOf('--chapter-id');
const chapterId = chapterIndex >= 0 ? String(argv[chapterIndex + 1] || '').trim() : '';
if (chapterIndex >= 0 && !chapterId) throw new Error('--chapter-id requires a value');

const PROJECT = path.resolve(projectArg);
const htmlRelative = chapterId ? `deck/chapters/${chapterId}.html` : 'deck/proposal.html';
const buildRelative = chapterId ? `deck/chapters/${chapterId}.build-manifest.json` : 'deck/build-manifest.json';
const HTML = path.join(PROJECT, ...htmlRelative.split('/'));
const BUILD_MANIFEST = path.join(PROJECT, ...buildRelative.split('/'));
const STATE = path.join(PROJECT, 'project-state.json');
const DECK = path.join(PROJECT, 'deck', 'deck-spec.json');
const outputKey = chapterId || 'full';
const OUTPUT_DIR = path.join(PROJECT, 'deck', 'review', outputKey);
const REVIEW_MANIFEST = path.join(OUTPUT_DIR, 'review-manifest.json');

function sha256(file) {
  return createHash('sha256').update(readFileSync(file)).digest('hex');
}

function readJson(file) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch (error) {
    throw new Error(`Invalid JSON ${file}: ${error.message}`);
  }
}

function safeTrackedPath(root, relative, label) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative)) {
    throw new Error(`Review guard rejected ${label}: invalid relative path ${JSON.stringify(relative)}`);
  }
  const resolvedRoot = path.resolve(root);
  const resolved = path.resolve(resolvedRoot, ...relative.split('/'));
  if (resolved !== resolvedRoot && !resolved.startsWith(`${resolvedRoot}${path.sep}`)) {
    throw new Error(`Review guard rejected ${label}: path escapes project (${relative})`);
  }
  return resolved;
}

function verifyReviewBuild() {
  for (const file of [HTML, BUILD_MANIFEST, STATE, DECK]) {
    if (!existsSync(file)) throw new Error(`Review guard missing required file: ${file}`);
  }
  const build = readJson(BUILD_MANIFEST);
  const state = readJson(STATE);
  const deck = readJson(DECK);
  if (build.output !== htmlRelative || !build.output_sha256 || sha256(HTML) !== build.output_sha256) {
    throw new Error('Review HTML is edited or stale; rerun render_deck.py.');
  }
  for (const [relative, expected] of Object.entries(build.inputs || {})) {
    const file = safeTrackedPath(PROJECT, relative, `input ${relative}`);
    if (!existsSync(file) || sha256(file) !== expected) {
      throw new Error(`Review guard detected changed or missing input: ${relative}; rerun render_deck.py.`);
    }
  }
  if (!state.content_freeze_id || build.content_freeze_id !== state.content_freeze_id || deck.content_freeze_id !== state.content_freeze_id) {
    throw new Error('Review guard detected content-freeze drift.');
  }
  if (build.design_version !== state.design_version || deck.design_version !== state.design_version) {
    throw new Error('Review guard detected design-version drift.');
  }
  if (!['generation', 'review', 'qa'].includes(state.phase)) {
    throw new Error(`Review PNGs require generation, review, or qa phase; current phase is ${state.phase}.`);
  }
  return {build, state};
}

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
    process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'], 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'], 'Google', 'Chrome', 'Application', 'chrome.exe'),
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ].filter(Boolean);
  return candidates.find(existsSync) || null;
}

const {build, state} = verifyReviewBuild();
const executablePath = browserPath();
if (!executablePath) throw new Error('Chrome/Edge/Chromium not found. Set CHROME_PATH or EDGE_PATH.');
mkdirSync(OUTPUT_DIR, {recursive:true});

const browser = await chromium.launch({executablePath, headless:true});
try {
  const page = await browser.newPage({viewport:{width:1920,height:1080}, deviceScaleFactor:1});
  await page.goto(`${pathToFileURL(HTML).href}?review=1`, {waitUntil:'load'});
  await page.waitForFunction(() => window.__qifeiReady === true, null, {timeout:30000});
  const qa = await page.evaluate(() => window.__qifeiQa);
  if (!qa?.ok) throw new Error(`Browser QA failed: ${JSON.stringify(qa?.errors || [])}`);
  if (qa.build_id !== build.build_id) throw new Error('Browser build id does not match the review build manifest.');

  const slides = page.locator('.slide-canvas');
  const count = await slides.count();
  if (!count) throw new Error('No .slide-canvas elements found.');
  const ids = await slides.evaluateAll(nodes => nodes.map((node, index) => node.dataset.slideId || `slide-${index + 1}`));
  const pages = [];
  for (let index = 0; index < count; index += 1) {
    const slideId = ids[index];
    const safeId = slideId.replace(/[^A-Za-z0-9_-]+/g, '-');
    const out = path.join(OUTPUT_DIR, `${safeId}.png`);
    await slides.nth(index).screenshot({path:out, type:'png', animations:'disabled'});
    pages.push({
      slide_id: slideId,
      png_path: path.relative(PROJECT, out).replaceAll('\\', '/'),
      png_sha256: sha256(out),
    });
  }
  const review = {
    schema_version: '1.0',
    project_id: state.project_id,
    created_at: new Date().toISOString(),
    chapter_id: chapterId || null,
    build_id: build.build_id,
    content_freeze_id: build.content_freeze_id,
    design_version: build.design_version,
    html_path: htmlRelative,
    html_sha256: sha256(HTML),
    build_manifest_path: buildRelative,
    build_manifest_sha256: sha256(BUILD_MANIFEST),
    pages,
  };
  writeFileSync(REVIEW_MANIFEST, `${JSON.stringify(review, null, 2)}\n`, 'utf8');
  console.log(`Captured ${count} review PNG(s) without generating PDF/PPT.`);
  console.log(`HTML: ${htmlRelative}`);
  console.log(`Review manifest: ${path.relative(PROJECT, REVIEW_MANIFEST).replaceAll('\\', '/')}`);
} finally {
  await browser.close();
}
