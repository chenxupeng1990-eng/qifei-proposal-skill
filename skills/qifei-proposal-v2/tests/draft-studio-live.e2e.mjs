// Drive a running draft studio like a person would: edit a field, save, then watch an outside change arrive.
// Usage: node tests/draft-studio-live.e2e.mjs <studio-url> <draft-file> <slide-id> <field-key> <outside-slide-id>
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';

const [url, draftFile, slideId, fieldKey, outsideSlide] = process.argv.slice(2);
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

const report = {};
const browser = await chromium.launch({executablePath: browserPath, headless: true});
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('dialog', dialog => dialog.accept());
  await page.goto(url, {waitUntil: 'load'});
  await page.waitForSelector('#live-state');
  report.live_label = await page.textContent('#live-state');

  const button = `[data-edit="field"][data-slide="${slideId}"][data-key="${fieldKey}"]`;
  await page.locator(button).evaluate(el => el.scrollIntoView({block: 'center'}));
  await page.locator(button).click({force: true});
  await page.waitForSelector('.editor textarea');
  const marker = `端到端测试修改 ${Date.now()}`;
  await page.fill('.editor textarea', marker);
  await page.keyboard.press(process.platform === 'darwin' ? 'Meta+Enter' : 'Control+Enter');
  await page.waitForFunction(() => !document.querySelector('.editor'), undefined, {timeout: 10000});
  report.saved_in_file = readFileSync(draftFile, 'utf8').includes(marker);
  report.saved_in_page = await page.locator(`#slide-${slideId}`).innerText().then(text => text.includes(marker));
  report.status_after_save = await page.locator(`#slide-${slideId} .chip`).innerText();
  report.toast_after_save = await page.textContent('#toast');

  const outsideMarker = `（外部写入 ${Date.now()}）`;
  const text = readFileSync(draftFile, 'utf8');
  const heading = new RegExp(`^(#{1,4}\\s*\\[?${outsideSlide}\\]?\\s*[｜|]?\\s*.+)$`, 'm');
  writeFileSync(draftFile, text.replace(heading, `$1${outsideMarker}`), 'utf8');
  await page.waitForFunction(
    ([id, mark]) => (document.querySelector(`#slide-${id} .slide-title`)?.textContent || '').includes(mark),
    [outsideSlide, outsideMarker],
    {timeout: 10000},
  );
  report.outside_change_rendered = true;
  report.toast_after_outside = await page.textContent('#toast');
  report.revision_shown = await page.textContent('#doc-meta');
  report.script_errors = errors;
  console.log(JSON.stringify(report, null, 2));
  process.exitCode = errors.length || !report.saved_in_file ? 1 : 0;
} finally {
  await browser.close();
}
