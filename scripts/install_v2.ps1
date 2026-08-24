param(
  [switch]$InstallSystemDeps,
  [switch]$InstallLarkCli
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
  if ($InstallSystemDeps -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    winget install --id Python.Python.3.12 --exact
    throw "Python was installed. Restart PowerShell, then rerun this script."
  }
  throw "Python 3.9+ is required. Rerun with -InstallSystemDeps or install Python manually."
}
if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
  if ($InstallSystemDeps -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    winget install --id OpenJS.NodeJS.LTS --exact
    throw "Node.js was installed. Restart PowerShell, then rerun this script."
  }
  throw "Node.js 18+ and npm are required. Rerun with -InstallSystemDeps or install Node.js manually."
}

$Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$PythonArgs = if ($Python -eq "py") { @("-3") } else { @() }

& $Python @PythonArgs "$Root/scripts/bootstrap.py" --suite v2
& $Python @PythonArgs "$Root/scripts/install_skills.py" --suite v2

if ($InstallLarkCli -and -not (Get-Command lark-cli -ErrorAction SilentlyContinue)) {
  npm install -g @larksuite/cli
}

Write-Host "Proposal Skill V2 installation is complete. Restart Codex before first use."
