#!/usr/bin/env python3
"""Tell the user when a newer release of the proposal Skill is out, and update it on request.

Most users talk only to their agent and never open GitHub, so the Skill checks for itself:
doctor.py runs `check` at the start of a task and prints one plain-language line when a newer
release exists. The agent passes it on; it never updates without the user asking.

    python3 scripts/update_skill.py check          # what doctor runs; silent when offline or up to date
    python3 scripts/update_skill.py run            # the user said "更新提案 skill"
    python3 scripts/update_skill.py off | on       # stop or resume the check (all projects)

Updating replaces only the installed Skill folders. Projects, proposal memory and settings under
~/.qifei-proposal are never touched. The installer backs up the old folders and restores them if
the new copy fails its self-check.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
INSTALL_RECORD = SKILL_ROOT / ".install.json"  # written by install_skills.py
REPO = os.environ.get("QIFEI_UPDATE_REPO") or "chenxupeng1990-eng/qifei-proposal-skill"
TIMEOUT = 3


def home() -> Path:
    return Path(os.environ.get("QIFEI_HOME") or Path.home() / ".qifei-proposal")


def settings_path() -> Path:
    return home() / "settings.json"


def cache_path() -> Path:
    return home() / "update-check.json"


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_enabled() -> bool:
    env = os.environ.get("QIFEI_UPDATE_CHECK", "").strip().lower()
    if env in {"0", "off", "false", "no"}:
        return False
    return read_json(settings_path()).get("update_check", True) is not False


def set_check_enabled(enabled: bool) -> None:
    settings = read_json(settings_path())
    settings["update_check"] = enabled
    write_json(settings_path(), settings)


def version_tuple(value: str | None) -> tuple[int, ...] | None:
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
    return tuple(int(part) for part in match.groups()) if match else None


def installed() -> dict:
    """Version and source of this installed copy; a repo checkout reads its VERSION file."""
    record = read_json(INSTALL_RECORD)
    if not record.get("version"):
        version_file = SKILL_ROOT.parent.parent / "VERSION"
        if version_file.is_file():
            record = {"version": version_file.read_text(encoding="utf-8").strip(), "source": "repo_checkout",
                      "source_path": str(SKILL_ROOT.parent.parent)}
    return record


def managed_by() -> str | None:
    """A Skill folder kept by a skill manager is updated through that manager, never overwritten here."""
    resolved = str(SKILL_ROOT.resolve())
    if "/.config/magpie/" in resolved.replace("\\", "/"):
        return "magpie"
    return None


def release_summary(body: str) -> list[str]:
    """The release's opening line, which is written for users, not developers: short enough for an
    agent to pass on to someone who has never opened GitHub. Bullet lists below it are not used."""
    lines = [line.strip() for line in body.splitlines()]
    summary = next((line for line in lines if line and not line.startswith(("#", "*", "-", ">", "|"))), "")
    summary = summary.rstrip("。.")[:60]
    return [summary] if summary else []


def fetch_latest() -> dict | None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "qifei-proposal-update-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:  # offline, rate-limited, blocked: the check stays silent
        return None
    tag = str(data.get("tag_name") or "")
    if not version_tuple(tag):
        return None
    return {"version": tag.lstrip("v"), "summary": release_summary(str(data.get("body") or "")),
            "zipball_url": data.get("zipball_url"), "html_url": data.get("html_url")}


def check(today: str | None = None, fetch=fetch_latest) -> dict:
    """What doctor shows. Looks online at most once a day, and tells the user about one version once a day."""
    today = today or dt.date.today().isoformat()
    result = {"enabled": check_enabled(), "current": installed().get("version"), "latest": None,
              "newer": False, "notify": False, "managed_by": managed_by(), "message": None}
    if not result["enabled"] or not version_tuple(result["current"]):
        return result
    cache = read_json(cache_path())
    if cache.get("checked_on") != today:
        latest = fetch()
        if latest is None:
            return result
        cache.update({"checked_on": today, "latest": latest})
        write_json(cache_path(), cache)
    latest = cache.get("latest") or {}
    result["latest"] = latest.get("version")
    result["newer"] = bool(version_tuple(latest.get("version")) and version_tuple(latest["version"]) > version_tuple(result["current"]))
    if not result["newer"]:
        return result
    notified = cache.get("notified") or {}
    result["notify"] = notified != {"version": latest["version"], "on": today}
    how = ("这份 skill 由 magpie 管理，用 magpie 更新" if result["managed_by"] == "magpie"
           else "说“更新提案 skill”就能更新")
    points = "；".join(latest.get("summary") or [])
    result["message"] = (f"提案 skill 有新版本 {latest['version']}（你现在用的是 {result['current']}）。"
                         + (f"这次更新：{points}。" if points else "") + how + "。")
    if result["notify"]:
        cache["notified"] = {"version": latest["version"], "on": today}
        write_json(cache_path(), cache)
    return result


def run_install(source_root: Path, target: Path) -> None:
    installer = source_root / "scripts" / "install_skills.py"
    if not installer.is_file():
        raise SystemExit(f"找不到安装脚本：{installer}")
    command = [sys.executable, str(installer), "--suite", "v2", "--force", "--target", str(target)]
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise SystemExit("更新没有完成，原来的版本已经恢复。把上面的输出发给维护者。")


def update() -> int:
    if managed_by() == "magpie":
        print("这份 skill 由 magpie 管理，请用 magpie 更新（例如 magpie library sync），这里不直接覆盖。")
        return 2
    record = installed()
    target = SKILL_ROOT.parent
    source = Path(str(record.get("source_path") or ""))
    if record.get("source") in {"git", "repo_checkout"} and (source / ".git").exists():
        print(f"从本地仓库更新：{source}", flush=True)
        pulled = subprocess.run(["git", "-C", str(source), "pull", "--ff-only"], check=False)
        if pulled.returncode:
            raise SystemExit("拉取最新代码失败（本地仓库可能有改动），没有改动已安装的 skill。")
        if record.get("source") == "repo_checkout":
            print("当前就是仓库里的副本，已经更新到最新。")
            return 0
        run_install(source, target)
    else:
        latest = fetch_latest()
        if not latest or not latest.get("zipball_url"):
            raise SystemExit("连不上 GitHub，暂时没法下载新版本；已安装的 skill 没有改动。")
        print(f"下载新版本 {latest['version']} …", flush=True)
        with tempfile.TemporaryDirectory(prefix="qifei-update-") as tmp:
            archive = Path(tmp) / "release.zip"
            request = urllib.request.Request(latest["zipball_url"], headers={"User-Agent": "qifei-proposal-update"})
            with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as out:
                shutil.copyfileobj(response, out)
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(Path(tmp) / "src")
            roots = [p for p in (Path(tmp) / "src").iterdir() if p.is_dir()]
            if len(roots) != 1:
                raise SystemExit("下载的压缩包结构不对，已安装的 skill 没有改动。")
            run_install(roots[0], target)
    print("更新完成。重启 Codex（或当前 Agent）后生效；你的项目文件和提案记忆都没有改动。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check", "run", "on", "off"), nargs="?", default="check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command in {"on", "off"}:
        set_check_enabled(args.command == "on")
        print("已开启更新检查。" if args.command == "on" else "已关闭更新检查（所有项目）。用 on 重新开启。")
        return 0
    if args.command == "run":
        return update()
    result = check()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["message"]:
        print(result["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
