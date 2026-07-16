#!/usr/bin/env node
import { createServer } from 'node:http';
import { createReadStream, existsSync, mkdirSync, readFileSync, renameSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const projectArg = process.argv[2];
if (!projectArg) {
  console.error('Usage: node scripts/serve_review.mjs <project-directory> [port]');
  process.exit(1);
}
const PROJECT = path.resolve(projectArg);
const PORT = Number(process.argv[3] || process.env.QIFEI_REVIEW_PORT || 4179);
const HOST = '127.0.0.1';
const COMMENTS = path.join(PROJECT, 'reviews', 'review-comments.json');

if (!existsSync(path.join(PROJECT, 'deck', 'proposal.html'))) {
  console.error('Missing deck/proposal.html; run render_deck.py first.');
  process.exit(1);
}

const contentTypes = {
  '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml',
};

function sendJson(res, status, value) {
  res.writeHead(status, {'content-type':'application/json; charset=utf-8', 'cache-control':'no-store'});
  res.end(JSON.stringify(value));
}

function validComments(value) {
  if (!value || typeof value !== 'object' || !Array.isArray(value.comments)) return false;
  if (value.comments.length > 5000) return false;
  return value.comments.every(item => item && typeof item === 'object'
    && typeof item.comment_id === 'string' && typeof item.slide_id === 'string'
    && typeof item.author === 'string' && typeof item.body === 'string'
    && ['open','resolved'].includes(item.status));
}

function readBody(req, maxBytes = 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = []; let total = 0;
    req.on('data', chunk => { total += chunk.length; if (total > maxBytes) reject(new Error('Payload too large')); else chunks.push(chunk); });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function atomicWrite(file, content) {
  mkdirSync(path.dirname(file), {recursive:true});
  const temp = path.join(path.dirname(file), `.${path.basename(file)}.tmp-${process.pid}-${Date.now()}`);
  writeFileSync(temp, content);
  renameSync(temp, file);
}

function requestIsLocal(req) {
  const host = String(req.headers.host || '').toLowerCase();
  if (!host.startsWith(`127.0.0.1:${PORT}`) && !host.startsWith(`localhost:${PORT}`)) return false;
  const origin = req.headers.origin;
  if (!origin) return true;
  return origin === `http://127.0.0.1:${PORT}` || origin === `http://localhost:${PORT}`;
}

function safeFile(urlPath) {
  const decoded = decodeURIComponent(urlPath).replace(/^\/+/, '');
  const relative = decoded || 'deck/proposal.html';
  const target = path.resolve(PROJECT, relative);
  const rel = path.relative(PROJECT, target);
  if (rel.startsWith('..') || path.isAbsolute(rel)) return null;
  return target;
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || '/', `http://${req.headers.host || `${HOST}:${PORT}`}`);
    if (url.pathname === '/api/review-comments') {
      if (!requestIsLocal(req)) return sendJson(res, 403, {error:'Local same-origin access only'});
      if (req.method === 'GET') {
        const value = existsSync(COMMENTS) ? JSON.parse(readFileSync(COMMENTS, 'utf8')) : {schema_version:'1.0', comments:[]};
        return sendJson(res, 200, value);
      }
      if (req.method === 'PUT') {
        const value = JSON.parse(await readBody(req));
        if (!validComments(value)) return sendJson(res, 400, {error:'Malformed review comments'});
        atomicWrite(COMMENTS, `${JSON.stringify(value, null, 2)}\n`);
        return sendJson(res, 200, {ok:true});
      }
      return sendJson(res, 405, {error:'Method not allowed'});
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') return sendJson(res, 405, {error:'Method not allowed'});
    const file = safeFile(url.pathname);
    if (!file || !existsSync(file) || !statSync(file).isFile()) return sendJson(res, 404, {error:'Not found'});
    res.writeHead(200, {'content-type':contentTypes[path.extname(file).toLowerCase()] || 'application/octet-stream', 'cache-control':'no-store'});
    if (req.method === 'HEAD') return res.end();
    createReadStream(file).pipe(res);
  } catch (error) {
    sendJson(res, 500, {error:String(error?.message || error)});
  }
});

server.listen(PORT, HOST, () => {
  console.log(`QIFEI review server: http://${HOST}:${PORT}/deck/proposal.html`);
  console.log(`Project: ${PROJECT}`);
});
