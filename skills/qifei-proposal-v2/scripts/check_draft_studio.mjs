// Load a rendered draft-studio page in a headless browser and report what a reader would see.
import { existsSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const html = process.argv[2];
if (!html) {
  console.error('Usage: node scripts/check_draft_studio.mjs <draft-studio.html>');
  process.exit(2);
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
  ];
  return candidates.find(candidate => candidate && existsSync(candidate));
}

const executablePath = browserPath();
if (!executablePath) throw new Error('Chrome/Edge/Chromium not found. Set CHROME_PATH or EDGE_PATH.');

const browser = await chromium.launch({executablePath, headless:true});
try {
  const page = await browser.newPage({viewport:{width:1440, height:900}});
  const scriptErrors = [];
  page.on('pageerror', error => scriptErrors.push(String(error)));
  await page.goto(pathToFileURL(path.resolve(html)).href, {waitUntil:'load'});
  const report = await page.evaluate(() => {
    const visible = selector => [...document.querySelectorAll(selector)].filter(el => el.offsetParent !== null).length;
    const result = {
      title: document.getElementById('doc-title').textContent,
      chapters: document.querySelectorAll('[data-chapter]').length,
      slides: document.querySelectorAll('.slide').length,
      toc_links: document.querySelectorAll('.toc-slide').length,
      screens: document.querySelectorAll('.screen').length,
      views: {},
    };
    for (const view of ['full', 'client', 'chain']) {
      document.querySelector(`[data-view="${view}"]`).click();
      result.views[view] = {
        visual_fields: visible('.field-visual'),
        internal_fields: visible('details.internal'),
        screens: visible('.screen'),
      };
    }
    document.querySelector('[data-view="full"]').click();
    const markdown = JSON.parse(document.getElementById('markdown').textContent);
    result.markdown_bytes = {full: markdown.full.length, brief: markdown.brief.length};
    return result;
  });
  await page.fill('#search', report.title ? '\u0000no-such-text\u0000' : '');
  report.search_empty_state = await page.evaluate(() => !document.getElementById('empty').hidden);
  report.script_errors = scriptErrors;
  console.log(JSON.stringify(report, null, 2));
  process.exitCode = scriptErrors.length || !report.slides ? 1 : 0;
} finally {
  await browser.close();
}
