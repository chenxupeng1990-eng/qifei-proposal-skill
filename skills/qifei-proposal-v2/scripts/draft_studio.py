#!/usr/bin/env python3
"""Proposal draft studio: read, edit and export the proposal draft.

The Markdown draft stays the only authority. `render` and `export-md` write
derived views; `serve` runs a local studio where every save is written to the
draft at once, recorded as a new revision with its SHA256, and pushed to every
open page. Edits made to the draft file by an agent are picked up the same way.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets" / "draft-studio"
DEFAULT_DRAFT = "content/draft/proposal-draft.md"
DEFAULT_OUT = "deck/review/draft-studio.html"

# Field headings in the feishu-proposal-draft-v1 page format.
FIELD_HEADINGS = {
    "核心内容": "core",
    "逻辑展开": "logic",
    "PPT上屏内容": "screen",
    "上屏内容": "screen",
    "讲解方向": "talk",
    "策略与过桥": "bridge",
    "视觉生成建议": "visual",
    "证据与来源": "evidence",
}
FIELD_NAMES = {
    "core": "核心内容",
    "logic": "逻辑展开",
    "screen": "PPT上屏内容",
    "talk": "讲解方向",
    "bridge": "策略与过桥",
    "visual": "视觉生成建议",
    "evidence": "证据与来源",
    "lead": "页面预览",
    "other": "其他",
}
FIELD_ORDER = ("lead", "core", "logic", "screen", "talk", "visual", "bridge", "evidence", "other")

# Chapter files written as "- 名称：值" bullets map onto the same fields.
BULLET_FIELDS = {
    "核心内容": "core",
    "页面角色": "core",
    "认知变化": "core",
    "目标情绪": "core",
    "鲜明判断": "core",
    "可见证明": "core",
    "下一页张力": "core",
    "逻辑展开": "logic",
    "上屏副标题": "screen",
    "上屏正文/数字/图注": "screen",
    "上屏正文": "screen",
    "讲解方向": "talk",
    "演讲任务": "talk",
    "前页推导": "bridge",
    "后页承接": "bridge",
    "服务的章节命题": "bridge",
    "在页面论证链中的步骤": "bridge",
    "视觉锤": "visual",
    "主载体": "visual",
    "构图方向": "visual",
    "Image2任务": "visual",
    "HTML任务": "visual",
    "素材需求": "visual",
    "视觉避免事项": "visual",
    "避免事项": "visual",
    "证据编号": "evidence",
    "市场信号边界": "evidence",
}

# The brief Markdown profile keeps what a reader needs, not production notes.
BRIEF_FIELDS = {"core", "logic", "screen", "talk", "evidence"}

SLIDE_HEADING = re.compile(
    r"^(#{1,4})\s*(?:\[`?([A-Z]{1,4}\d{1,3}[A-Za-z]?)`?\]\s*[｜|]?|`?([A-Z]{1,4}\d{1,3}[A-Za-z]?)`?\s*[｜|])\s*(.+?)\s*$"
)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BULLET_FIELD = re.compile(r"^-\s+([^：:`]+?)\s*(?:`[^`]+`)?\s*[：:]\s*(.*)$")
DIRECTIVE_OPEN = re.compile(r"^:::\s*([a-z]+)\s*(.*)$")
FEISHU_TITLE = re.compile(r"^\s*<title>(.*?)</title>\s*$", re.M)
FEISHU_CALLOUT = re.compile(r"<callout[^>]*>\n?(.*?)\n?</callout>", re.S)
FEISHU_IMAGE = re.compile(r"!\[([^\]]*)\]\((https://internal-api-drive-stream\.feishu\.cn[^)]*)\)")


def iter_lines_outside_fences(lines: list[str]):
    """Yield (index, line, in_fence) so headings inside code fences are ignored."""
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            yield index, line, True
            continue
        yield index, line, in_fence


def from_feishu_markup(text: str) -> tuple[str, str | None]:
    """Map Feishu <title>/<callout> tags onto plain Markdown, line for line.

    Keeping the line count unchanged lets edits address the original file by line.
    """
    title = None
    out = []
    for line in text.split("\n"):
        title_match = FEISHU_TITLE.match(line)
        if title_match and title is None:
            title = title_match.group(1).strip()
            out.append("")
        elif re.match(r"^\s*<callout[^>]*>\s*$", line):
            out.append(":::callout")
        elif re.match(r"^\s*</callout>\s*$", line):
            out.append(":::")
        else:
            out.append(line)
    return "\n".join(out), title


def trim_span(lines: list[str], start: int, end: int) -> list[int]:
    """Shrink a line range so blank lines and '---' separators stay outside it."""
    while start < end and not lines[start].strip():
        start += 1
    while end > start and (not lines[end - 1].strip() or re.match(r"^\s*---\s*$", lines[end - 1])):
        end -= 1
    return [start, end]


def parse_draft(text: str) -> dict[str, Any]:
    text, doc_title = from_feishu_markup(text.replace("\r\n", "\n"))
    lines = text.split("\n")
    slide_hits: list[tuple[int, int, str, str]] = []
    for index, line, in_fence in iter_lines_outside_fences(lines):
        if in_fence:
            continue
        match = SLIDE_HEADING.match(line)
        if match:
            slide_hits.append((index, len(match.group(1)), match.group(2) or match.group(3), match.group(4)))
    if not slide_hits:
        raise ValueError("No page units found: expected headings like '## P01｜结论式标题'.")

    levels = [hit[1] for hit in slide_hits]
    slide_level = max(set(levels), key=levels.count)
    slide_hits = [hit for hit in slide_hits if hit[1] == slide_level]
    slide_starts = {hit[0]: hit for hit in slide_hits}
    chapter_level = pick_chapter_level(lines, slide_level, slide_starts)

    title = doc_title
    chapters: list[dict[str, Any]] = []
    preface: list[str] = []
    current_chapter: dict[str, Any] | None = None
    current_slide: dict[str, Any] | None = None

    def flush_slide(end: int) -> None:
        nonlocal current_slide
        if current_slide is not None:
            start = current_slide.pop("_start")
            current_slide["body_span"] = trim_span(lines, start, end)
            current_slide.update(split_fields(lines, start, end, slide_level))
            current_chapter["slides"].append(current_slide)
            current_slide = None

    def close_intro(end: int) -> None:
        if current_chapter is not None and current_chapter.get("intro_span") is None:
            current_chapter["intro_span"] = trim_span(lines, current_chapter["_intro_start"], end)

    for index, line, in_fence in iter_lines_outside_fences(lines):
        heading = None if in_fence else HEADING.match(line)
        if index in slide_starts:
            flush_slide(index)
            if current_chapter is None:
                current_chapter = new_chapter("未分章", len(chapters), index)
                chapters.append(current_chapter)
            close_intro(index)
            _, _, slide_id, slide_title = slide_starts[index]
            current_slide = {"id": slide_id, "title": slide_title.strip(), "line": index, "_start": index + 1}
            continue
        if heading and len(heading.group(1)) == chapter_level and chapter_level >= 1:
            flush_slide(index)
            close_intro(index)
            current_chapter = new_chapter(heading.group(2), len(chapters), index + 1)
            chapters.append(current_chapter)
            continue
        if heading and len(heading.group(1)) < chapter_level and title is None:
            title = heading.group(2)
            continue
        if current_slide is not None:
            continue
        elif current_chapter is not None:
            current_chapter["intro"].append(line)
        else:
            preface.append(line)
    flush_slide(len(lines))
    close_intro(len(lines))

    for chapter in chapters:
        chapter.pop("_intro_start", None)
        chapter["intro_md"] = tidy("\n".join(chapter.pop("intro")))
        if chapter.get("intro_span"):
            start, end = chapter["intro_span"]
            if start < end:
                chapter["intro_raw"] = "\n".join(lines[start:end])
            else:
                chapter["intro_span"] = None
    return {
        "title": title or "提案母稿",
        "preface_md": tidy("\n".join(preface)),
        "chapters": [chapter for chapter in chapters if chapter["slides"] or chapter["intro_md"]],
    }


def pick_chapter_level(lines: list[str], slide_level: int, slide_starts: dict) -> int:
    """Pick the heading level that groups pages into chapters.

    Feishu drafts use '# 章' over '## P01'. Chapter files use '# CH02' over
    '## 章节说明' sections and '### [P08]' pages; there the h2 sections are
    chapter intro, not chapters. A lone top heading over real chapters is the
    document title.
    """
    owners_by_level: dict[int, list[int]] = {}
    for level in range(1, slide_level):
        owners: list[int] = []
        unowned = False
        for index, line, in_fence in iter_lines_outside_fences(lines):
            if in_fence:
                continue
            if index in slide_starts:
                if owners:
                    owners[-1] += 1
                else:
                    unowned = True
                continue
            heading = HEADING.match(line)
            if heading and len(heading.group(1)) == level:
                owners.append(0)
        if owners and not unowned:
            owners_by_level[level] = owners
    if not owners_by_level:
        return 0
    level = min(owners_by_level)
    deeper = owners_by_level.get(level + 1)
    if len(owners_by_level[level]) == 1 and deeper and len(deeper) >= 2 and all(deeper):
        return level + 1
    return level


def new_chapter(title: str, index: int, intro_start: int) -> dict[str, Any]:
    clean = re.sub(r"^\s*CH\d+\s*[｜|]\s*", "", title).strip()
    return {
        "id": f"ch{index + 1:02d}",
        "title": clean or title,
        "intro": [],
        "intro_span": None,
        "_intro_start": intro_start,
        "slides": [],
    }


def split_fields(lines: list[str], start: int, end: int, slide_level: int) -> dict[str, Any]:
    """Split one page unit into known fields; keep anything else as 'other'.

    Heading-style fields keep their source line span so they can be edited in place.
    """
    body = lines[start:end]
    field_level = slide_level + 1
    buckets: dict[str, list[str]] = {}
    spans: dict[str, list[int]] = {"lead": [start, start]}
    current = "lead"
    has_field_headings = False
    for offset, line, in_fence in iter_lines_outside_fences(body):
        heading = None if in_fence else HEADING.match(line)
        if heading and len(heading.group(1)) == field_level:
            name = re.sub(r"\s+", "", heading.group(2))
            if name in FIELD_HEADINGS:
                current = FIELD_HEADINGS[name]
                has_field_headings = True
                buckets.setdefault(current, [])
                spans[current] = [start + offset + 1, start + offset + 1]
                continue
        buckets.setdefault(current, []).append(line)
        spans[current][1] = start + offset + 1
    if not has_field_headings:
        buckets, spans = split_bullet_fields(body), {}
    elif "lead" in buckets and not re.search(r"!\[", "\n".join(buckets["lead"])):
        buckets["other"] = buckets.pop("lead") + buckets.get("other", [])
        spans["other"] = spans.pop("lead")
    fields = []
    for key in FIELD_ORDER:
        content = tidy("\n".join(buckets.get(key, [])))
        if content:
            field = {"key": key, "name": FIELD_NAMES[key], "md": content}
            if key in spans:
                field["span"] = trim_span(lines, *spans[key])
                raw = "\n".join(lines[field["span"][0]:field["span"][1]])
                if raw != content:
                    field["raw"] = raw  # exact source, so editing never rewrites what the reader did not touch
            fields.append(field)
    result: dict[str, Any] = {"fields": fields}
    if not any("span" in field for field in fields):
        span = trim_span(lines, start, end)
        result["body_md"] = "\n".join(lines[span[0]:span[1]])
    return result


def split_bullet_fields(body: list[str]) -> dict[str, list[str]]:
    """Chapter-file style: '- 字段：值' bullets grouped into the page fields."""
    rows: dict[str, list[tuple[str, str]]] = {}
    other: list[str] = []
    for line in body:
        match = BULLET_FIELD.match(line.strip())
        if match:
            name, value = match.group(1).strip(), match.group(2).strip()
            key = BULLET_FIELDS.get(name, "other")
            rows.setdefault(key, []).append((name, value))
        elif line.strip():
            other.append(line)
    buckets: dict[str, list[str]] = {}
    for key, items in rows.items():
        lead: list[str] = []
        if key in {"core", "logic"}:
            # The page's own statement reads as prose; the rest becomes a task table.
            primary = [value for name, value in items if name == FIELD_NAMES[key]]
            items = [(name, value) for name, value in items if name != FIELD_NAMES[key]]
            lead = [f"**{primary[0]}**" if key == "core" else primary[0], ""] if primary else []
            if not items:
                buckets[key] = lead
                continue
        table = lead + ["| 项目 | 内容 |", "|-|-|"]
        table += [f"| {name} | {value.replace('|', '｜')} |" for name, value in items]
        buckets[key] = table
    if other:
        buckets.setdefault("other", []).extend(other)
    return buckets


def tidy(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*---\s*$", "", text, flags=re.M)
    return text.strip()


def attach_status(model: dict[str, Any], state: dict[str, Any] | None) -> None:
    confirmed_chapters: set[str] = set()
    confirmed_by_slide: dict[str, bool] = {}
    verified: set[str] = set()
    if state:
        for chapter in state.get("chapters") or []:
            for slide_id in chapter.get("slides") or []:
                confirmed_by_slide[slide_id] = bool(chapter.get("manuscript_confirmed"))
        verified = set((state.get("proposal_draft") or {}).get("verified_slide_ids") or [])
    for chapter in model["chapters"]:
        for slide in chapter["slides"]:
            if not state:
                slide["status"] = "unknown"
            elif confirmed_by_slide.get(slide["id"]):
                slide["status"] = "confirmed"
            elif slide["id"] in verified:
                slide["status"] = "verified"
            else:
                slide["status"] = "pending"


def normalize_markdown(md: str) -> str:
    """Make a fragment portable: directives become quotes, auth-only images become captions."""
    md = FEISHU_IMAGE.sub(lambda m: f"> 图：{m.group(1) or '飞书图片'}", md)
    out: list[str] = []
    lines = md.split("\n")
    index = 0
    while index < len(lines):
        match = DIRECTIVE_OPEN.match(lines[index].strip())
        if match and match.group(1):
            label = {"callout": "提示", "flow": "流程", "compare": "对比", "data": "数据"}.get(match.group(1), match.group(1))
            heading = match.group(2).strip()
            out.append(f"> **{label}{('｜' + heading) if heading else ''}**")
            index += 1
            while index < len(lines) and lines[index].strip() != ":::":
                out.append(f"> {lines[index]}".rstrip())
                index += 1
            index += 1
            continue
        out.append(lines[index])
        index += 1
    return "\n".join(out)


def review_record(threads: list[dict[str, Any]]) -> str:
    """Comment threads of one page as a readable decision record."""
    lines = []
    for thread in threads:
        state = "已决定" if thread.get("status") == "resolved" else "未解决"
        lines.append(f"- **{thread['id']}｜{state}**　“{thread['quote']}”（{field_label(thread.get('field', ''))}）")
        for message in thread.get("messages", []):
            text = " ".join(str(message.get("text", "")).split())
            lines.append(f"  - {message.get('author', '')} {str(message.get('at', ''))[:16].replace('T', ' ')}：{text}")
        if thread.get("status") == "resolved":
            lines.append(f"  - 决定：{thread.get('status_by', '')} {str(thread.get('status_at', ''))[:16].replace('T', ' ')}")
    return "\n".join(lines)


def export_markdown(model: dict[str, Any], profile: str = "full", threads: list[dict[str, Any]] | None = None) -> str:
    """Full profile also carries each page's comment threads as a review record."""
    keep = None if profile == "full" else BRIEF_FIELDS
    by_slide: dict[str, list[dict[str, Any]]] = {}
    if profile == "full":
        for thread in threads or []:
            by_slide.setdefault(thread.get("slide", ""), []).append(thread)
    parts = [f"# {model['title']}"]
    meta = model.get("meta") or {}
    if meta.get("revision") is not None or meta.get("sha256"):
        parts.append(f"> 母稿版本：rev {meta.get('revision', '—')}｜SHA256 {str(meta.get('sha256', ''))[:12]}")
    if model.get("preface_md"):
        parts.append(normalize_markdown(model["preface_md"]))
    for chapter in model["chapters"]:
        parts.append(f"## {chapter['title']}")
        if chapter["intro_md"]:
            parts.append(normalize_markdown(chapter["intro_md"]))
        for slide in chapter["slides"]:
            parts.append(f"### {slide['id']}｜{slide['title']}")
            for field in slide["fields"]:
                if keep is not None and field["key"] not in keep:
                    continue
                parts.append(f"#### {field['name']}")
                parts.append(normalize_markdown(field["md"]))
            if by_slide.get(slide["id"]):
                parts.append("#### 评审记录")
                parts.append(review_record(by_slide[slide["id"]]))
    return tidy("\n\n".join(parts)) + "\n"


def load_project(project: Path, draft_arg: str | None) -> tuple[Path, dict[str, Any] | None]:
    state_path = project / "project-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else None
    candidates = [draft_arg] if draft_arg else []
    if state:
        candidates.append((state.get("proposal_draft") or {}).get("verified_snapshot_path"))
    candidates += [DEFAULT_DRAFT, "content/feishu/proposal-draft.md"]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        path = path if path.is_absolute() else project / path
        if path.is_file():
            return path, state
    raise SystemExit(f"No proposal draft found under {project}; pass --draft.")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def model_from_text(
    text: str,
    project: Path,
    draft_path: Path,
    state: dict[str, Any] | None,
    revision: int | None = None,
    edited: set[str] | None = None,
) -> dict[str, Any]:
    model = parse_draft(text)
    attach_status(model, state)
    for chapter in model["chapters"]:
        for slide in chapter["slides"]:
            if edited and slide["id"] in edited and slide["status"] in {"confirmed", "verified"}:
                slide["status"] = "modified"
    draft_state = (state or {}).get("proposal_draft") or {}
    model["meta"] = {
        "source": str(draft_path.relative_to(project)) if draft_path.is_relative_to(project) else str(draft_path),
        "authority": draft_state.get("authority"),
        "revision": revision if revision is not None else draft_state.get("revision_id"),
        "sha256": sha256_text(text),
        "phase": (state or {}).get("phase"),
        "project_name": (state or {}).get("project_name"),
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if model["title"] == "提案母稿" and model["meta"]["project_name"]:
        model["title"] = model["meta"]["project_name"]
    return model


def build_model(project: Path, draft_arg: str | None) -> dict[str, Any]:
    draft_path, state = load_project(project, draft_arg)
    text = draft_path.read_bytes().decode("utf-8")
    store = DraftStore(project, draft_path, state)
    if store.log_path.is_file():
        return model_from_text(text, project, draft_path, state, store.revision, store.edited_slides())
    return model_from_text(text, project, draft_path, state)


# ---------- Editing ----------

class EditError(ValueError):
    """The requested edit does not address an editable part of the draft."""


class EditConflict(Exception):
    """The draft changed since the editor loaded it."""


def find_slide(model: dict[str, Any], slide_id: str) -> dict[str, Any]:
    for chapter in model["chapters"]:
        for slide in chapter["slides"]:
            if slide["id"] == slide_id:
                return slide
    raise EditError(f"unknown page {slide_id}")


def replace_span(lines: list[str], span: list[int], md: str) -> list[str]:
    start, end = span
    block = md.strip("\n").split("\n") if md.strip() else []
    if block and start > 0 and lines[start - 1].strip():
        block = [""] + block
    if block and end < len(lines) and lines[end].strip():
        block = block + [""]
    return lines[:start] + block + lines[end:]


def apply_edit(text: str, target: dict[str, Any]) -> tuple[str, str | None]:
    """Apply one edit to the draft text; return the new text and the page it touched."""
    model = parse_draft(text)
    lines = text.split("\n")
    kind = target.get("kind")
    md = str(target.get("md", ""))
    if kind == "intro":
        chapter = next((c for c in model["chapters"] if c["id"] == target.get("chapter")), None)
        if chapter is None or not chapter.get("intro_span"):
            raise EditError("this chapter introduction cannot be edited")
        return "\n".join(replace_span(lines, chapter["intro_span"], md)), None
    slide = find_slide(model, str(target.get("slide")))
    if kind == "title":
        title = " ".join(md.split())
        if not title:
            raise EditError("page title cannot be empty")
        match = SLIDE_HEADING.match(lines[slide["line"]])
        lines[slide["line"]] = lines[slide["line"]][: match.start(4)] + title
        return "\n".join(lines), slide["id"]
    if kind == "body":
        return "\n".join(replace_span(lines, slide["body_span"], md)), slide["id"]
    if kind == "field":
        field = next((f for f in slide["fields"] if f["key"] == target.get("key") and "span" in f), None)
        if field is None:
            raise EditError(f"field {target.get('key')} of {slide['id']} cannot be edited separately; edit the page source")
        return "\n".join(replace_span(lines, field["span"], md)), slide["id"]
    raise EditError(f"unknown edit kind {kind!r}")


def changed_slides(before: str, after: str) -> list[str]:
    def digest(text: str) -> dict[str, str]:
        try:
            model = parse_draft(text)
        except ValueError:
            return {}
        return {
            s["id"]: json.dumps([s["title"], s["fields"]], ensure_ascii=False, sort_keys=True)
            for c in model["chapters"] for s in c["slides"]
        }
    old, new = digest(before), digest(after)
    return sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))


def page_ids(text: str) -> list[str]:
    return [s["id"] for c in parse_draft(text)["chapters"] for s in c["slides"]]


class DraftStore:
    """The draft file plus its revision log: every change gets a revision number and SHA256."""

    def __init__(self, project: Path, draft_path: Path, state: dict[str, Any] | None) -> None:
        self.project = project
        self.draft_path = draft_path
        self.state = state
        self.revisions_dir = draft_path.parent / "revisions"
        self.log_path = self.revisions_dir / "log.jsonl"
        self.lock = threading.RLock()

    def entries(self) -> list[dict[str, Any]]:
        if not self.log_path.is_file():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @property
    def revision(self) -> int:
        entries = self.entries()
        if entries:
            return int(entries[-1]["revision"])
        return int(((self.state or {}).get("proposal_draft") or {}).get("revision_id") or 0)

    def last_sha(self) -> str | None:
        entries = self.entries()
        return entries[-1]["sha256"] if entries else None

    def edited_slides(self) -> set[str]:
        return {slide for entry in self.entries() if entry["actor"] != "baseline" for slide in entry.get("slides", [])}

    def read(self) -> str:
        return self.draft_path.read_bytes().decode("utf-8")

    def model(self) -> dict[str, Any]:
        with self.lock:
            return model_from_text(self.read(), self.project, self.draft_path, self.state, self.revision, self.edited_slides())

    def _record(self, text: str, actor: str, slides: list[str], note: str) -> dict[str, Any]:
        entry = {
            "revision": self.revision + (0 if actor == "baseline" else 1),
            "sha256": sha256_text(text),
            "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "actor": actor,
            "slides": slides,
            "note": note,
        }
        self.revisions_dir.mkdir(parents=True, exist_ok=True)
        (self.revisions_dir / f"rev-{entry['revision']:06d}.md").write_text(text, encoding="utf-8")
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def ensure_baseline(self) -> None:
        with self.lock:
            if not self.entries():
                self._record(self.read(), "baseline", [], "studio opened")

    def _write(self, text: str) -> None:
        fd, tmp = tempfile.mkstemp(prefix=".draft-", suffix=".md", dir=self.draft_path.parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp, self.draft_path)

    def save(self, target: dict[str, Any], base_sha: str, actor: str = "owner") -> dict[str, Any]:
        with self.lock:
            self.sync_external()
            current = self.read()
            if sha256_text(current) != base_sha:
                raise EditConflict(sha256_text(current))
            updated, slide_id = apply_edit(current, target)
            if updated == current:
                return {"revision": self.revision, "sha256": base_sha, "slides": [], "unchanged": True}
            if page_ids(updated) != page_ids(current):
                raise EditError("编辑内容不能新增、删除或重排页面；页面结构的变更请走页面变更流程")
            self._write(updated)
            label = target.get("kind")
            note = f"{label}:{target.get('key')}" if label == "field" else str(label)
            return self._record(updated, actor, [slide_id] if slide_id else [], note)

    def sync_external(self) -> dict[str, Any] | None:
        """Record a change made to the draft outside the studio (for example by an agent)."""
        with self.lock:
            text = self.read()
            last = self.last_sha()
            if last is None or sha256_text(text) == last:
                return None
            previous = self.revisions_dir / f"rev-{self.revision:06d}.md"
            before = previous.read_text(encoding="utf-8") if previous.is_file() else ""
            return self._record(text, "external", changed_slides(before, text), "draft file changed outside the studio")


def field_label(anchor: str) -> str:
    """'P09:core' -> '核心内容'; 'title:P09' -> '标题'; 'intro:ch01' -> '章节说明'."""
    head, _, tail = anchor.partition(":")
    if head == "title":
        return "标题"
    if head == "intro":
        return "章节说明"
    if head == "body":
        return "整页"
    return FIELD_NAMES.get(tail, anchor)


class CommentStore:
    """Comment threads anchored to quoted text in a page field, kept beside the draft.

    People and agents share one file, so an agent can read open threads and reply
    by writing `comments.json`; the studio picks the change up like a draft edit.
    """

    MAX_TEXT = 4000

    def __init__(self, draft_path: Path) -> None:
        self.path = draft_path.parent / "comments.json"
        self.lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"threads": []}
        return json.loads(self.path.read_text(encoding="utf-8") or '{"threads": []}')

    def digest(self) -> str | None:
        return hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.is_file() else None

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".comments-", suffix=".json", dir=self.path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, self.path)

    @staticmethod
    def _now() -> str:
        return dt.datetime.now().astimezone().isoformat(timespec="seconds")

    def _text(self, value: Any, name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise EditError(f"{name} cannot be empty")
        if len(text) > self.MAX_TEXT:
            raise EditError(f"{name} is longer than {self.MAX_TEXT} characters")
        return text

    def _find(self, data: dict[str, Any], thread_id: str) -> dict[str, Any]:
        for thread in data["threads"]:
            if thread["id"] == thread_id:
                return thread
        raise EditError(f"unknown comment thread {thread_id}")

    def create(self, payload: dict[str, Any], revision: int | None) -> dict[str, Any]:
        with self.lock:
            data = self.load()
            number = max((int(t["id"].split("-")[1]) for t in data["threads"]), default=0) + 1
            author = self._text(payload.get("author") or "Owner", "author")[:40]
            thread = {
                "id": f"C-{number:04d}",
                "slide": str(payload.get("slide") or ""),
                "field": str(payload.get("field") or ""),
                "quote": self._text(payload.get("quote"), "quote")[:500],
                "prefix": str(payload.get("prefix") or "")[-40:],
                "suffix": str(payload.get("suffix") or "")[:40],
                "status": "open",
                "created_at": self._now(),
                "draft_revision": revision,
                "messages": [{"author": author, "at": self._now(), "text": self._text(payload.get("text"), "comment")}],
            }
            data["threads"].append(thread)
            self._write(data)
            return thread

    def reply(self, thread_id: str, text: str, author: str) -> dict[str, Any]:
        with self.lock:
            data = self.load()
            thread = self._find(data, thread_id)
            thread["messages"].append({"author": self._text(author or "Owner", "author")[:40], "at": self._now(), "text": self._text(text, "reply")})
            self._write(data)
            return thread

    def set_status(self, thread_id: str, status: str, author: str) -> dict[str, Any]:
        if status not in {"open", "resolved"}:
            raise EditError("status must be open or resolved")
        with self.lock:
            data = self.load()
            thread = self._find(data, thread_id)
            thread["status"] = status
            thread["status_by"] = (author or "Owner")[:40]
            thread["status_at"] = self._now()
            self._write(data)
            return thread


# ---------- Rendering ----------

def script_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_html(model: dict[str, Any], live: dict[str, Any] | None = None, threads: list[dict[str, Any]] | None = None) -> str:
    template = (ASSET_ROOT / "studio.html").read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": model["title"].replace("<", "&lt;"),
        "{{CSS}}": (ASSET_ROOT / "studio.css").read_text(encoding="utf-8"),
        "{{JS}}": (ASSET_ROOT / "studio.js").read_text(encoding="utf-8").replace("</script", "<\\/script"),
        "{{MODEL_JSON}}": script_json(model),
        "{{MD_JSON}}": script_json({"full": export_markdown(model, "full", threads), "brief": export_markdown(model, "brief")}),
        "{{LIVE_JSON}}": script_json(live),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


# ---------- Local studio server ----------

class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], store: DraftStore) -> None:
        super().__init__(address, StudioHandler)
        self.store = store
        self.comments = CommentStore(store.draft_path)
        self.comments_digest = self.comments.digest()
        self.token = secrets.token_urlsafe(18)
        self.changed = threading.Condition()
        self.latest: dict[str, Any] = {"revision": store.revision, "sha256": store.last_sha(), "slides": []}
        self.stopping = threading.Event()

    def publish(self, entry: dict[str, Any]) -> None:
        with self.changed:
            self.latest = {
                **{k: entry[k] for k in ("revision", "sha256", "slides", "actor") if k in entry},
                "comments": self.latest.get("comments"),
            }
            self.changed.notify_all()

    def publish_comments(self) -> None:
        with self.changed:
            self.comments_digest = self.comments.digest()
            self.latest = {**self.latest, "comments": self.comments_digest}
            self.changed.notify_all()

    def watch(self, interval: float = 0.5) -> None:
        while not self.stopping.wait(interval):
            try:
                entry = self.store.sync_external()
                if entry:
                    self.publish(entry)
                if self.comments.digest() != self.comments_digest:
                    self.publish_comments()
            except (OSError, ValueError):
                continue


class StudioHandler(BaseHTTPRequestHandler):
    server: StudioServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # keep the terminal quiet
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        # Refuse DNS-rebinding style requests that arrive under another host name.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in {"127.0.0.1", "localhost", "::1", self.server.server_address[0]}

    def _token_ok(self, query: dict[str, list[str]]) -> bool:
        supplied = self.headers.get("X-Studio-Token") or (query.get("token") or [""])[0]
        return secrets.compare_digest(supplied, self.server.token)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if not self._host_ok():
            return self._json(403, {"error": "host not allowed"})
        if url.path == "/":
            live = {"token": self.server.token}
            html = render_html(self.server.store.model(), live, self.server.comments.load()["threads"])
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if not self._token_ok(query):
            return self._json(403, {"error": "missing studio token"})
        if url.path == "/api/model":
            return self._json(200, self.server.store.model())
        if url.path == "/api/markdown":
            profile = (query.get("profile") or ["full"])[0]
            text = export_markdown(
                self.server.store.model(), "brief" if profile == "brief" else "full", self.server.comments.load()["threads"]
            )
            return self._send(200, text.encode("utf-8"), "text/markdown; charset=utf-8")
        if url.path == "/api/revisions":
            return self._json(200, self.server.store.entries())
        if url.path == "/api/comments":
            return self._json(200, self.server.comments.load())
        if url.path == "/api/events":
            return self._events()
        return self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if not self._host_ok() or not self._token_ok({}):
            return self._json(403, {"error": "forbidden"})
        if url.path.startswith("/api/comments"):
            return self._comment_post(url.path)
        if url.path != "/api/save":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            entry = self.server.store.save(payload["target"], str(payload["base_sha"]))
        except EditConflict as conflict:
            return self._json(409, {"error": "conflict", "sha256": str(conflict), "model": self.server.store.model()})
        except (EditError, KeyError, json.JSONDecodeError, ValueError) as error:
            return self._json(400, {"error": str(error)})
        if not entry.get("unchanged"):
            self.server.publish(entry)
        return self._json(200, {"entry": entry, "model": self.server.store.model()})

    def _comment_post(self, path: str) -> None:
        comments = self.server.comments
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/comments":
                thread = comments.create(payload, self.server.store.revision)
            elif path == "/api/comments/reply":
                thread = comments.reply(str(payload["id"]), payload.get("text", ""), payload.get("author", ""))
            elif path == "/api/comments/status":
                thread = comments.set_status(str(payload["id"]), str(payload.get("status")), payload.get("author", ""))
            else:
                return self._json(404, {"error": "not found"})
        except (EditError, KeyError, json.JSONDecodeError, ValueError) as error:
            return self._json(400, {"error": str(error)})
        self.server.publish_comments()
        return self._json(200, {"thread": thread, "comments": comments.load()})

    def _events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        seen = self.server.latest.get("sha256")
        seen_comments = self.server.comments_digest
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while not self.server.stopping.is_set():
                with self.server.changed:
                    self.server.changed.wait(timeout=15)
                    latest = dict(self.server.latest)
                sent = False
                if latest.get("sha256") != seen:
                    seen = latest.get("sha256")
                    data = json.dumps(latest, ensure_ascii=False)
                    self.wfile.write(f"event: revision\ndata: {data}\n\n".encode("utf-8"))
                    sent = True
                if latest.get("comments") and latest.get("comments") != seen_comments:
                    seen_comments = latest.get("comments")
                    self.wfile.write(f"event: comments\ndata: {json.dumps({'digest': seen_comments})}\n\n".encode("utf-8"))
                    sent = True
                if not sent:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


def serve(project: Path, draft_arg: str | None, host: str, port: int, open_browser: bool) -> int:
    draft_path, state = load_project(project, draft_arg)
    store = DraftStore(project, draft_path, state)
    store.ensure_baseline()
    server = None
    for candidate in range(port, port + 20):
        try:
            server = StudioServer((host, candidate), store)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit(f"No free port between {port} and {port + 19}")
    watcher = threading.Thread(target=server.watch, daemon=True)
    watcher.start()
    url = f"http://{'127.0.0.1' if host in {'0.0.0.0', '::'} else host}:{server.server_address[1]}/"
    print(f"Draft studio: {url}")
    print(f"Draft: {draft_path}  revision {store.revision}  log {store.log_path}")
    sys.stdout.flush()
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        with server.changed:
            server.changed.notify_all()
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render", help="write the rich read-only draft page")
    render.add_argument("project")
    render.add_argument("--draft")
    render.add_argument("--out", default=DEFAULT_OUT)
    export = sub.add_parser("export-md", help="write clean Markdown")
    export.add_argument("project")
    export.add_argument("--draft")
    export.add_argument("--profile", choices=("full", "brief"), default="full")
    export.add_argument("--out")
    studio = sub.add_parser("serve", help="run the local studio: edit in place, save to the draft, live refresh")
    studio.add_argument("project")
    studio.add_argument("--draft")
    studio.add_argument("--host", default="127.0.0.1")
    studio.add_argument("--port", type=int, default=8765)
    studio.add_argument("--open", action="store_true", help="open the studio in the default browser")
    comments = sub.add_parser("comments", help="list comment threads (open ones by default)")
    comments.add_argument("project")
    comments.add_argument("--draft")
    comments.add_argument("--all", action="store_true", help="include resolved threads")
    comments.add_argument("--json", action="store_true")
    reply = sub.add_parser("reply", help="reply to a comment thread as an agent")
    reply.add_argument("project")
    reply.add_argument("thread")
    reply.add_argument("text")
    reply.add_argument("--draft")
    reply.add_argument("--author", default="Agent")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    if args.command == "serve":
        return serve(project, args.draft, args.host, args.port, args.open)
    if args.command in {"comments", "reply"}:
        draft_path, _ = load_project(project, args.draft)
        store = CommentStore(draft_path)
        if args.command == "reply":
            thread = store.reply(args.thread, args.text, args.author)
            print(f"Replied to {thread['id']} ({thread['slide']} {thread['field']}); the Owner decides whether to resolve it.")
            return 0
        threads = [t for t in store.load()["threads"] if args.all or t["status"] == "open"]
        if args.json:
            print(json.dumps(threads, ensure_ascii=False, indent=2))
            return 0
        for thread in threads:
            print(f"{thread['id']} [{thread['status']}] {thread['slide']} {field_label(thread['field'])}｜“{thread['quote']}”")
            for message in thread["messages"]:
                print(f"    {message['author']} {message['at'][:16].replace('T', ' ')}：{message['text']}")
        if not threads:
            print("No open comment threads.")
        return 0
    model = build_model(project, args.draft)
    threads = CommentStore(load_project(project, args.draft)[0]).load()["threads"]
    slide_count = sum(len(chapter["slides"]) for chapter in model["chapters"])
    if args.command == "render":
        out = Path(args.out)
        out = out if out.is_absolute() else project / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(model, threads=threads), encoding="utf-8")
        print(f"Rendered {len(model['chapters'])} chapter(s), {slide_count} page(s) -> {out}")
    else:
        text = export_markdown(model, args.profile, threads)
        if args.out:
            out = Path(args.out)
            out = out if out.is_absolute() else project / out
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(f"Exported {args.profile} Markdown ({slide_count} page(s)) -> {out}")
        else:
            sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
