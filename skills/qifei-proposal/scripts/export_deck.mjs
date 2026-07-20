#!/usr/bin/env node
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, unlinkSync, writeFileSync } from 'node:fs';
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
const ASSEMBLY_MANIFEST = path.join(PROJECT, 'deck', 'assembly-ready', 'manifest.json');
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
  for (const file of [HTML, MANIFEST, PROJECT_STATE, DECK_SPEC, ASSEMBLY_MANIFEST]) {
    if (!existsSync(file)) throw new Error(`Build guard missing required file: ${file}`);
  }
  const manifest = readJson(MANIFEST);
  const state = readJson(PROJECT_STATE);
  const deck = readJson(DECK_SPEC);
  const assembly = readJson(ASSEMBLY_MANIFEST);
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
  const owner = String(state.proposal_owner || '').trim();
  const finalApproval = assembly.final_assembly || {};
  const stateFinalApproval = state.approvals?.final_assembly || {};
  if (assembly.status !== 'final_approved' || state.assembly?.status !== 'final_approved') {
    throw new Error('Build guard requires every page to be confirmed before final assembly.');
  }
  if (finalApproval.approved !== true || stateFinalApproval.approved !== true || finalApproval.by !== owner || stateFinalApproval.by !== owner) {
    throw new Error('Build guard requires explicit Proposal Owner approval for final assembly.');
  }
  if (!finalApproval.record_id || finalApproval.record_id !== stateFinalApproval.record_id || finalApproval.record_id !== state.assembly?.final_approval_record_id) {
    throw new Error('Build guard detected mismatched final-assembly approval records.');
  }
  if (assembly.content_freeze_id !== state.content_freeze_id || assembly.design_version !== state.design_version) {
    throw new Error('Build guard detected stale assembly-ready content or design version.');
  }
  const deckSlides = Array.isArray(deck.slides) ? deck.slides : [];
  const readyPages = Array.isArray(assembly.pages) ? assembly.pages : [];
  const readyMap = new Map();
  for (const item of readyPages) {
    const slideId = String(item?.slide_id || '').trim();
    if (!slideId || readyMap.has(slideId)) throw new Error(`Build guard rejected missing or duplicate assembly slide id: ${slideId}`);
    readyMap.set(slideId, item);
  }
  if (!deckSlides.length || readyMap.size !== deckSlides.length) {
    throw new Error('Build guard requires every formal slide exactly once in the assembly-ready manifest.');
  }
  for (const slide of deckSlides) {
    const slideId = String(slide?.slide_id || '').trim();
    const ready = readyMap.get(slideId);
    if (!ready || ready.status !== 'ready') throw new Error(`Build guard: page is not assembly-ready: ${slideId}`);
    if (ready.approved_by !== owner || !ready.approval_record_id) throw new Error(`Build guard: page lacks explicit Owner approval: ${slideId}`);
    if (ready.content_freeze_id !== state.content_freeze_id || ready.design_version !== state.design_version) {
      throw new Error(`Build guard: page version is stale: ${slideId}`);
    }
    if (ready.approved_content_hash !== slide.approved_content_hash) {
      throw new Error(`Build guard: page content hash is stale: ${slideId}`);
    }
    if (typeof ready.ready_png_path !== 'string' || !ready.ready_png_path.startsWith('deck/assembly-ready/pages/')) {
      throw new Error(`Build guard: invalid approved PNG path for ${slideId}`);
    }
    const png = safeTrackedPath(PROJECT, ready.ready_png_path, `approved PNG ${slideId}`);
    if (!existsSync(png) || sha256(png) !== ready.ready_png_sha256) {
      throw new Error(`Build guard: approved PNG is missing or changed: ${slideId}`);
    }
  }
  return {manifest, deck, assembly};
}

const {manifest, deck, assembly} = verifyBuildFreshness();
console.log(`Build guard passed: ${manifest.build_id}`);

function browserPath() {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.EDGE_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
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
for (const file of readdirSync(PNG_DIR)) {
  if (file.toLowerCase().endsWith('.png')) unlinkSync(path.join(PNG_DIR, file));
}

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
  console.log('Browser QA passed. Assembling explicitly approved pages...');
  const slides = page.locator('.slide-canvas');
  const count = await slides.count();
  if (!count) throw new Error('No .slide-canvas elements found.');
  const ids = await slides.evaluateAll(nodes => nodes.map((node, index) => node.dataset.slideId || `slide-${index + 1}`));
  const deckIds = (deck.slides || []).map(item => String(item.slide_id || ''));
  if (JSON.stringify(ids) !== JSON.stringify(deckIds)) {
    throw new Error('Final HTML page order does not match deck-spec.json.');
  }
  const readyMap = new Map((assembly.pages || []).map(item => [String(item.slide_id), item]));
  const pngFiles = [];
  for (const slideId of ids) {
    const safeId = slideId.replace(/[^A-Za-z0-9_-]+/g, '-');
    const out = path.join(PNG_DIR, `${safeId}.png`);
    const ready = readyMap.get(slideId);
    const source = safeTrackedPath(PROJECT, ready.ready_png_path, `approved PNG ${slideId}`);
    copyFileSync(source, out);
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
