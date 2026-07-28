#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

export function canonicalBuildMaterial(inputs, runtime, chapterId) {
  return canonicalJson({
    chapter_id: chapterId || null,
    inputs: inputs || {},
    runtime: runtime || {},
  });
}

export function buildId(inputs, runtime, chapterId) {
  return createHash('sha256')
    .update(canonicalBuildMaterial(inputs, runtime, chapterId), 'utf8')
    .digest('hex')
    .slice(0, 16);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const payload = JSON.parse(process.argv[2] || '{}');
  process.stdout.write(JSON.stringify({
    material: canonicalBuildMaterial(payload.inputs, payload.runtime, payload.chapter_id),
    build_id: buildId(payload.inputs, payload.runtime, payload.chapter_id),
  }));
}
