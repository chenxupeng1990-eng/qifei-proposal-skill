#!/usr/bin/env python3
"""Three-layer proposal memory: Owner preferences, project decisions, playbook.

Memory lives in plain Markdown under one memory home so the Owner can review every layer in one
place (`memory_box.py`); project memory sits in `projects/<project_id>/`, not in the project folder.
`load` prints only the active entries relevant to the current phase, within a budget.
`signals` digests studio decisions (resolved comments, Owner edits, chapter confirmations)
so an agent can propose candidates in `memory/candidates.md`; only the Owner accepts them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "memory-templates"
PROJECT_MEMORY = "decisions.md"
CANDIDATES = "candidates.md"

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
# Work in a later stage often reopens earlier content, so earlier-stage memory is loaded too.
STAGE_ORDER = ("intake", "strategy", "manuscript", "review", "visual", "production", "export")
RECEIPT = "receipt.json"
LAYER_ORDER = ("project", "owner", "playbook")
LAYER_LABEL = {"project": "项目记忆", "owner": "Owner 偏好", "playbook": "方法论"}
ID_PREFIX = {"owner": "O", "project": "D", "playbook": "PB"}

ENTRY_HEADING = re.compile(r"^##\s+([A-Z]{1,2}-\d{3,})\s*[｜|]\s*(.+?)\s*$")
ENTRY_FIELD = re.compile(r"^-\s*(阶段|状态|日期|来源|适用|建议层级)\s*[：:]\s*(.*?)\s*$")
COMMENT = re.compile(r"<!--.*?-->", re.S)
STATUS = re.compile(r"^(active|retired|superseded:([A-Z]{1,2}-\d{3,}))$")
CANDIDATE_STATUS = re.compile(r"^(candidate|rejected|accepted:([A-Z]{1,2}-\d{3,}))$")
SIGNAL_REF = re.compile(r"(?<![A-Za-z0-9_-])(C-\d{4,}|R\d+|confirm-[A-Za-z0-9_-]+)")


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
    target: str = ""
    body: str = ""
    project: str = ""

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
            elif name == "建议层级":
                current.target = value
            else:
                current.scope = split_list(value)
            continue
        if line.strip() or body:
            body.append(line)
    close()
    return entries


def project_dir(project: Path) -> Path:
    """The project's folder in the memory home, keyed by project_id; records where the project lives."""
    state_path = project / "project-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    key = re.sub(r"[^\w.-]+", "-", str(state.get("project_id") or project.name)).strip("-") or "project"
    folder = memory_home() / "projects" / key
    info = {"project_id": key, "name": state.get("project_name") or project.name, "path": str(project)}
    info_path = folder / "project.json"
    if not info_path.is_file() or json.loads(info_path.read_text(encoding="utf-8")) != info:
        folder.mkdir(parents=True, exist_ok=True)
        info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return folder


def project_dirs() -> list[Path]:
    root = memory_home() / "projects"
    return sorted(p for p in root.iterdir() if (p / "project.json").is_file()) if root.is_dir() else []


def memory_files(pdir: Path | None) -> list[tuple[str, Path]]:
    home = memory_home()
    files: list[tuple[str, Path]] = []
    if pdir is not None and (pdir / PROJECT_MEMORY).is_file():
        files.append(("project", pdir / PROJECT_MEMORY))
    if (home / "owner.md").is_file():
        files.append(("owner", home / "owner.md"))
    playbook = home / "playbook"
    if playbook.is_dir():
        files += [("playbook", path) for path in sorted(playbook.glob("*.md")) if path.name.lower() != "readme.md"]
    return files


def collect(pdir: Path | None) -> list[Entry]:
    entries = [entry for layer, path in memory_files(pdir) for entry in parse_file(path, layer)]
    for entry in entries:
        if entry.layer == "project":
            entry.project = pdir.name
    return entries


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


def stage_distance(entry: Entry, stage: str) -> int | None:
    """0 for the current stage (or all), n for an entry from n stages earlier, None for later-only entries."""
    if "all" in entry.stages or stage in entry.stages:
        return 0
    here = STAGE_ORDER.index(stage)
    earlier = [here - STAGE_ORDER.index(s) for s in entry.stages if s in STAGE_ORDER and STAGE_ORDER.index(s) < here]
    return min(earlier) if earlier else None


def select(entries: list[Entry], stage: str, tags: list[str]) -> list[Entry]:
    chosen = []
    for entry in entries:
        if not entry.active or stage_distance(entry, stage) is None:
            continue
        if tags and entry.scope and "all" not in entry.scope and not set(entry.scope) & set(tags):
            continue
        chosen.append(entry)
    # Project decisions first (most specific), then Owner, then playbook; within a layer the
    # current stage comes before earlier stages, newest first.
    rank = {layer: index for index, layer in enumerate(LAYER_ORDER)}
    return sorted(chosen, key=lambda e: (rank[e.layer], stage_distance(e, stage),
                                         -int(re.sub(r"\D", "", e.date) or 0)))


def render_load(entries: list[Entry], stage: str, max_entries: int, max_chars: int) -> str:
    lines = [
        f"# 提案记忆｜{stage} 阶段",
        "",
        "以下是 Owner 确认过的偏好与经验，用来校准判断，不是事实来源。"
        "与本项目已确认的决定、证据台账或 Owner 当下指示冲突时，以后者为准。"
        "标注“前序阶段”的条目来自更早的阶段，本次工作涉及那部分内容时同样适用。",
    ]
    used = sum(len(line) for line in lines)
    shown = 0
    current_layer = None
    for entry in entries:
        earlier = "" if stage_distance(entry, stage) == 0 else f"前序阶段 {'、'.join(entry.stages)}；"
        block = [f"- **{entry.id}｜{entry.title}**（{earlier}{entry.date}，{entry.source}）"]
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


def memory_for_phase(project: Path, phase: str, tags: list[str] | None = None,
                     max_entries: int = 30, max_chars: int = 8000) -> tuple[str, str, int]:
    """(rendered memory, digest, entry count) for a project phase. The digest ignores tags,
    so a receipt stays valid however the agent narrowed what it printed."""
    stage = PHASE_STAGE[phase]
    entries = collect(project_dir(project))
    everything = select(entries, stage, [])
    digest = hashlib.sha256(json.dumps([[e.id, e.date, e.status, e.title, e.body] for e in everything],
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    text = render_load(select(entries, stage, tags or []), stage, max_entries, max_chars)
    return text, digest, len(everything)


def write_receipt(project: Path, phase: str, digest: str, by: str) -> None:
    """Record that the memory for this phase was put in front of the agent."""
    receipt = {"phase": phase, "digest": digest, "by": by, "at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    (project_dir(project) / RECEIPT).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def receipt_problem(project: Path, phase: str) -> str | None:
    """Why the current memory for this phase has not been read yet, or None when it has (or there is none)."""
    if phase not in PHASE_STAGE:
        return None
    _, digest, count = memory_for_phase(project, phase)
    if not count:
        return None
    path = project_dir(project) / RECEIPT
    receipt = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if receipt.get("phase") != phase:
        return f"本阶段（{phase}）的 {count} 条提案记忆还没有读取"
    if receipt.get("digest") != digest:
        return f"提案记忆在上次读取后有更新（{count} 条适用于 {phase}）"
    return None


def init(pdir: Path | None) -> list[Path]:
    created: list[Path] = []
    home = memory_home()
    targets = [
        (TEMPLATE_ROOT / "owner.md", home / "owner.md"),
        (TEMPLATE_ROOT / "playbook.md", home / "playbook" / "playbook.md"),
    ]
    if pdir is not None:
        targets += [(TEMPLATE_ROOT / "project.md", pdir / PROJECT_MEMORY),
                    (TEMPLATE_ROOT / "candidates.md", pdir / CANDIDATES)]
    for source, destination in targets:
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(destination)
    return created

# ---------- R2: candidates distilled from studio decisions ----------

def _clip(text: str, limit: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def load_candidates(pdir: Path) -> list[Entry]:
    path = pdir / CANDIDATES
    entries = parse_file(path, "candidate") if path.is_file() else []
    for entry in entries:
        entry.project = pdir.name
    return entries


def used_refs(pdir: Path) -> set[str]:
    """Signal ids already cited by a candidate or a memory entry, so they are not offered twice."""
    sources = [entry.source for entry in load_candidates(pdir) + collect(pdir)]
    return {ref for source in sources for ref in SIGNAL_REF.findall(source)}


def _field_md(text: str, slide_id: str, key: str) -> str | None:
    import draft_studio

    for chapter in draft_studio.parse_draft(text)["chapters"]:
        for slide in chapter["slides"]:
            if slide["id"] == slide_id:
                if key == "title":
                    return slide["title"]
                return next((f["md"] for f in slide["fields"] if f["key"] == key), None)
    return None


def studio_signals(project: Path) -> list[dict]:
    """Decided comment threads, Owner edits and chapter confirmations, oldest first, each with a ref id."""
    import draft_studio

    draft_path, _ = draft_studio.load_project(project, None)
    signals: list[dict] = []
    for thread in draft_studio.CommentStore(draft_path).load()["threads"]:
        if thread.get("status") != "resolved":
            continue
        signals.append({
            "ref": thread["id"], "kind": "comment",
            "head": f"{thread.get('slide') or '全稿'} · {draft_studio.field_label(thread.get('field') or '')}"
                    f"（{thread.get('status_by') or 'Owner'} 决定）",
            "lines": [f"> {_clip(thread['quote'], 160)}"]
                     + [f"- {m['author']}：{_clip(m['text'])}" for m in thread["messages"]],
        })
    revisions = draft_path.parent / "revisions"
    for entry in draft_studio.DraftStore(project, draft_path, None).entries():
        if entry.get("actor") != "owner" or not entry.get("slides"):
            continue
        slide, note = entry["slides"][0], str(entry.get("note") or "")
        key = note.split(":", 1)[1] if note.startswith("field:") else note
        lines = [f"- 改动：{draft_studio.FIELD_NAMES.get(key, key)}"]
        before_path = revisions / f"rev-{entry['revision'] - 1:06d}.md"
        after_path = revisions / f"rev-{entry['revision']:06d}.md"
        if before_path.is_file() and after_path.is_file():
            try:
                before = _field_md(before_path.read_text(encoding="utf-8"), slide, key)
                after = _field_md(after_path.read_text(encoding="utf-8"), slide, key)
            except ValueError:
                before = after = None
            if before is not None and after is not None:
                lines = [f"- 改前：{_clip(before)}", f"- 改后：{_clip(after)}"]
        signals.append({
            "ref": f"R{entry['revision']}", "kind": "edit",
            "head": f"{slide} · {draft_studio.FIELD_NAMES.get(key, key)}（Owner 修改，{entry['at'][:10]}）",
            "lines": lines,
        })
    for record in draft_studio.ConfirmationStore(draft_path).load()["records"]:
        pages = list(record.get("slides") or {})
        signals.append({
            "ref": record["record_id"], "kind": "confirm",
            "head": f"{record['chapter_id']}（{record.get('by') or 'Owner'} 确认，rev {record.get('revision')}）",
            "lines": [f"- 页面：{'、'.join(pages)}"],
        })
    return signals


SIGNAL_SECTIONS = (("comment", "已决定的评论"), ("edit", "Owner 的修改"), ("confirm", "章节确认"))


def render_signals(project: Path, show_all: bool) -> str:
    signals = studio_signals(project)
    used = used_refs(project_dir(project))
    fresh = [s for s in signals if show_all or s["ref"] not in used]
    lines = [
        "# 记忆信号",
        "",
        "从工作台的评论、修改和确认里汇总的素材。只把能在后续页面、阶段或其他项目复用的判断写成候选，"
        f"一次性的措辞修改不写。每条候选的来源写上信号编号（如 C-0003、R262），写进 `{project_dir(project) / CANDIDATES}`，"
        "由 Owner 在记忆库（`memory_box.py`）里采纳或丢弃。",
    ]
    hidden = len(signals) - len(fresh)
    if hidden:
        lines += ["", f"（{hidden} 条信号已被候选或记忆引用，未显示；加 `--all` 查看全部。）"]
    for kind, label in SIGNAL_SECTIONS:
        group = [s for s in fresh if s["kind"] == kind]
        if not group:
            continue
        lines += ["", f"## {label}"]
        for signal in group:
            lines += ["", f"### {signal['ref']}｜{signal['head']}", *signal["lines"]]
    if not fresh:
        lines += ["", "（没有新的信号）"]
    return "\n".join(lines) + "\n"


def _entry_spans(text: str) -> list[tuple[str, int, int]]:
    """(id, start, end) of every entry section, ignoring the commented examples."""
    hidden = [m.span() for m in COMMENT.finditer(text)]
    heads = [m for m in re.finditer(ENTRY_HEADING.pattern, text, re.M)
             if not any(a <= m.start() < b for a, b in hidden)]
    return [(m.group(1), m.start(), heads[i + 1].start() if i + 1 < len(heads) else len(text))
            for i, m in enumerate(heads)]


def set_candidate_status(pdir: Path, candidate_id: str, status: str) -> None:
    path = pdir / CANDIDATES
    text = path.read_text(encoding="utf-8")
    for entry_id, start, end in _entry_spans(text):
        if entry_id == candidate_id:
            section, count = re.subn(r"^(-\s*状态\s*[：:]\s*).*$", lambda m: m.group(1) + status,
                                     text[start:end], count=1, flags=re.M)
            if not count:
                raise ValueError(f"{candidate_id} has no 状态 line")
            path.write_text(text[:start] + section + text[end:], encoding="utf-8")
            return
    raise ValueError(f"unknown candidate {candidate_id}")


def layer_path(pdir: Path, layer: str) -> Path:
    if layer == "project":
        return pdir / PROJECT_MEMORY
    if layer == "owner":
        return memory_home() / "owner.md"
    return memory_home() / "playbook" / "playbook.md"


def _open_candidate(pdir: Path, candidate_id: str) -> Entry:
    candidate = next((c for c in load_candidates(pdir) if c.id == candidate_id), None)
    if candidate is None:
        raise ValueError(f"unknown candidate {candidate_id}")
    if candidate.status != "candidate":
        raise ValueError(f"{candidate_id} is already {candidate.status}")
    return candidate


def accept(pdir: Path, candidate_id: str, layer: str | None = None, title: str | None = None,
           body: str | None = None, stages: list[str] | None = None, by: str = "Owner") -> str:
    """Owner action: write the candidate (as edited) into its memory layer and mark it accepted."""
    candidate = _open_candidate(pdir, candidate_id)
    layer = layer or candidate.target
    if layer not in ID_PREFIX:
        raise ValueError(f"layer must be one of {', '.join(LAYER_ORDER)}")
    title = " ".join((title or candidate.title).split())
    body = (body if body is not None else candidate.body).strip()
    stages = stages or candidate.stages
    if not title or not body:
        raise ValueError("title and body cannot be empty")
    unknown = [stage for stage in stages if stage not in STAGES]
    if not stages or unknown:
        raise ValueError(f"阶段 must be chosen from {', '.join(STAGES)}")
    init(pdir)
    prefix = ID_PREFIX[layer]
    taken = [int(e.id.split("-")[1]) for e in collect(pdir) if e.id.startswith(prefix + "-")]
    new_id = f"{prefix}-{max(taken, default=0) + 1:04d}"
    today = dt.date.today().isoformat()
    lines = [
        f"## {new_id}｜{title}",
        f"- 阶段：{', '.join(stages)}",
        "- 状态：active",
        f"- 日期：{today}",
        f"- 来源：{candidate.source}；{by[:40]} 采纳 {today}（{candidate_id}）",
    ]
    if candidate.scope:
        lines.append(f"- 适用：{', '.join(candidate.scope)}")
    target = layer_path(pdir, layer)
    existing = target.read_text(encoding="utf-8")
    target.write_text(existing.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n\n" + body + "\n", encoding="utf-8")
    set_candidate_status(pdir, candidate_id, f"accepted:{new_id}")
    return new_id


def reject(pdir: Path, candidate_id: str) -> None:
    _open_candidate(pdir, candidate_id)
    set_candidate_status(pdir, candidate_id, "rejected")


def update_entry(path: Path, entry_id: str, title: str, body: str, stages: list[str], scope: list[str],
                 status: str) -> None:
    """Owner edit of one memory entry in place; date and source stay as recorded."""
    title, body = " ".join(title.split()), body.strip()
    if not title or not body:
        raise ValueError("title and body cannot be empty")
    if not stages or any(stage not in STAGES for stage in stages):
        raise ValueError(f"阶段 must be chosen from {', '.join(STAGES)}")
    if not STATUS.match(status):
        raise ValueError("状态 must be active, retired or superseded:<id>")
    layer = "owner" if path.name == "owner.md" else "project" if path.name == PROJECT_MEMORY else "playbook"
    entry = next((e for e in parse_file(path, layer) if e.id == entry_id), None)
    if entry is None:
        raise ValueError(f"unknown entry {entry_id}")
    lines = [f"## {entry_id}｜{title}", f"- 阶段：{', '.join(stages)}", f"- 状态：{status}",
             f"- 日期：{entry.date}", f"- 来源：{entry.source}"]
    if scope:
        lines.append(f"- 适用：{', '.join(scope)}")
    text = path.read_text(encoding="utf-8")
    for found, start, end in _entry_spans(text):
        if found == entry_id:
            tail = "\n\n" if end < len(text) else "\n"
            path.write_text(text[:start] + "\n".join(lines) + "\n\n" + body + tail + text[end:], encoding="utf-8")
            return


def check_candidates(candidates: list[Entry], ids: set[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for entry in candidates:
        where = f"candidates.md:{entry.id}"
        if entry.id in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(entry.id)
        if not entry.id.startswith("MC-"):
            errors.append(f"{where}: candidate ids start with MC-")
        status = CANDIDATE_STATUS.match(entry.status or "")
        if not status:
            errors.append(f"{where}: 状态 must be candidate, rejected or accepted:<id>")
        elif status.group(2) and status.group(2) not in ids:
            errors.append(f"{where}: accepted as unknown id {status.group(2)}")
        if entry.target not in ID_PREFIX:
            errors.append(f"{where}: 建议层级 must be one of {', '.join(LAYER_ORDER)}")
        if not entry.stages or any(stage not in STAGES for stage in entry.stages):
            errors.append(f"{where}: 阶段 must be chosen from {', '.join(STAGES)}")
        if not SIGNAL_REF.search(entry.source):
            errors.append(f"{where}: 来源 must cite a signal id (C-0001, R12 or a confirmation record)")
        if not entry.body:
            errors.append(f"{where}: body is empty")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "load", "check", "list", "signals", "accept", "reject"):
        command = sub.add_parser(name)
        command.add_argument("--project", required=name in {"signals", "accept", "reject"},
                             help="proposal project directory")
        if name in {"accept", "reject"}:
            command.add_argument("candidate", help="candidate id, e.g. MC-0001 (Owner action)")
        if name == "accept":
            command.add_argument("--layer", choices=LAYER_ORDER, help="override 建议层级")
            command.add_argument("--title")
            command.add_argument("--body")
            command.add_argument("--stages", help="comma-separated stages")
            command.add_argument("--by", default="Owner")
        if name == "signals":
            command.add_argument("--all", action="store_true", help="include signals already cited")
        if name == "load":
            command.add_argument("--phase", required=True, help="project-state.json phase")
            command.add_argument("--tags", default="", help="comma-separated scope tags, e.g. 美妆,比稿")
            command.add_argument("--max-entries", type=int, default=30)
            command.add_argument("--max-chars", type=int, default=8000)
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve() if args.project else None
    pdir = project_dir(project) if project is not None else None

    if args.command == "init":
        created = init(pdir)
        for path in created:
            print(f"created {path}")
        if not created:
            print("memory files already exist")
        return 0
    try:
        if args.command == "signals":
            sys.stdout.write(render_signals(project, args.all))
            return 0
        if args.command == "accept":
            stages = split_list(args.stages) if args.stages else None
            new_id = accept(pdir, args.candidate, args.layer, args.title, args.body, stages, args.by)
            print(f"{args.candidate} accepted as {new_id}")
            return 0
        if args.command == "reject":
            reject(pdir, args.candidate)
            print(f"{args.candidate} rejected")
            return 0
    except ValueError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1

    entries = collect(pdir)
    if args.command == "check":
        errors = check(entries)
        if pdir is not None:
            errors += check_candidates(load_candidates(pdir), {entry.id for entry in entries})
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
    if project is None:
        sys.stdout.write(render_load(select(entries, stage, tags), stage, args.max_entries, args.max_chars))
        return 0
    text, digest, _ = memory_for_phase(project, args.phase, tags, args.max_entries, args.max_chars)
    write_receipt(project, args.phase, digest, "load")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
