#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h}/.."

install_formula() {
  local command_name="$1"
  local formula="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    return
  fi
  if ! command -v brew >/dev/null 2>&1; then
    print "$command_name is missing and Homebrew is unavailable. Install $formula, then rerun this file."
    exit 2
  fi
  local reply
  read -r "reply?$command_name is missing. Install $formula with Homebrew now? [y/N] "
  if [[ "$reply" != [yY] ]]; then
    print "Installation stopped without changing the system runtime."
    exit 2
  fi
  brew install "$formula"
}

if ! command -v python3 >/dev/null 2>&1; then
  install_formula python3 python
fi

if ! command -v node >/dev/null 2>&1; then
  install_formula node node
fi
if ! command -v npm >/dev/null 2>&1; then
  install_formula npm node
fi

python3 "$ROOT/scripts/bootstrap.py" --suite v2
install_args=(--suite v2)
if [[ -d "$HOME/.codex/skills/qifei-proposal-v2" ]]; then
  read -r "reply?Proposal Skill V2 is already installed. Replace it with this version? [y/N] "
  if [[ "$reply" != [yY] ]]; then
    print "Installation stopped; the existing Skill was preserved."
    exit 2
  fi
  install_args+=(--force)
fi
python3 "$ROOT/scripts/install_skills.py" "${install_args[@]}"

if ! command -v lark-cli >/dev/null 2>&1; then
  print ""
  read -r "reply?Feishu CLI is not installed. Install it now? [y/N] "
  if [[ "$reply" == [yY] ]]; then
    npm install -g @larksuite/cli
  else
    print "Feishu support was skipped. Install later with: npm install -g @larksuite/cli"
  fi
fi

print "Feishu authorization is intentionally deferred until a Feishu task starts."

print ""
print "Proposal Skill V2 installation is complete. Restart Codex before first use."
