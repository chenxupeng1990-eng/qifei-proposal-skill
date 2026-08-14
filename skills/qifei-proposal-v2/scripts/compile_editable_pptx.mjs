#!/usr/bin/env node
import {createHash} from 'node:crypto';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import pptxgen from 'pptxgenjs';

const args = process.argv.slice(2);
const projectArg = args[0];
if (!projectArg) {
  console.error('Usage: node scripts/compile_editable_pptx.mjs <project> [--manifest deck/editable-layout/editable-layout-manifest.json] [--out exports/proposal-editable.pptx]');
  process.exit(2);
}
const valueAfter = flag => {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : null;
};
const project = path.resolve(projectArg);
const manifestPath = path.resolve(project, valueAfter('--manifest') || 'deck/editable-layout/editable-layout-manifest.json');
const out = path.resolve(project, valueAfter('--out') || 'exports/proposal-editable.pptx');
if (!existsSync(manifestPath)) throw new Error(`Manifest not found: ${manifestPath}`);
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const pxToIn = px => Number(px) / 144;
// The HTML review canvas is 1920 px wide and maps to a 13.333 in slide.
// Therefore its effective scale is 144 px/in, or 0.5 PowerPoint pt/px.
const pxToPt = px => Number(px) * 72 / 144;
const hex = rgb => rgb.map(value => Math.max(0, Math.min(255, value)).toString(16).padStart(2, '0')).join('').toUpperCase();
const sha256 = file => createHash('sha256').update(readFileSync(file)).digest('hex');
mkdirSync(path.dirname(out), {recursive:true});

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Company';
pptx.company = 'Company';
pptx.lang = 'zh-CN';
pptx.subject = 'Editable proposal compiled from measured HTML layout boxes';
pptx.defineSlideMaster({title:'COMPANY_EDITABLE', background:{color:'FFFFFF'}, objects:[]});
const report = {
  schema_version:'0.2',
  deck_id:manifest.deck_id || null,
  content_freeze_id:manifest.content_freeze_id || null,
  design_version:manifest.design_version || null,
  source_manifest:path.relative(project, manifestPath).replaceAll(path.sep, '/'),
  slides:[],
};

for (const page of manifest.slides || []) {
  const background = path.resolve(project, page.background);
  if (!existsSync(background) || sha256(background) !== page.background_sha256) {
    throw new Error(`Background missing or changed: ${page.slide_id}`);
  }
  const slide = pptx.addSlide('COMPANY_EDITABLE');
  slide.addImage({
    path:background, x:0, y:0, w:13.333333, h:7.5,
    objectName:`${page.slide_id}-approved-visual`,
    altText:`Approved visual background for ${page.slide_id}`,
  });
  for (const item of page.text || []) {
    const {box, style} = item;
    const content = Array.isArray(item.runs) && item.runs.length > 1
      ? item.runs.map(run => ({
          text:run.text,
          options:{
            fontFace:run.style?.fontFamily || style.fontFamily || 'Arial',
            fontSize:pxToPt(run.style?.fontSizePx || style.fontSizePx),
            bold:Number(run.style?.fontWeight ?? style.fontWeight) >= 600,
            italic:(run.style?.fontStyle || style.fontStyle) === 'italic',
            color:hex(run.style?.colorRgb || style.colorRgb || [0, 0, 0]),
          },
        }))
      : item.text;
    slide.addText(content, {
      x:pxToIn(box.x), y:pxToIn(box.y), w:pxToIn(box.width), h:pxToIn(box.height),
      fontFace:style.fontFamily || 'Arial', fontSize:pxToPt(style.fontSizePx),
      bold:Number(style.fontWeight) >= 600, italic:style.fontStyle === 'italic',
      color:hex(style.colorRgb || [0, 0, 0]), align:style.textAlign || 'left',
      valign:'top', margin:0, wrap:true,
      charSpacing:pxToPt(style.letterSpacingPx || 0),
      lineSpacingMultiple:style.lineHeightPx ? style.lineHeightPx / style.fontSizePx : undefined,
      objectName:item.id,
    });
  }
  slide.addNotes([
    `slide_id: ${page.slide_id}`,
    `content_freeze_id: ${manifest.content_freeze_id || ''}`,
    `approved_content_hash: ${page.approved_content_hash || ''}`,
    `speaker_doc_anchor: ${page.speaker_doc_anchor || ''}`,
    `source_manifest: ${report.source_manifest}`,
  ].join('\n'));
  report.slides.push({
    slide_id:page.slide_id,
    approved_content_hash:page.approved_content_hash || null,
    speaker_doc_anchor:page.speaker_doc_anchor || null,
    editable_text_objects:(page.text || []).length,
    background:page.background,
  });
}

await pptx.writeFile({fileName:out});
const reportPath = out.replace(/\.pptx$/i, '.report.json');
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
console.log(`Editable PPTX: ${out}`);
console.log(`Report: ${reportPath}`);
