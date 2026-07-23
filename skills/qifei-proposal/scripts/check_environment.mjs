import { existsSync } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const results = [];

function record(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: ${detail}`);
}

const nodeMajor = Number(process.versions.node.split('.')[0]);
record('Node.js', nodeMajor >= 18, `${process.versions.node} (required >=18)`);

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

const browser = browserCandidates.find(existsSync);
record('Chromium browser', Boolean(browser), browser || 'not found; set CHROME_PATH or EDGE_PATH');

record('Platform', true, `${process.platform} ${process.arch}`);

if (results.some((item) => !item.ok)) process.exitCode = 1;
