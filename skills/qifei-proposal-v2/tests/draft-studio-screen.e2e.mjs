// Open a rendered draft page and report what the "PPT上屏内容" field shows on each slide.
// Usage: node tests/draft-studio-screen.e2e.mjs <draft-studio.html>
import { existsSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const [html] = process.argv.slice(2);
const browserPath = [
  process.env.CHROME_PATH,
  process.env.EDGE_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'], 'Google', 'Chrome', 'Application', 'chrome.exe'),
  process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'], 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
].find(candidate => candidate && existsSync(candidate));
if (!browserPath) { console.error('Chrome not found'); process.exit(3); }

const browser = await chromium.launch({executablePath: browserPath, headless: true});
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(pathToFileURL(path.resolve(html)).href, {waitUntil: 'load'});
  const slides = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.slide')].map(slide => {
    const body = slide.querySelector('.field-screen .field-body');
    if (!body) return [slide.dataset.slideId, null];
    return [slide.dataset.slideId, {
      title: body.querySelector('.s-title')?.textContent ?? null,
      kv_rows: [...body.querySelectorAll('.s-row')].map(row => row.querySelector('.k').textContent),
      tables: [...body.querySelectorAll('table')].map(table => ({
        columns: table.querySelectorAll('thead th').length,
        rows: table.querySelectorAll('tbody tr').length,
        cells: [...table.querySelectorAll('tbody tr')].map(tr => tr.querySelectorAll('td').length),
      })),
      // Order of what the reader sees: bold captions, tables and plain lines, in sequence.
      sequence: [...body.querySelectorAll('.md > *')].map(el => el.tagName === 'TABLE' ? 'TABLE' : el.textContent.trim().slice(0, 12)),
    }];
  })));
  console.log(JSON.stringify({slides, script_errors: errors}));
} finally {
  await browser.close();
}
