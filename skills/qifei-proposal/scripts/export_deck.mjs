#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';
import { PDFDocument } from 'pdf-lib';
import pptxgen from 'pptxgenjs';

const projectArg = process.argv[2];
if (!projectArg) {
  console.error('Usage: node scripts/export_deck.mjs <project-directory>');
  process.exit(1);
}
const PROJECT = path.resolve(projectArg);
const SKILL_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const HTML = path.join(PROJECT, 'deck', 'proposal.html');
const MANIFEST = path.join(PROJECT, 'deck', 'build-manifest.json');
const PROJECT_STATE = path.join(PROJECT, 'project-state.json');
const DECK_SPEC = path.join(PROJECT, 'deck', 'deck-spec.json');
const PNG_DIR = path.join(PROJECT, 'exports', 'png');
const PDF_OUT = path.join(PROJECT, 'exports', 'proposal.pdf');
const PPTX_OUT = path.join(PROJECT, 'exports', 'proposal-preview.pptx');

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

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function safeTrackedPath(root, relative, label) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative)) {
    throw new Error(`Build guard rejected ${label}: invalid relative path ${JSON.stringify(relative)}`);
  }
  const resolvedRoot = path.resolve(root);
  const resolved = path.resolve(resolvedRoot, ...relative.split('/'));
  if (resolved !== resolvedRoot && !resolved.startsWith(`${resolvedRoot}${path.sep}`)) {
    throw new Error(`Build guard rejected ${label}: path escapes its root (${relative})`);
  }
  return resolved;
}

function verifyBuildFreshness() {
  for (const file of [HTML, MANIFEST, PROJECT_STATE, DECK_SPEC]) {
    if (!existsSync(file)) throw new Error(`Build guard missing required file: ${file}`);
  }
  const manifest = readJson(MANIFEST);
  const state = readJson(PROJECT_STATE);
  const deck = readJson(DECK_SPEC);
  if (manifest.output !== 'deck/proposal.html') {
    throw new Error(`Build guard rejected unexpected output: ${manifest.output}`);
  }
  if (!manifest.output_sha256 || sha256(HTML) !== manifest.output_sha256) {
    throw new Error('Build guard detected edited or stale proposal.html; rerun render_deck.py.');
  }
  for (const [relative, expected] of Object.entries(manifest.inputs || {})) {
    const file = safeTrackedPath(PROJECT, relative, `input ${relative}`);
    if (!existsSync(file) || sha256(file) !== expected) {
      throw new Error(`Build guard detected changed or missing input: ${relative}; rerun render_deck.py.`);
    }
  }
  for (const [key, expected] of Object.entries(manifest.runtime || {})) {
    if (!key.startsWith('skill:')) throw new Error(`Build guard rejected runtime key: ${key}`);
    const relative = key.slice('skill:'.length);
    const file = safeTrackedPath(SKILL_ROOT, relative, `runtime ${relative}`);
    if (!existsSync(file) || sha256(file) !== expected) {
      throw new Error(`Build guard detected changed or missing runtime: ${relative}; rerun render_deck.py.`);
    }
  }
  const buildMaterial = canonicalJson({inputs:manifest.inputs || {}, runtime:manifest.runtime || {}});
  const expectedBuildId = createHash('sha256').update(buildMaterial, 'utf8').digest('hex').slice(0, 16);
  if (manifest.build_id !== expectedBuildId) {
    throw new Error('Build guard detected an invalid build id; rerun render_deck.py.');
  }
  if (!state.content_freeze_id || state.content_freeze_id !== manifest.content_freeze_id || deck.content_freeze_id !== manifest.content_freeze_id) {
    throw new Error('Build guard detected content-freeze drift between project state, deck spec, and manifest.');
  }
  if (state.design_version !== manifest.design_version || deck.design_version !== manifest.design_version) {
    throw new Error('Build guard detected design-version drift between project state, deck spec, and manifest.');
  }
  if (state.phase !== 'export') throw new Error(`Build guard requires project phase export; current phase is ${state.phase}.`);
  if (state.approvals?.content_freeze?.approved !== true || state.approvals.content_freeze.record_id !== state.content_freeze_id) {
    throw new Error('Build guard requires a matching approved content-freeze record.');
  }
  if (state.approvals?.content_qa?.approved !== true || state.approvals?.visual_qa?.approved !== true) {
    throw new Error('Build guard requires approved content QA and visual QA.');
  }
  return manifest;
}

const manifest = verifyBuildFreshness();
console.log(`Build guard passed: ${manifest.build_id}`);

function browserPath() {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.EDGE_PATH,
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ].filter(Boolean);
  return candidates.find(existsSync) || null;
}

const executablePath = browserPath();
if (!executablePath) throw new Error('Chrome/Edge/Chromium not found. Set CHROME_PATH or EDGE_PATH.');
console.log(`Browser: ${executablePath}`);
console.log(`HTML: ${HTML}`);
mkdirSync(PNG_DIR, {recursive:true});
mkdirSync(path.dirname(PDF_OUT), {recursive:true});

console.log('Launching browser...');
const browser = await chromium.launch({executablePath, headless:true});
try {
  console.log('Opening export page...');
  const page = await browser.newPage({viewport:{width:1920,height:1080}, deviceScaleFactor:1});
  page.on('console', message => console.log(`[browser:${message.type()}] ${message.text()}`));
  page.on('pageerror', error => console.error(`[browser:error] ${error.stack || error.message}`));
  await page.goto(`${pathToFileURL(HTML).href}?export=1`, {waitUntil:'load'});
  console.log('Waiting for deck readiness...');
  await page.waitForFunction(() => window.__qifeiReady === true, null, {timeout:30000});
  const qa = await page.evaluate(() => window.__qifeiQa);
  if (!qa?.ok) throw new Error(`Browser QA failed: ${JSON.stringify(qa?.errors || [])}`);
  if (qa.build_id !== manifest.build_id) {
    throw new Error(`Browser build id ${qa.build_id} does not match manifest ${manifest.build_id}.`);
  }
  console.log('Browser QA passed. Capturing slides...');
  const slides = page.locator('.slide-canvas');
  const count = await slides.count();
  if (!count) throw new Error('No .slide-canvas elements found.');
  const ids = await slides.evaluateAll(nodes => nodes.map((node, index) => node.dataset.slideId || `slide-${index + 1}`));
  const pngFiles = [];
  for (let index = 0; index < count; index += 1) {
    const safeId = ids[index].replace(/[^A-Za-z0-9_-]+/g, '-');
    const out = path.join(PNG_DIR, `${safeId}.png`);
    await slides.nth(index).screenshot({path:out, type:'png', animations:'disabled'});
    pngFiles.push(out);
  }

  const pdf = await PDFDocument.create();
  for (const file of pngFiles) {
    const image = await pdf.embedPng(readFileSync(file));
    const pdfPage = pdf.addPage([960, 540]);
    pdfPage.drawImage(image, {x:0, y:0, width:960, height:540});
  }
  writeFileSync(PDF_OUT, await pdf.save());

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_WIDE';
  pptx.author = 'QIFEI';
  pptx.subject = 'Image-based proposal preview generated from the HTML visual master';
  pptx.title = path.basename(PROJECT);
  pptx.company = 'QIFEI';
  pptx.lang = 'zh-CN';
  pptx.defineSlideMaster({title:'QIFEI_MASTER', background:{color:'000000'}, objects:[]});
  for (const file of pngFiles) {
    const slide = pptx.addSlide('QIFEI_MASTER');
    slide.addImage({path:file, x:0, y:0, w:13.333333, h:7.5});
  }
  await pptx.writeFile({fileName:PPTX_OUT});

  console.log(`Exported ${count} slide(s)`);
  console.log(`PNG: ${PNG_DIR}`);
  console.log(`PDF: ${PDF_OUT}`);
  console.log(`PPTX: ${PPTX_OUT}`);
} finally {
  await browser.close();
}
