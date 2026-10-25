#!/usr/bin/env python3
"""Render the proposal draft as a rich read-only page and export clean Markdown.

Milestone M1 of the proposal draft studio: the Markdown draft stays the only
authority; the HTML page and the exported Markdown are derived views.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


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
    """Feishu exports carry <title> and <callout> tags; map them onto plain Markdown."""
    title_match = FEISHU_TITLE.search(text)
    text = FEISHU_TITLE.sub("", text)
    text = FEISHU_CALLOUT.sub(lambda m: f":::callout\n{m.group(1).strip()}\n:::", text)
    return text, (title_match.group(1).strip() if title_match else None)


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

    def flush_slide() -> None:
        nonlocal current_slide
        if current_slide is not None:
            current_slide.update(split_fields(current_slide.pop("_body"), slide_level))
            current_chapter["slides"].append(current_slide)
            current_slide = None

    for index, line, in_fence in iter_lines_outside_fences(lines):
        heading = None if in_fence else HEADING.match(line)
        if index in slide_starts:
            flush_slide()
            if current_chapter is None:
                current_chapter = new_chapter("未分章", len(chapters))
                chapters.append(current_chapter)
            _, _, slide_id, slide_title = slide_starts[index]
            current_slide = {"id": slide_id, "title": slide_title.strip(), "_body": []}
            continue
        if heading and len(heading.group(1)) == chapter_level and chapter_level >= 1:
            flush_slide()
            current_chapter = new_chapter(heading.group(2), len(chapters))
            chapters.append(current_chapter)
            continue
        if heading and len(heading.group(1)) < chapter_level and title is None:
            title = heading.group(2)
            continue
        if current_slide is not None:
            current_slide["_body"].append(line)
        elif current_chapter is not None:
            current_chapter["intro"].append(line)
        else:
            preface.append(line)
    flush_slide()

    for chapter in chapters:
        chapter["intro_md"] = tidy("\n".join(chapter.pop("intro")))
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


def new_chapter(title: str, index: int) -> dict[str, Any]:
    clean = re.sub(r"^\s*CH\d+\s*[｜|]\s*", "", title).strip()
    return {"id": f"ch{index + 1:02d}", "title": clean or title, "intro": [], "slides": []}


def split_fields(body: list[str], slide_level: int) -> dict[str, Any]:
    """Split one page unit into known fields; keep anything else as 'other'."""
    field_level = slide_level + 1
    buckets: dict[str, list[str]] = {}
    current = "lead"
    has_field_headings = False
    for _, line, in_fence in iter_lines_outside_fences(body):
        heading = None if in_fence else HEADING.match(line)
        if heading and len(heading.group(1)) == field_level:
            name = re.sub(r"\s+", "", heading.group(2))
            if name in FIELD_HEADINGS:
                current = FIELD_HEADINGS[name]
                has_field_headings = True
                buckets.setdefault(current, [])
                continue
        buckets.setdefault(current, []).append(line)
    if not has_field_headings:
        buckets = split_bullet_fields(body)
    elif "lead" in buckets and not re.search(r"!\[", "\n".join(buckets["lead"])):
        buckets["other"] = buckets.pop("lead") + buckets.get("other", [])
    fields = []
    for key in FIELD_ORDER:
        content = tidy("\n".join(buckets.get(key, [])))
        if content:
            fields.append({"key": key, "name": FIELD_NAMES[key], "md": content})
    return {"fields": fields}


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


def export_markdown(model: dict[str, Any], profile: str = "full") -> str:
    keep = None if profile == "full" else BRIEF_FIELDS
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


def build_model(project: Path, draft_arg: str | None) -> dict[str, Any]:
    draft_path, state = load_project(project, draft_arg)
    raw = draft_path.read_bytes()
    model = parse_draft(raw.decode("utf-8"))
    attach_status(model, state)
    draft_state = (state or {}).get("proposal_draft") or {}
    model["meta"] = {
        "source": str(draft_path.relative_to(project)) if draft_path.is_relative_to(project) else str(draft_path),
        "authority": draft_state.get("authority"),
        "revision": draft_state.get("revision_id"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "phase": (state or {}).get("phase"),
        "project_name": (state or {}).get("project_name"),
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if model["title"] == "提案母稿" and model["meta"]["project_name"]:
        model["title"] = model["meta"]["project_name"]
    return model


def script_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_html(model: dict[str, Any]) -> str:
    template = (ASSET_ROOT / "studio.html").read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": model["title"].replace("<", "&lt;"),
        "{{CSS}}": (ASSET_ROOT / "studio.css").read_text(encoding="utf-8"),
        "{{JS}}": (ASSET_ROOT / "studio.js").read_text(encoding="utf-8").replace("</script", "<\\/script"),
        "{{MODEL_JSON}}": script_json(model),
        "{{MD_JSON}}": script_json({"full": export_markdown(model, "full"), "brief": export_markdown(model, "brief")}),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


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
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    model = build_model(project, args.draft)
    slide_count = sum(len(chapter["slides"]) for chapter in model["chapters"])
    if args.command == "render":
        out = Path(args.out)
        out = out if out.is_absolute() else project / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(model), encoding="utf-8")
        print(f"Rendered {len(model['chapters'])} chapter(s), {slide_count} page(s) -> {out}")
    else:
        text = export_markdown(model, args.profile)
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
