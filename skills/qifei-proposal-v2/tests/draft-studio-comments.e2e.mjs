// Comment like a person would: select text, comment, see an agent reply arrive, resolve.
// Usage: node tests/draft-studio-comments.e2e.mjs <studio-url> <project> <slide-id> <field-key> <phrase>
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const [url, project, slideId, fieldKey, phrase] = process.argv.slice(2);
const studio = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'scripts', 'draft_studio.py');
const browserPath = [
  process.env.CHROME_PATH,
  process.env.EDGE_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
].find(candidate => candidate && existsSync(candidate));
if (!browserPath) { console.error('Chrome not found'); process.exit(3); }

const browser = await chromium.launch({executablePath: browserPath, headless: true});
const report = {};
try {
  const page = await browser.newPage({viewport: {width: 1600, height: 950}});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(url, {waitUntil: 'load'});
  await page.waitForSelector('#live-state');
  report.selected = await page.evaluate(([field, text]) => {
    const root = document.querySelector(`[data-field="${field}"]`);
    root.scrollIntoView({block: 'center'});
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const i = node.nodeValue.indexOf(text);
      if (i >= 0) {
        const range = document.createRange();
        range.setStart(node, i);
        range.setEnd(node, i + text.length);
        getSelection().removeAllRanges();
        getSelection().addRange(range);
        return true;
      }
    }
    return false;
  }, [`${slideId}:${fieldKey}`, phrase]);
  await page.waitForSelector('#sel-comment:not([hidden])', {timeout: 3000});
  await page.click('#sel-comment');
  await page.fill('.composer textarea', '口径要写清楚');
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+Enter' : 'Control+Enter');
  await page.waitForSelector('mark.cmt-mark[data-thread="C-0001"]', {timeout: 5000});
  report.highlight_text = await page.textContent('mark.cmt-mark[data-thread="C-0001"]');
  report.card_aligned = await page.evaluate(() => {
    const mark = document.querySelector('mark.cmt-mark[data-thread="C-0001"]').getBoundingClientRect();
    const card = document.querySelector('[data-card="C-0001"]').getBoundingClientRect();
    return Math.abs(mark.top - card.top) < 40 && card.left > mark.right;
  });
  const longReply = Array.from({length: 9}, (_, i) => `第 ${i + 1} 点：口径说明`).join('\n');
  execFileSync('python3', [studio, 'reply', project, 'C-0001', longReply]);
  await page.waitForFunction(() => document.querySelectorAll('[data-card="C-0001"] .msg').length === 2, undefined, {timeout: 5000});
  await page.click('[data-card="C-0001"] .card-quote');
  report.long_message_clamped = await page.textContent('[data-card="C-0001"] [data-msg-toggle]').catch(() => null);
  await page.click('[data-card="C-0001"] [data-msg-toggle]');
  report.long_message_expanded = await page.evaluate(() => document.querySelector('[data-card="C-0001"] .msg-text.full') !== null);
  report.agent_reply_shown = true;
  report.toast = await page.textContent('#toast');
  await page.click('[data-card="C-0001"] [data-card-status="resolved"]');
  await page.waitForSelector('mark.cmt-mark.resolved[data-thread="C-0001"]', {timeout: 5000});
  report.decision_kept_visible = await page.isVisible('[data-card="C-0001"].collapsed');
  await page.click('[data-card="C-0001"]');
  report.expanded_on_click = await page.isVisible('[data-card="C-0001"].active [data-card-collapse]');
  await page.click('[data-card="C-0001"] [data-card-collapse]');
  report.collapsed_by_button = await page.isVisible('[data-card="C-0001"].collapsed');
  await page.click('[data-card="C-0001"]');
  await page.keyboard.press('Escape');
  report.collapsed_by_escape = await page.isVisible('[data-card="C-0001"].collapsed');
  await page.click('[data-card="C-0001"]');
  await page.mouse.click(700, 120);
  report.collapsed_by_blank_click = await page.isVisible('[data-card="C-0001"].collapsed');
  report.header_rows = await page.evaluate(() => {
    const head = document.querySelector('.rail-row').getBoundingClientRect();
    return {height: Math.round(head.height), counts: document.getElementById('rail-counts').textContent};
  });
  report.decision_badge = await page.textContent(`#slide-${slideId} .cmt-count.done`);
  const threads = JSON.parse(execFileSync('python3', [studio, 'comments', project, '--json', '--all'], {encoding: 'utf8'}));
  report.status_in_file = threads[0].status;
  report.messages_in_file = threads[0].messages.map(m => m.author);
  report.script_errors = errors;
  console.log(JSON.stringify(report, null, 2));
  process.exitCode = errors.length ? 1 : 0;
} finally {
  await browser.close();
}
