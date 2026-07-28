#!/usr/bin/env node
import {createHash} from 'node:crypto';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import JSZip from 'jszip';

const args = process.argv.slice(2);
const projectArg = args[0];
if (!projectArg) {
  console.error('Usage: node scripts/validate_editable_pptx.mjs <project> [--pptx exports/proposal-editable.pptx] [--manifest deck/editable-layout/editable-layout-manifest.json]');
  process.exit(2);
}
const valueAfter = flag => {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : null;
};
const project = path.resolve(projectArg);
const pptxPath = path.resolve(project, valueAfter('--pptx') || 'exports/proposal-editable.pptx');
const manifestPath = path.resolve(project, valueAfter('--manifest') || 'deck/editable-layout/editable-layout-manifest.json');
const deckSpecPath = path.join(project, 'deck', 'deck-spec.json');
for (const file of [pptxPath, manifestPath, deckSpecPath]) {
  if (!existsSync(file)) throw new Error(`Required file not found: ${file}`);
}

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const deckSpec = JSON.parse(readFileSync(deckSpecPath, 'utf8'));
const zip = await JSZip.loadAsync(readFileSync(pptxPath));
const sha256 = file => createHash('sha256').update(readFileSync(file)).digest('hex');
const decodeXml = value => String(value)
  .replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&quot;', '"')
  .replaceAll('&apos;', "'").replaceAll('&amp;', '&');
const normalize = value => String(value).replace(/\s+/g, ' ').trim();
const textFromXml = xml => [...String(xml).matchAll(/<a:t[^>]*>([\s\S]*?)<\/a:t>/g)]
  .map(match => decodeXml(match[1])).join('');
const emuToPx = emu => Number(emu) / 914400 * 144;

function collectFrozenStrings(slide) {
  const values = [];
  for (const key of ['kicker', 'title', 'subtitle']) {
    if (typeof slide[key] === 'string' && slide[key].trim()) values.push(slide[key]);
  }
  const walk = value => {
    if (typeof value === 'string') {
      if (value.trim()) values.push(value);
      return;
    }
    if (Array.isArray(value)) return value.forEach(walk);
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      if (['type', 'src', 'alt', 'position', 'evidence_ids'].includes(key)) continue;
      walk(child);
    }
  };
  walk(slide.blocks || []);
  return [...new Set(values.map(normalize).filter(Boolean))];
}

function editableShapes(xml) {
  const result = new Map();
  for (const match of String(xml).matchAll(/<p:sp>([\s\S]*?)<\/p:sp>/g)) {
    const block = match[1];
    const name = block.match(/<p:cNvPr[^>]*\bname="([^"]+)"/)?.[1];
    const box = block.match(/<a:xfrm>[\s\S]*?<a:off x="(\d+)" y="(\d+)"\/>[\s\S]*?<a:ext cx="(\d+)" cy="(\d+)"\/>/);
    if (!name || !box) continue;
    result.set(name, {
      x:emuToPx(box[1]), y:emuToPx(box[2]), width:emuToPx(box[3]), height:emuToPx(box[4]),
      text:normalize(textFromXml(block)),
    });
  }
  return result;
}

const failures = [];
const pages = [];
if (manifest.source_deck_spec_sha256 && manifest.source_deck_spec_sha256 !== sha256(deckSpecPath)) {
  failures.push('editable manifest is stale: deck-spec hash changed');
}
const sourceHtmlPath = manifest.source_html ? path.resolve(project, manifest.source_html) : null;
if (!sourceHtmlPath || !existsSync(sourceHtmlPath) || manifest.source_html_sha256 !== sha256(sourceHtmlPath)) {
  failures.push('editable manifest is stale: source HTML missing or changed');
}
for (const key of ['deck_id', 'content_freeze_id', 'design_version']) {
  if ((manifest[key] || null) !== (deckSpec[key] || null)) failures.push(`${key} mismatch between manifest and deck-spec`);
}
if ((manifest.slides || []).length !== (deckSpec.slides || []).length) {
  failures.push(`slide count mismatch: manifest=${manifest.slides?.length || 0}, deck-spec=${deckSpec.slides?.length || 0}`);
}
for (let index = 0; index < (manifest.slides || []).length; index += 1) {
  const page = manifest.slides[index];
  const spec = (deckSpec.slides || []).find(item => item.slide_id === page.slide_id);
  const slideXml = await zip.file(`ppt/slides/slide${index + 1}.xml`)?.async('string');
  const notesXml = await zip.file(`ppt/notesSlides/notesSlide${index + 1}.xml`)?.async('string');
  if (!slideXml || !notesXml || !spec) {
    failures.push(`${page.slide_id}: slide XML, notes XML, or deck-spec entry missing`);
    continue;
  }
  if ((page.approved_content_hash || null) !== (spec.approved_content_hash || null)) {
    failures.push(`${page.slide_id}: approved content hash mismatch`);
  }
  const slideText = normalize(textFromXml(slideXml));
  const noteText = normalize(textFromXml(notesXml));
  const missingFrozen = collectFrozenStrings(spec).filter(value => !slideText.includes(value));
  missingFrozen.forEach(value => failures.push(`${page.slide_id}: frozen text missing: ${value}`));
  for (const requiredNote of [
    `slide_id: ${page.slide_id}`,
    `content_freeze_id: ${manifest.content_freeze_id || ''}`,
    `approved_content_hash: ${page.approved_content_hash || ''}`,
    `speaker_doc_anchor: ${page.speaker_doc_anchor || ''}`,
  ]) {
    if (!noteText.includes(normalize(requiredNote))) failures.push(`${page.slide_id}: note metadata missing: ${requiredNote}`);
  }
  const shapes = editableShapes(slideXml);
  let maxDeltaPx = 0;
  for (const item of page.text || []) {
    const shape = shapes.get(item.id);
    if (!shape) {
      failures.push(`${page.slide_id}: editable shape missing: ${item.id}`);
      continue;
    }
    if (shape.text !== normalize(item.text)) failures.push(`${page.slide_id}: editable text changed: ${item.id}`);
    const delta = Math.max(
      Math.abs(shape.x - item.box.x), Math.abs(shape.y - item.box.y),
      Math.abs(shape.width - item.box.width), Math.abs(shape.height - item.box.height),
    );
    maxDeltaPx = Math.max(maxDeltaPx, delta);
    if (delta > 0.6) failures.push(`${page.slide_id}: layout delta > 0.6px for ${item.id}: ${delta.toFixed(3)}px`);
  }
  pages.push({slide_id:page.slide_id, frozen_fields:collectFrozenStrings(spec).length, editable_text_objects:(page.text || []).length, max_layout_delta_px:Number(maxDeltaPx.toFixed(3))});
}

for (const [name, entry] of Object.entries(zip.files)) {
  if (!/\.(xml|rels)$/i.test(name) || entry.dir) continue;
  const value = await entry.async('string');
  if (/(?:file:\/\/|\/Users\/|\/home\/|[A-Za-z]:\\)/.test(value)) {
    failures.push(`local filesystem path leaked into PPTX package: ${name}`);
  }
}

const report = {
  schema_version:'0.1',
  status:failures.length ? 'FAIL' : 'PASS',
  pptx:path.relative(project, pptxPath).replaceAll(path.sep, '/'),
  manifest:path.relative(project, manifestPath).replaceAll(path.sep, '/'),
  pages,
  failures,
};
const reportPath = pptxPath.replace(/\.pptx$/i, '.validation.json');
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
console.log(`${report.status}: ${pages.length} slide(s), ${failures.length} failure(s)`);
console.log(`Report: ${reportPath}`);
if (failures.length) {
  failures.slice(0, 20).forEach(item => console.error(`- ${item}`));
  process.exit(1);
}
