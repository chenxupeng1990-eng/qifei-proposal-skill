#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const input = process.argv[2];
if (!input) {
  console.error('Usage: node validate_page_contracts.mjs <page-contracts.json>');
  process.exit(2);
}

const file = path.resolve(input);
const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
const pages = Array.isArray(parsed) ? parsed : parsed.pages;
if (!Array.isArray(pages) || pages.length === 0) {
  console.error('FAIL: expected a non-empty page contract array');
  process.exit(1);
}

const required = [
  'id',
  'audienceDecision',
  'audienceFacingCopyConfirmed',
  'priorPageQuestion',
  'conclusion',
  'causalStatement',
  'communicationObject',
  'primaryCarrier',
  'carrierMakesVisible',
  'visualHammer',
  'productRole',
  'image2ProductReferenceRequired',
  'htmlExactContent',
  'productionRoute',
  'failureMode',
  'nextPageQuestion',
];

const tests = ['removal', 'swap', 'thumbnail', 'narrative'];
const errors = [];
const seenIds = new Set();
const routes = new Set(['HTML', 'HTML + transparent PNG', 'Image2 + HTML', 'direct PNG + Cowart']);
const placeholderPattern = /\b(?:TBD|TODO|PLACEHOLDER|Lorem\s+ipsum)\b|待补充|待确认|占位|请替换|示例文案/i;
const internalCopyPattern = /本页展示|建议呈现|章节视觉|设计说明|页面任务/i;
const localPathPattern = /(?:^|[\s"'`(])(?:file:\/\/|data:|\/[Uu]sers\/|\/home\/|[A-Za-z]:[\\/])/;

function strings(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings);
  return [];
}

const communicationJob = Array.isArray(parsed) ? null : parsed.communicationJob;
for (const key of ['audience', 'outcome', 'centralTakeaway', 'statement']) {
  if (!communicationJob?.[key]) errors.push(`communicationJob: missing ${key}`);
}

for (const [index, page] of pages.entries()) {
  const label = page?.id || `index ${index}`;

  if (page?.id) {
    if (seenIds.has(page.id)) errors.push(`${label}: duplicate page id`);
    seenIds.add(page.id);
  }

  for (const key of required) {
    if (page?.[key] === undefined || page?.[key] === null || page?.[key] === '') {
      errors.push(`${label}: missing ${key}`);
    }
  }

  if (!routes.has(page?.productionRoute)) {
    errors.push(`${label}: productionRoute must be one of ${[...routes].join(', ')}`);
  }

  if (!Array.isArray(page?.htmlExactContent)) {
    errors.push(`${label}: htmlExactContent must be an array`);
  }

  if (!page?.htmlSkipReason) {
    errors.push(`${label}: missing htmlSkipReason`);
  }

  const visibleCopy = strings({
    audienceDecision: page?.audienceDecision,
    conclusion: page?.conclusion,
    causalStatement: page?.causalStatement,
    htmlExactContent: page?.htmlExactContent,
  });
  for (const value of visibleCopy) {
    if (placeholderPattern.test(value)) errors.push(`${label}: unresolved placeholder in audience-facing copy: ${JSON.stringify(value)}`);
    if (internalCopyPattern.test(value)) errors.push(`${label}: internal production language leaked into audience-facing copy: ${JSON.stringify(value)}`);
  }

  for (const value of strings(page)) {
    if (localPathPattern.test(value)) errors.push(`${label}: local or inline path leaked into page contract: ${JSON.stringify(value)}`);
  }

  const causal = String(page?.causalStatement || '');
  if (!(causal.includes('因为') && causal.includes('所以'))) {
    errors.push(`${label}: causalStatement must explicitly include “因为” and “所以”`);
  }

  for (const test of tests) {
    if (page?.qa?.[test] !== 'pass') {
      errors.push(`${label}: qa.${test} must be "pass" before generation`);
    }
  }

  if (page?.productRole !== 'none' && page?.image2ProductReferenceRequired !== true) {
    errors.push(`${label}: productRole=${page.productRole} requires image2ProductReferenceRequired=true`);
  }

  if (page?.audienceFacingCopyConfirmed !== true) {
    errors.push(`${label}: audienceFacingCopyConfirmed must be true`);
  }

  const imageRoutes = new Set(['HTML + transparent PNG', 'Image2 + HTML', 'direct PNG + Cowart']);
  if (imageRoutes.has(page?.productionRoute)) {
    const frame = page?.visualFrame;
    for (const key of ['aspectRatio', 'subjectPosition', 'protectedTextZone', 'cropTolerance', 'reuseAllowed']) {
      if (frame?.[key] === undefined || frame?.[key] === null || frame?.[key] === '') {
        errors.push(`${label}: visualFrame.${key} is required for ${page.productionRoute}`);
      }
    }
    if (frame?.aspectRatio !== '16:9') errors.push(`${label}: visualFrame.aspectRatio must be 16:9`);
  }

  const typography = page?.typography;
  if (!typography) {
    errors.push(`${label}: missing typography plan`);
  } else if (typography.templateControlled !== true) {
    if (Number(typography.titlePt) < 35) errors.push(`${label}: titlePt must be >=35 unless templateControlled=true`);
    if (Number(typography.midLevelPt) < 24) errors.push(`${label}: midLevelPt must be >=24 unless templateControlled=true`);
    if (Number(typography.bodyMinPt) < 16) errors.push(`${label}: bodyMinPt must be >=16 unless templateControlled=true`);
    if (!['single', 'multi'].includes(typography.titleLineIntent)) {
      errors.push(`${label}: typography.titleLineIntent must be single or multi`);
    }
  }

  const labels = page?.image2ExactSparseLabels || [];
  if (!Array.isArray(labels)) {
    errors.push(`${label}: image2ExactSparseLabels must be an array`);
  } else if (labels.length > 3) {
    errors.push(`${label}: Image2 sparse labels exceed the maximum of 3`);
  }
}

if (errors.length) {
  console.error(`FAIL: ${errors.length} page-contract violation(s)`);
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`PASS: ${pages.length} page contract(s) cleared for visual production`);
