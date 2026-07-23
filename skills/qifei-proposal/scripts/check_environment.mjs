import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SKILL_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const RUNTIME_ROOT = path.resolve(process.env.PROPOSAL_ENV_ROOT || SKILL_ROOT);
const results = [];

function record(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: ${detail}`);
}

const nodeMajor = Number(process.versions.node.split('.')[0]);
record('Node.js', nodeMajor >= 18, `${process.versions.node} (required >=18)`);

const npmCheck = spawnSync('npm', ['--version'], { encoding: 'utf8' });
record(
  'npm',
  npmCheck.status === 0,
  npmCheck.status === 0 ? npmCheck.stdout.trim() : 'not found or not executable',
);

const pythonCommands = process.platform === 'win32'
  ? [['py', ['-3', '--version']], ['python', ['--version']], ['python3', ['--version']]]
  : [['python3', ['--version']], ['python', ['--version']]];

let pythonVersion = '';
for (const [command, args] of pythonCommands) {
  const check = spawnSync(command, args, { encoding: 'utf8' });
  if (check.status === 0) {
    pythonVersion = `${command} ${(check.stdout || check.stderr).trim()}`;
    break;
  }
}

const pythonMatch = pythonVersion.match(/Python\s+(\d+)\.(\d+)/i);
const pythonOk = Boolean(pythonMatch) && (Number(pythonMatch[1]) > 3 || Number(pythonMatch[2]) >= 9);
record('Python', pythonOk, pythonVersion || 'not found (required >=3.9)');

const nodeModules = path.join(RUNTIME_ROOT, 'node_modules');
record('node_modules', existsSync(nodeModules), existsSync(nodeModules) ? nodeModules : `missing: ${nodeModules}`);

const packageRequire = createRequire(path.join(RUNTIME_ROOT, 'package.json'));
const loaded = new Map();
for (const packageName of ['playwright-core', 'pdf-lib', 'pptxgenjs', 'jszip']) {
  try {
    const resolved = packageRequire.resolve(packageName);
    const module = await import(pathToFileURL(resolved));
    loaded.set(packageName, module);
    record(`Node package ${packageName}`, true, resolved);
  } catch (error) {
    record(`Node package ${packageName}`, false, error.message);
  }
}

const browserCandidates = [
  process.env.CHROME_PATH,
  process.env.EDGE_PATH,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'], 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'], 'Google', 'Chrome', 'Application', 'chrome.exe'),
].filter(Boolean);

const browserPath = browserCandidates.find(existsSync);
if (!browserPath) {
  record('Chromium launch', false, 'browser not found; set CHROME_PATH or EDGE_PATH');
} else if (!loaded.has('playwright-core')) {
  record('Chromium launch', false, 'playwright-core is unavailable');
} else {
  try {
    const imported = loaded.get('playwright-core');
    const playwright = imported.default || imported;
    const browser = await playwright.chromium.launch({ executablePath: browserPath, headless: true });
    await browser.close();
    record('Chromium launch', true, browserPath);
  } catch (error) {
    record('Chromium launch', false, `${browserPath}: ${error.message}`);
  }
}

record('Platform', true, `${process.platform} ${process.arch}`);

if (results.some((item) => !item.ok)) process.exitCode = 1;
