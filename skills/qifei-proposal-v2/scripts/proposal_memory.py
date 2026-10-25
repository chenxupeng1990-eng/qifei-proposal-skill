#!/usr/bin/env python3
"""Three-layer proposal memory: Owner preferences, project decisions, playbook.

Memory lives in plain Markdown so any agent can read it and the Owner can edit it.
`load` prints only the active entries relevant to the current phase, within a budget.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "memory-templates"
PROJECT_MEMORY = Path("memory") / "decisions.md"

# project-state phase -> memory stage
PHASE_STAGE = {
    "intake": "intake",
    "requirements": "intake",
    "strategy": "strategy",
    "project_agents": "strategy",
    "manuscript": "manuscript",
    "full_redteam": "review",
    "content_frozen": "review",
    "visual_direction": "visual",
    "design_calibration": "visual",
    "design_system": "visual",
    "generation": "production",
    "review": "production",
    "speaker_notes": "export",
    "qa": "export",
    "export": "export",
}
STAGES = sorted(set(PHASE_STAGE.values()) | {"all"})
LAYER_ORDER = ("project", "owner", "playbook")
LAYER_LABEL = {"project": "项目记忆", "owner": "Owner 偏好", "playbook": "方法论"}
ID_PREFIX = {"owner": "O", "project": "D", "playbook": "PB"}

ENTRY_HEADING = re.compile(r"^##\s+([A-Z]{1,2}-\d{3,})\s*[｜|]\s*(.+?)\s*$")
ENTRY_FIELD = re.compile(r"^-\s*(阶段|状态|日期|来源|适用)\s*[：:]\s*(.*?)\s*$")
COMMENT = re.compile(r"<!--.*?-->", re.S)
STATUS = re.compile(r"^(active|retired|superseded:([A-Z]{1,2}-\d{3,}))$")


@dataclass
class Entry:
    id: str
    title: str
    layer: str
    path: Path
    stages: list[str] = field(default_factory=list)
    status: str = ""
    date: str = ""
    source: str = ""
    scope: list[str] = field(default_factory=list)
    body: str = ""

    @property
    def active(self) -> bool:
        return self.status == "active"


def memory_home() -> Path:
    return Path(os.environ.get("QIFEI_MEMORY_HOME") or Path.home() / ".qifei-proposal" / "memory")


def split_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、/]", value) if item.strip()]


def parse_file(path: Path, layer: str) -> list[Entry]:
    text = COMMENT.sub("", path.read_text(encoding="utf-8"))
    entries: list[Entry] = []
    current: Entry | None = None
    body: list[str] = []

    def close() -> None:
        if current is not None:
            current.body = "\n".join(body).strip()
            entries.append(current)

    for line in text.split("\n"):
        heading = ENTRY_HEADING.match(line)
        if heading:
            close()
            current, body = Entry(heading.group(1), heading.group(2), layer, path), []
            continue
        if current is None:
            continue
        match = ENTRY_FIELD.match(line.strip())
        if match and not body:
            name, value = match.groups()
            if name == "阶段":
                current.stages = split_list(value)
            elif name == "状态":
                current.status = value
            elif name == "日期":
                current.date = value
            elif name == "来源":
                current.source = value
            else:
                current.scope = split_list(value)
            continue
        if line.strip() or body:
            body.append(line)
    close()
    return entries


def memory_files(project: Path | None) -> list[tuple[str, Path]]:
    home = memory_home()
    files: list[tuple[str, Path]] = []
    if project is not None and (project / PROJECT_MEMORY).is_file():
        files.append(("project", project / PROJECT_MEMORY))
    if (home / "owner.md").is_file():
        files.append(("owner", home / "owner.md"))
    playbook = home / "playbook"
    if playbook.is_dir():
        files += [("playbook", path) for path in sorted(playbook.glob("*.md")) if path.name.lower() != "readme.md"]
    return files


def collect(project: Path | None) -> list[Entry]:
    return [entry for layer, path in memory_files(project) for entry in parse_file(path, layer)]


def check(entries: list[Entry]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, Path] = {}
    ids = {entry.id for entry in entries}
    for entry in entries:
        where = f"{entry.path.name}:{entry.id}"
        if entry.id in seen:
            errors.append(f"{where}: duplicate id (also in {seen[entry.id].name})")
        seen[entry.id] = entry.path
        if not entry.id.startswith(ID_PREFIX[entry.layer] + "-"):
            errors.append(f"{where}: {LAYER_LABEL[entry.layer]} ids start with {ID_PREFIX[entry.layer]}-")
        if not entry.stages:
            errors.append(f"{where}: 阶段 is required")
        for stage in entry.stages:
            if stage not in STAGES:
                errors.append(f"{where}: unknown 阶段 '{stage}' (use {', '.join(STAGES)})")
        status = STATUS.match(entry.status or "")
        if not status:
            errors.append(f"{where}: 状态 must be active, retired or superseded:<id>")
        elif status.group(2) and status.group(2) not in ids:
            errors.append(f"{where}: superseded by unknown id {status.group(2)}")
        try:
            dt.date.fromisoformat(entry.date)
        except ValueError:
            errors.append(f"{where}: 日期 must be YYYY-MM-DD")
        if not entry.source:
            errors.append(f"{where}: 来源 is required (Owner's words, record id or review)")
        if not entry.body:
            errors.append(f"{where}: body is empty")
    return errors


def select(entries: list[Entry], stage: str, tags: list[str]) -> list[Entry]:
    chosen = []
    for entry in entries:
        if not entry.active:
            continue
        if stage not in entry.stages and "all" not in entry.stages:
            continue
        if tags and entry.scope and "all" not in entry.scope and not set(entry.scope) & set(tags):
            continue
        chosen.append(entry)
    # Project decisions first (most specific), then Owner, then playbook; newest first in each.
    rank = {layer: index for index, layer in enumerate(LAYER_ORDER)}
    return sorted(chosen, key=lambda e: (rank[e.layer], -int(re.sub(r"\D", "", e.date) or 0)))


def render_load(entries: list[Entry], stage: str, max_entries: int, max_chars: int) -> str:
    lines = [
        f"# 提案记忆｜{stage} 阶段",
        "",
        "以下是 Owner 确认过的偏好与经验，用来校准判断，不是事实来源。"
        "与本项目已确认的决定、证据台账或 Owner 当下指示冲突时，以后者为准。",
    ]
    used = sum(len(line) for line in lines)
    shown = 0
    current_layer = None
    for entry in entries:
        block = [f"- **{entry.id}｜{entry.title}**（{entry.date}，{entry.source}）"]
        block += [f"  {line}" for line in entry.body.split("\n") if line.strip()]
        size = sum(len(line) + 1 for line in block)
        if shown >= max_entries or used + size > max_chars:
            break
        if entry.layer != current_layer:
            lines += ["", f"## {LAYER_LABEL[entry.layer]}"]
            current_layer = entry.layer
        lines += block
        used += size
        shown += 1
    omitted = len(entries) - shown
    if not entries:
        lines += ["", "（本阶段没有相关记忆）"]
    elif omitted:
        lines += ["", f"（另有 {omitted} 条相关记忆超出加载上限未显示；需要时用 `proposal_memory.py list` 查看。）"]
    return "\n".join(lines) + "\n"


def init(project: Path | None) -> list[Path]:
    created: list[Path] = []
    home = memory_home()
    targets = [
        (TEMPLATE_ROOT / "owner.md", home / "owner.md"),
        (TEMPLATE_ROOT / "playbook.md", home / "playbook" / "playbook.md"),
    ]
    if project is not None:
        targets.append((SKILL_ROOT / "assets" / "project-template" / PROJECT_MEMORY, project / PROJECT_MEMORY))
    for source, destination in targets:
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(destination)
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "load", "check", "list"):
        command = sub.add_parser(name)
        command.add_argument("--project", help="proposal project directory")
        if name == "load":
            command.add_argument("--phase", required=True, help="project-state.json phase")
            command.add_argument("--tags", default="", help="comma-separated scope tags, e.g. 美妆,比稿")
            command.add_argument("--max-entries", type=int, default=30)
            command.add_argument("--max-chars", type=int, default=8000)
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve() if args.project else None

    if args.command == "init":
        created = init(project)
        for path in created:
            print(f"created {path}")
        if not created:
            print("memory files already exist")
        return 0

    entries = collect(project)
    if args.command == "check":
        errors = check(entries)
        for error in errors:
            print(f"ERROR {error}")
        print(f"{'FAIL' if errors else 'PASS'}: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} checked")
        return 1 if errors else 0
    if args.command == "list":
        for entry in entries:
            print(f"{entry.id}\t{entry.layer}\t{entry.status}\t{','.join(entry.stages)}\t{entry.title}")
        return 0

    stage = PHASE_STAGE.get(args.phase)
    if stage is None:
        print(f"unknown phase '{args.phase}'", file=sys.stderr)
        return 2
    tags = split_list(args.tags)
    sys.stdout.write(render_load(select(entries, stage, tags), stage, args.max_entries, args.max_chars))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
