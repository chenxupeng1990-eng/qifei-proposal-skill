#!/usr/bin/env python3
"""Validate company proposal phase gates and required project artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import design_review
from draft_studio import SCREEN_CAUTION, check_format, studio_evidence_errors
from proposal_memory import memory_enabled, memory_for_phase, read_signals_receipt, receipt_problem, write_receipt
from validate_assembly_ready import validate_assembly_ready
from validate_deck_spec import png_has_alpha
from validate_design_loop import validate_chapter_report
from validate_json_schema import validate_json_schema
from validate_production_plan import validate_production_plan


PHASES = [
    "intake",
    "requirements",
    "strategy",
    "project_agents",
    "manuscript",
    "full_redteam",
    "content_frozen",
    "visual_direction",
    "visual_sample",
    "design_calibration",
    "design_system",
    "generation",
    "review",
    "speaker_notes",
    "qa",
    "export",
]

GATES = {
    "requirements": ["materials_scope"],
    "strategy": ["materials_scope", "brief_grill", "proposal_brief", "requirements"],
    "project_agents": ["materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline"],
    "manuscript": ["materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline", "project_agents"],
    "full_redteam": ["project_agents"],
    "content_frozen": ["full_redteam", "content_freeze"],
    "visual_direction": ["content_freeze", "brand_visual_sources", "brand_visual_audit"],
    "design_calibration": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction"],
    "design_system": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction", "design_calibration"],
    "generation": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "visual_direction", "design_calibration", "design", "generation_ready"],
    "review": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready"],
    "speaker_notes": ["content_freeze", "design", "final_page_order"],
    "qa": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready", "design_loop", "final_page_order", "speaker_notes"],
    "export": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready", "design_loop", "final_page_order", "speaker_notes", "final_assembly"],
}

MODULE_GATES = {
    "requirements": ["materials_scope"],
    "strategy": ["materials_scope", "brief_grill", "proposal_brief", "requirements"],
    "project_agents": ["materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline"],
    "manuscript": ["materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline", "project_agents"],
    "content_frozen": [
        "materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline",
        "project_agents", "content_freeze",
    ],
    "visual_direction": ["content_freeze"],
    "visual_sample": ["content_freeze", "visual_direction"],
    "design_system": ["content_freeze", "visual_direction"],
    "generation": ["content_freeze", "generation_ready"],
    "review": ["content_freeze", "generation_ready"],
    "qa": ["content_freeze", "generation_ready", "design_loop", "final_page_order"],
    "export": [
        "content_freeze", "generation_ready", "design_loop", "final_page_order",
        "final_assembly",
    ],
}

BRAND_SOURCE_SUFFIXES = {".ai", ".eps", ".jpg", ".jpeg", ".key", ".pdf", ".png", ".ppt", ".pptx", ".svg", ".webp"}
IMAGE2_DRAFT_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_DESIGN_SAMPLE_TYPES = (
    "cover",
    "toc",
    "chapter-type-led",
    "chapter-image-led",
    "chapter-data-led",
    "content-low",
    "content-medium",
    "content-high",
    "content-visual-module",
    "closing",
)
DESIGN_SAMPLE_PROFILES = {
    "compact": (
        "cover",
        "toc",
        "chapter-image-led",
        "content-medium",
        "content-high",
        "closing",
    ),
    "standard": (
        "cover",
        "toc",
        "chapter-type-led",
        "chapter-image-led",
        "content-low",
        "content-medium",
        "content-high",
        "closing",
    ),
    "extended": DEFAULT_DESIGN_SAMPLE_TYPES,
}
DESIGN_PROFILE_RANK = {"compact": 1, "standard": 2, "extended": 3}
CHAPTER_SAMPLE_TYPES = {"chapter-type-led", "chapter-image-led", "chapter-data-led"}
CONTENT_DENSITY_SAMPLE_TYPES = {"content-low", "content-medium", "content-high"}
DESIGN_REQUIRED_MARKERS = (
    "## 6. 设计语言冻结",
    "### 6.1 首页",
    "### 6.2 目录页",
    "### 6.3 章节页系统",
    "### 6.4 内容页系统",
    "### 6.5 结尾感谢页",
    "## 7. 内容页弹性合同",
    "## 8. 透明 PNG 表现层",
    "## 9. 章节批量生成规则",
)
FEISHU_DRAFT_FORMAT_VERSION = "proposal-draft-v2"
# v1 projects predate the single draft format; they keep the looser section check below.
ACCEPTED_DRAFT_FORMAT_VERSIONS = {"proposal-draft-v2", "feishu-proposal-draft-v1"}
FEISHU_PAGE_SECTIONS = (
    "核心内容",
    "逻辑展开",
    "PPT上屏内容",
    "讲解方向",
    "策略与过桥",
    "视觉生成建议",
    "证据与来源",
)
PROJECT_STATE_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "project-state.schema.json"
PLACEHOLDER_PHASES = {
    "PROJECT_AGENTS": "project_agents",
    "MANUSCRIPT": "manuscript",
    "SPEAKER_NOTES": "speaker_notes",
}



CHAPTER_FIELDS = ("本章回答", "逻辑路径", "情绪方向")


def missing_chapter_fields(text: str) -> list[str]:
    """Bold or plain, either colon: "**本章回答：**" and "本章回答：" are the same field."""
    return [
        marker for marker in CHAPTER_FIELDS
        if not re.search(rf"(?m)^\s*(?:[-*]\s+)?(?:\*\*)?\s*{marker}\s*(?:\*\*)?\s*[：:]", text)
    ]

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def is_approved(approvals: dict, key: str) -> bool:
    item = approvals.get(key)
    return (
        isinstance(item, dict)
        and item.get("approved") is True
        and bool(item.get("by"))
        and bool(item.get("at"))
        and bool(item.get("record_id"))
    )


def approved_by_owner(item: dict, owner: str) -> bool:
    by = str(item.get("by") or "").strip()
    return bool(by) and (owner in by or by in owner)


def apply_waivers(state: dict, errors: list[str]) -> list[str]:
    """Drop errors the Proposal Owner explicitly waived; an agent cannot waive a validator error itself."""
    owner = str(state.get("proposal_owner") or "").strip()
    approvals = state.get("approvals") if isinstance(state.get("approvals"), dict) else {}
    owner_records = {
        str(item.get("record_id")) for item in approvals.values()
        if isinstance(item, dict) and item.get("approved") is True and owner and approved_by_owner(item, owner)
    }
    waived = set()
    problems = []
    for index, waiver in enumerate(state.get("validation_waivers") or [], start=1):
        error = str((waiver or {}).get("error") or "").strip()
        record_id = str((waiver or {}).get("record_id") or "").strip()
        if not error or not str((waiver or {}).get("reason") or "").strip():
            problems.append(f"validation_waivers[{index}] needs error, reason and record_id")
        elif record_id not in owner_records:
            problems.append(f"validation_waivers[{index}] record_id {record_id!r} is not an Owner approval; agents cannot waive validator errors")
        else:
            waived.add(error)
    return [e for e in errors if e not in waived] + problems


def final_order_hash(slide_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(slide_ids).encode("utf-8")).hexdigest()


def validate_speaker_notes(project: Path, state: dict) -> list[str]:
    errors: list[str] = []
    notes = state.get("speaker_notes") if isinstance(state.get("speaker_notes"), dict) else {}
    deck_path = project / "deck" / "deck-spec.json"
    try:
        deck = load_json(deck_path)
    except ValueError as exc:
        return [str(exc)]
    slides = deck.get("slides") if isinstance(deck.get("slides"), list) else []
    slide_ids = [str(slide.get("slide_id") or "").strip() for slide in slides if isinstance(slide, dict)]
    if notes.get("status") != "verified":
        errors.append("speaker_notes.status must be verified")
    if notes.get("final_slide_count") != len(slide_ids):
        errors.append("speaker_notes.final_slide_count must match the final deck")
    if notes.get("final_order_hash") != final_order_hash(slide_ids):
        errors.append("speaker_notes.final_order_hash must match the final slide order")
    if state.get("content_authority") == "feishu" and not str(notes.get("feishu_doc_url") or "").strip():
        errors.append("speaker_notes.feishu_doc_url is required when Feishu is the content authority")
    _, backup_error = registered_project_file(project, notes.get("local_backup_path"), "content")
    if backup_error:
        errors.append(f"speaker_notes.local_backup_path: {backup_error}")
    return errors


TEXT_LAYER_COMPONENTS = ("标题组", "编号列表", "数据行", "信息带", "卡片", "章节标记", "来源")


def design_content_errors(text: str) -> list[str]:
    """DESIGN.md must fix the layout system with real values, not just carry the section headings."""
    checks = [
        (re.search(r"\d+\s*列", text) and re.search(r"安全区[^\n]*\d+\s*px", text),
         "网格与安全区（列数、列距和安全区的具体 px）"),
        (re.search(r"正文[^\n]*\d+\s*px", text) and re.search(r"标题[^\n]*\d+\s*px", text),
         "字号表（标题、正文等各层级的具体 px）"),
        (re.search(r"(小于|低于|下限)[^\n]*\d+\s*px[^\n]*(拆页|改写)", text),
         "字号下限与拆页触发（小于多少 px 必须改写或拆页）"),
        (re.search(r"(文字区|文案区|信息区)[^\n]*\d+\s*(%|％)", text), "受保护文字区的位置和画面占比（%）"),
        (sum(name in text for name in TEXT_LAYER_COMPONENTS) >= 5,
         "文字层组件（标题组、编号列表、数据行、信息带、卡片、章节标记、来源中至少 5 种）"),
        (re.search(r"每批[^\n]*\d", text), "分批生成规则（每批几页、先看 montage）"),
        ("母版清单" in text, "母版清单（每类页面对应哪张已确认校准页）"),
        ("孤字" in text and "对齐" in text and re.search(r"压(在|纹理)", text),
         "视觉 QA 清单（孤字、对齐、文字压纹理等逐页检查项）"),
    ]
    errors = [f"Approved DESIGN.md does not fix {label}" for ok, label in checks if not ok]
    errors.extend(product_image_rule_errors(text, "DESIGN.md"))
    return errors


def expression_choice_errors(brief_text: str, task_nature: str | None) -> list[str]:
    """The brief records the user's choice of expression; project-state.json.task_nature must say the same."""
    line = re.search(r"表达方式[：:]\s*(.+)", brief_text)
    if not line:
        return []  # briefs written before the choice was asked
    chosen = line.group(1)
    picked = {"visual_showcase"} if "视觉表现" in chosen else set()
    picked |= {"persuasive"} if "强逻辑" in chosen else set()
    if len(picked) != 1:
        return ["proposal brief 表达方式 must name one choice: 强逻辑叙述 or 视觉表现力"]
    expected = picked.pop()
    if (task_nature or "persuasive") != expected:
        return [f"proposal brief chose {chosen.strip()[:20]} but project-state.json task_nature is {task_nature or 'persuasive'}; "
                f"set task_nature to {expected}"]
    return []


# Draft fields that never go on screen; seeing their label on a sample means the draft was pasted in.
OFF_SCREEN_LABELS = ("核心内容", "逻辑展开", "讲解方向", "讲解词", "演讲任务", "策略与过桥", "视觉生成建议", "证据与来源")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class SampleText(HTMLParser):
    """Visible text inside each [data-design-sample] element, skipping [data-screen-ignore] parts."""

    def __init__(self) -> None:
        super().__init__()
        self.samples: list[tuple[str, list[str]]] = []
        self.stack: list[str] = []  # "sample", "skip" or "" per open element

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_TAGS:
            return
        names = dict(attrs)
        if tag in {"script", "style"} or "data-screen-ignore" in names:
            self.stack.append("skip")
        elif "data-design-sample" in names and "sample" not in self.stack:
            self.samples.append((str(names["data-design-sample"]), []))
            self.stack.append("sample")
        else:
            self.stack.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID_TAGS and self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if "sample" in self.stack and "skip" not in self.stack and data.strip():
            self.samples[-1][1].append(data.strip())


CALIBRATION_CHECK = "evidence/calibration-production-check.md"


def calibration_production_check_errors(project: Path, calibration: dict, sample_types: tuple[str, ...]) -> list[str]:
    """Before the calibration is approved, each sample is checked against the formal production rules
    (page-production-loop.md), so a sample that production could not follow is not frozen as a master."""
    path, error = registered_project_file(project, calibration.get("production_check_path") or CALIBRATION_CHECK, "evidence")
    if error or not path:
        return [f"design_calibration.production_check_path: {error or 'missing'} "
                f"(write {CALIBRATION_CHECK}: each sample against the formal production rules)"]
    text = path.read_text(encoding="utf-8")
    return [f"Calibration production check does not cover sample type: {sample_type}"
            for sample_type in sample_types if sample_type not in text]


def calibration_screen_errors(html: str) -> list[str]:
    """A calibration sample carries only on-screen text: no draft field labels, no internal caution
    wording. Notes for the reviewer go in an element marked data-screen-ignore."""
    parser = SampleText()
    parser.feed(html)
    errors = []
    for sample_type, chunks in parser.samples:
        text = "\n".join(chunks)
        for label in OFF_SCREEN_LABELS:
            if label in text:
                errors.append(f"Design calibration sample {sample_type} shows the draft field label {label}; "
                              "only PPT上屏内容 goes on a sample (reviewer notes go in data-screen-ignore)")
        for phrase in sorted({m.group(0) for m in SCREEN_CAUTION.finditer(text)}):
            errors.append(f"Design calibration sample {sample_type} shows internal caution wording \"{phrase}\"; keep it off screen")
    return errors


# Wording that keeps official product images out of generation (see design-and-generation.md §7).
PRODUCT_POST_ONLY = re.compile(
    r"产品(?:图|包装)?[^。\n]{0,20}(?:只能|仅|一律|统一)[^。\n]{0,12}(?:后期|贴回|后贴|合成|叠加)"
    r"|生成图只(?:承担|负责)[^。\n]{0,6}(?:场景|背景|材质)"
)


def product_image_rule_errors(text: str, label: str) -> list[str]:
    """Official product images go into generation as references; only the Logo is laid on afterwards.
    A rule that sends every product image to post-production, or leaves "产品图" without saying it
    is a generation reference, makes products float over the scene without shared light."""
    errors = []
    match = PRODUCT_POST_ONLY.search(text)
    if match:
        errors.append(f"{label} keeps product images out of generation (\"{match.group(0)}\"); "
                      "official product images go in as generation references, only the Logo is laid on afterwards")
    elif "产品图" in text and not re.search(r"产品图[^。\n]{0,40}参考图|参考图[^。\n]{0,40}产品图", text):
        errors.append(f"{label} mentions 产品图 without saying they enter generation as reference images")
    return errors


VISUAL_REVIEW_ITEMS = ("single_focus", "orphans", "alignment", "text_on_texture", "overflow", "hierarchy")


def runtime_gap_errors(state: dict, phase_index: int) -> list[str]:
    """Every capability gap doctor recorded must be filled (rerun doctor) or explicitly accepted by the Owner."""
    runtime = state.get("runtime") if isinstance(state.get("runtime"), dict) else None
    if runtime is None or phase_index < PHASES.index("strategy"):
        return []
    owner = str(state.get("proposal_owner") or "").strip()
    decisions = state.get("runtime_decisions") if isinstance(state.get("runtime_decisions"), dict) else {}
    errors = []
    for gap in runtime.get("gaps") or []:
        decision = decisions.get(gap)
        if not isinstance(decision, dict):
            errors.append(
                f"runtime: 能力缺口 {gap} 还没有问过 Owner；先按 doctor.py 列出的办法问用户能否补齐，补齐后重跑 "
                f"doctor.py --project，用户明确选择暂不补齐时运行 doctor.py --project <项目目录> --accept-gap {gap} --by <Owner>"
            )
        elif owner and not approved_by_owner(decision, owner):
            errors.append(f"runtime: 接受缺口 {gap} 的决定必须来自 Owner {owner}")
    return errors


def validate_visual_review(project: Path, state: dict) -> list[str]:
    """An independent agent reviewed every final page against the layout checklist, on the exact PNGs
    in the assembly-ready library, with the script-measured layout check attached."""
    review = state.get("visual_review") if isinstance(state.get("visual_review"), dict) else {}
    report_path, report_error = registered_project_file(project, review.get("report_path"), "reviews/visual")
    if report_error:
        return [f"visual_review.report_path: {report_error}; an independent agent must review the final pages"]
    report = load_json(report_path)
    errors = []
    if review.get("independent_agent") is not True or report.get("independent_agent") is not True:
        errors.append("visual_review must be done by an independent review agent")
    agent_id = str(report.get("review_agent_id") or "").strip()
    if not agent_id or agent_id != str(review.get("review_agent_id") or ""):
        errors.append("visual_review review_agent_id must be set and match its report")
    if report.get("status") != "passed":
        errors.append("visual_review report status must be passed")
    layout_path, layout_error = registered_project_file(project, report.get("layout_check_report"), "reviews/visual")
    if layout_error:
        errors.append(f"visual_review.layout_check_report: {layout_error}; attach check_page_layout.mjs output")
    else:
        layout = load_json(layout_path)
        measured = sum(len(p.get("problems") or []) for p in (layout.get("pages") or {}).values())
        if measured:
            errors.append(f"visual_review: the layout check still reports {measured} problem(s)")
    try:
        manifest = load_json(project / "deck" / "assembly-ready" / "manifest.json")
    except ValueError as exc:
        return errors + [str(exc)]
    ready = {str(p.get("slide_id")): p.get("ready_png_sha256") for p in manifest.get("pages") or [] if isinstance(p, dict)}
    reviewed = {str(p.get("slide_id")): p for p in report.get("pages") or [] if isinstance(p, dict)}
    for slide_id, png_hash in ready.items():
        page = reviewed.get(slide_id)
        if not page:
            errors.append(f"visual_review: {slide_id} was not reviewed")
            continue
        if page.get("png_sha256") != png_hash:
            errors.append(f"visual_review: {slide_id} changed after the review; review it again")
        missing = [item for item in VISUAL_REVIEW_ITEMS if item not in (page.get("checks") or {})]
        if missing:
            errors.append(f"visual_review: {slide_id} misses checklist items {', '.join(missing)}")
    return errors


def validate_final_check(project: Path, state: dict) -> list[str]:
    """The low-level final check (final_check.py) must pass for the current page order before export,
    and again on every exported PPTX."""
    check = state.get("final_check") if isinstance(state.get("final_check"), dict) else {}
    report_path, report_error = registered_project_file(project, check.get("report_path"), "reviews/qa")
    if report_error:
        return [f"final_check.report_path: {report_error}; run scripts/final_check.py"]
    report = load_json(report_path)
    errors = []
    if report.get("status") != "passed":
        errors.append("final_check report status must be passed")
    try:
        deck = load_json(project / "deck" / "deck-spec.json")
        order = [str(s.get("slide_id") or "").strip() for s in deck.get("slides") or [] if isinstance(s, dict)]
        if report.get("final_order_hash") != final_order_hash(order):
            errors.append("final_check was run for another page order; run it again")
    except ValueError as exc:
        errors.append(str(exc))
    if not str(report.get("proofread") or "").strip():
        errors.append("final_check must record the proofread for typos")
    # Editable PPTX files carry a compile report beside them; image-only previews have no text to check.
    exports = [p for p in sorted((project / "exports").glob("*.pptx")) if p.with_suffix(".report.json").is_file()] \
        if (project / "exports").is_dir() else []
    if exports and (report.get("pptx") or {}).get("status") != "passed":
        errors.append("exported PPTX has not passed the on-screen text check; run final_check.py --pptx")
    return errors


def unresolved_required_placeholders(text: str, phase: str) -> list[str]:
    current_index = PHASES.index(phase)
    unresolved: list[str] = []
    for required_phase, field in re.findall(r"\{\{REQUIRED_AT_([A-Z_]+):([A-Z0-9_]+)\}\}", text):
        target = PLACEHOLDER_PHASES.get(required_phase)
        if target and current_index >= PHASES.index(target):
            unresolved.append(f"{required_phase}:{field}")
    return unresolved


def registered_project_file(project: Path, value: object, required_root: str) -> tuple[Path | None, str | None]:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None, "path is empty"
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        return None, f"path must be project-relative: {raw}"
    project_root = project.resolve()
    required = (project_root / required_root).resolve()
    resolved = (project_root / relative).resolve()
    try:
        resolved.relative_to(required)
    except ValueError:
        return None, f"path must stay under {required_root}/: {raw}"
    if not resolved.is_file():
        return None, f"registered file does not exist: {raw}"
    return resolved, None


def validate_verified_feishu_draft(project: Path, state: dict, chapters: list[dict]) -> list[str]:
    errors: list[str] = []
    draft = state.get("proposal_draft") if isinstance(state.get("proposal_draft"), dict) else {}
    if not draft:
        return ["full_redteam requires a verified Feishu proposal draft or a registered studio draft; local Markdown is only a temporary fallback"]
    authority = draft.get("authority")
    if authority not in {"feishu", "studio"} or draft.get("status") != "verified":
        errors.append("proposal_draft must use authority feishu or studio with status verified before full_redteam")
    if authority == "studio" and draft.get("format_version") != FEISHU_DRAFT_FORMAT_VERSION:
        errors.append(f"studio drafts must use format_version {FEISHU_DRAFT_FORMAT_VERSION}")
    if draft.get("format_version") not in ACCEPTED_DRAFT_FORMAT_VERSIONS:
        errors.append(f"proposal_draft.format_version must be {FEISHU_DRAFT_FORMAT_VERSION}")
    required = ("feishu_doc_url", "document_id", "last_verified_at") if authority != "studio" else ("last_verified_at",)
    for field in required:
        if not str(draft.get(field) or "").strip():
            errors.append(f"proposal_draft.{field} is required")
    revision_id = draft.get("revision_id")
    if not isinstance(revision_id, int) or revision_id <= 0:
        errors.append("proposal_draft.revision_id must be a positive integer from Feishu reread")

    snapshot_path, snapshot_error = registered_project_file(
        project,
        draft.get("verified_snapshot_path"),
        "content/draft" if authority == "studio" else "content/feishu",
    )
    snapshot_text = ""
    if snapshot_error:
        errors.append(f"proposal_draft.verified_snapshot_path: {snapshot_error}")
    elif snapshot_path:
        snapshot_bytes = snapshot_path.read_bytes()
        snapshot_text = snapshot_bytes.decode("utf-8")
        actual_hash = hashlib.sha256(snapshot_bytes).hexdigest()
        if draft.get("verified_snapshot_sha256") != actual_hash:
            errors.append("proposal_draft.verified_snapshot_sha256 does not match the reread snapshot")
        if authority == "studio":
            errors.extend(studio_evidence_errors(project, draft, snapshot_path, chapters))

    expected_slide_ids = [
        str(slide_id)
        for chapter in chapters
        for slide_id in (chapter.get("slides") if isinstance(chapter.get("slides"), list) else [])
    ]
    verified_slide_ids = [
        str(slide_id)
        for slide_id in (draft.get("verified_slide_ids") if isinstance(draft.get("verified_slide_ids"), list) else [])
    ]
    if verified_slide_ids != expected_slide_ids:
        errors.append("proposal_draft.verified_slide_ids must exactly match the confirmed chapter slide order")

    if snapshot_text and draft.get("format_version") == FEISHU_DRAFT_FORMAT_VERSION:
        for issue in check_format(snapshot_text):
            errors.append(f"{issue['page']}: draft format: {issue['message']}")
    if snapshot_text:
        # A visual_showcase task (brand book) has no persuasion chain to declare per chapter.
        for marker in missing_chapter_fields(snapshot_text) if state.get("task_nature") != "visual_showcase" else []:
            errors.append(f"verified Feishu proposal draft is missing chapter field: {marker}")
        for slide_id in expected_slide_ids:
            match = re.search(
                rf"(?ms)^##\s+{re.escape(slide_id)}(?:\b|｜|\s).*?(?=^##\s+|^#\s+|\Z)",
                snapshot_text,
            )
            if not match:
                errors.append(f"verified Feishu proposal draft is missing slide section: {slide_id}")
                continue
            page_text = match.group(0)
            for section in FEISHU_PAGE_SECTIONS:
                heading_field = re.search(rf"(?m)^###\s+{re.escape(section)}\s*$", page_text)
                bold_paragraph_field = re.search(
                    rf"(?m)^\*\*{re.escape(section)}[：:]\*\*",
                    page_text,
                )
                if not heading_field and not bold_paragraph_field:
                    errors.append(f"{slide_id}: verified Feishu proposal draft is missing section: {section}")
        if re.search(r"(?m)^#{2,4}\s*(完整讲稿|逐字稿|Speaker Notes)", snapshot_text, re.IGNORECASE):
            errors.append("verified Feishu proposal draft must not contain the final full speaker script")
    return errors


def validate_visual_direction_drafts(
    project: Path,
    state: dict,
    approvals: dict,
    *,
    minimum_directions: int = 2,
) -> list[str]:
    errors: list[str] = []
    visual_direction = state.get("visual_direction") if isinstance(state.get("visual_direction"), dict) else {}
    directions = visual_direction.get("directions") if isinstance(visual_direction.get("directions"), list) else []
    if not minimum_directions <= len(directions) <= 3:
        errors.append(
            f"visual_direction.directions must contain {minimum_directions}-3 generated visual directions"
        )
        return errors

    direction_ids: list[str] = []
    visual_theses: list[str] = []
    for index, direction in enumerate(directions, start=1):
        scope = f"visual_direction.directions[{index}]"
        if not isinstance(direction, dict):
            errors.append(f"{scope} must be an object")
            continue
        direction_id = str(direction.get("direction_id") or "").strip()
        if not direction_id:
            errors.append(f"{scope}.direction_id is required")
        else:
            direction_ids.append(direction_id)
        for field in ("name", "visual_thesis", "visual_family_id"):
            value = str(direction.get(field) or "").strip()
            if not value:
                errors.append(f"{scope}.{field} is required")
            elif field == "visual_thesis":
                visual_theses.append(value)
        representative_slide_ids = (
            direction.get("representative_slide_ids")
            if isinstance(direction.get("representative_slide_ids"), list)
            else []
        )
        if not [item for item in representative_slide_ids if str(item).strip()]:
            errors.append(f"{scope}.representative_slide_ids must identify at least one real sample page")

        assets = direction.get("image2_assets") if isinstance(direction.get("image2_assets"), list) else []
        if not assets:
            errors.append(f"{scope} must register at least one real Image2 draft")
            continue
        for asset_index, asset in enumerate(assets, start=1):
            asset_scope = f"{scope}.image2_assets[{asset_index}]"
            if not isinstance(asset, dict):
                errors.append(f"{asset_scope} must be an object")
                continue
            if str(asset.get("generator") or "").strip().lower() != "image2":
                errors.append(f"{asset_scope}.generator must be image2")
            asset_path, asset_error = registered_project_file(
                project,
                asset.get("asset_path"),
                "assets/image2",
            )
            if asset_error:
                errors.append(f"{asset_scope}.asset_path: {asset_error}")
            elif asset_path and asset_path.suffix.lower() not in IMAGE2_DRAFT_SUFFIXES:
                errors.append(f"{asset_scope}.asset_path must be PNG, JPG, or WebP")
            _, prompt_error = registered_project_file(
                project,
                asset.get("prompt_record"),
                "assets/image2",
            )
            if prompt_error:
                errors.append(f"{asset_scope}.prompt_record: {prompt_error}")

    if len(direction_ids) != len(set(direction_ids)):
        errors.append("visual_direction.direction_id values must be unique")
    if len(visual_theses) != len(set(visual_theses)):
        errors.append("visual_direction.visual_thesis values must describe distinct visual propositions")

    selected_direction_id = str(visual_direction.get("selected_direction_id") or "").strip()
    if not selected_direction_id or selected_direction_id not in direction_ids:
        errors.append("visual_direction.selected_direction_id must reference one generated direction")
    approval = approvals.get("visual_direction") if isinstance(approvals.get("visual_direction"), dict) else {}
    approval_record_id = str(visual_direction.get("approval_record_id") or "").strip()
    if is_approved(approvals, "visual_direction") and (
        not approval_record_id or approval.get("record_id") != approval_record_id
    ):
        errors.append("visual_direction.approval_record_id must match its approval record")
    return errors


MEMORY_ERROR = "proposal memory: "


def validate_project(project: Path) -> list[str]:
    errors: list[str] = []
    state_path = project / "project-state.json"
    try:
        state = load_json(state_path)
    except ValueError as exc:
        return [str(exc)]

    if state.get("schema_version") is not None:
        schema = load_json(PROJECT_STATE_SCHEMA)
        schema_errors = validate_json_schema(state, schema)
        if schema_errors:
            return [f"project-state schema: {error}" for error in schema_errors]

    phase = state.get("phase")
    if phase not in PHASES:
        errors.append(f"Unknown phase: {phase!r}")
        return errors

    task_mode = str(state.get("task_mode") or "full_deck").strip()
    full_deck = task_mode == "full_deck"
    module_mode = task_mode in {"inherited_module", "standalone_module"}
    owner = str(state.get("proposal_owner") or "").strip()
    if not owner:
        errors.append("project-state.json is missing proposal_owner")

    approvals = state.get("approvals") if isinstance(state.get("approvals"), dict) else {}
    required_gates = list(GATES.get(phase, []) if full_deck else MODULE_GATES.get(phase, []))
    if task_mode == "standalone_module" and PHASES.index(phase) >= PHASES.index("generation"):
        required_gates.extend(("visual_direction", "design"))
    for gate in required_gates:
        if not is_approved(approvals, gate):
            errors.append(f"Phase {phase} requires approved gate: {gate}")
        elif owner and not approved_by_owner(approvals[gate], owner):
            errors.append(f"Approval {gate} was recorded by {approvals[gate].get('by')!r}; only the Proposal Owner ({owner}) approves gates")

    phase_index = PHASES.index(phase)
    if phase_index >= PHASES.index("strategy"):
        brief_path = project / "content" / "proposal-brief.md"
        if not brief_path.is_file():
            errors.append("content/proposal-brief.md is required before strategy")
        else:
            brief_text = brief_path.read_text(encoding="utf-8")
            if any(marker in brief_text for marker in ("待确认", "待填写")):
                errors.append("Approved proposal brief still contains unresolved placeholder markers")
            errors.extend(expression_choice_errors(brief_text, state.get("task_nature")))
        for gate in ("brief_grill", "proposal_brief"):
            if not is_approved(approvals, gate):
                message = f"Phase {phase} requires approved gate: {gate}"
                if message not in errors:
                    errors.append(message)
    if phase_index >= PHASES.index("project_agents"):
        agents_path = project / "AGENTS.md"
        if not agents_path.is_file():
            errors.append("AGENTS.md is required after outline confirmation")
        else:
            placeholders = unresolved_required_placeholders(agents_path.read_text(encoding="utf-8"), phase)
            for placeholder in placeholders:
                errors.append(f"AGENTS.md has unresolved phase placeholder: {placeholder}")
    if phase_index >= PHASES.index("design_system") and not (project / "DESIGN.md").is_file():
        errors.append("DESIGN.md is required after design calibration confirmation")
    if full_deck and phase_index >= PHASES.index("design_calibration"):
        calibration = state.get("design_calibration") if isinstance(state.get("design_calibration"), dict) else {}
        calibration_value = calibration.get("path") or "deck/design-calibration.html"
        calibration_path, calibration_error = registered_project_file(project, calibration_value, "deck")
        planned_slide_count = calibration.get("planned_slide_count")
        if not isinstance(planned_slide_count, int) or planned_slide_count <= 0:
            errors.append("design_calibration.planned_slide_count must be a positive integer")
            planned_slide_count = 0
        expected_profile = (
            "compact" if planned_slide_count and planned_slide_count <= 24
            else "standard" if planned_slide_count and planned_slide_count <= 60
            else "extended"
        )
        configured_profile = str(calibration.get("profile") or "auto").strip().lower()
        profile = expected_profile if configured_profile == "auto" else configured_profile
        if profile not in DESIGN_SAMPLE_PROFILES:
            errors.append("design_calibration.profile must be auto, compact, standard, or extended")
            profile = expected_profile
        elif DESIGN_PROFILE_RANK[profile] < DESIGN_PROFILE_RANK[expected_profile]:
            errors.append(
                f"design_calibration.profile {profile} is too small for {planned_slide_count} planned slides; "
                f"use at least {expected_profile}"
            )
            profile = expected_profile
        if calibration_error:
            errors.append(f"design_calibration.path: {calibration_error}")
        elif calibration_path:
            calibration_text = calibration_path.read_text(encoding="utf-8")
            configured_types = calibration.get("required_sample_types")
            required_types = (
                configured_types
                if isinstance(configured_types, list) and configured_types
                else DESIGN_SAMPLE_PROFILES[profile]
            )
            required_types = tuple(dict.fromkeys(str(item).strip() for item in required_types if str(item).strip()))
            minimum_count = len(DESIGN_SAMPLE_PROFILES[profile])
            minimum_chapter_variants = {"compact": 1, "standard": 2, "extended": 3}[profile]
            minimum_content_densities = {"compact": 2, "standard": 3, "extended": 3}[profile]
            if len(required_types) < minimum_count:
                errors.append(
                    f"design_calibration.required_sample_types needs at least {minimum_count} types for {profile}"
                )
            for essential in ("cover", "toc", "closing"):
                if essential not in required_types:
                    errors.append(f"design_calibration.required_sample_types must include {essential}")
            if len(CHAPTER_SAMPLE_TYPES.intersection(required_types)) < minimum_chapter_variants:
                errors.append(
                    "design_calibration.required_sample_types does not cover enough chapter-page variants"
                )
            if len(CONTENT_DENSITY_SAMPLE_TYPES.intersection(required_types)) < minimum_content_densities:
                errors.append(
                    "design_calibration.required_sample_types does not cover enough content-density levels"
                )
            for sample_type in required_types:
                marker_double = f'data-design-sample="{sample_type}"'
                marker_single = f"data-design-sample='{sample_type}'"
                if marker_double not in calibration_text and marker_single not in calibration_text:
                    errors.append(f"Design calibration is missing required sample type: {sample_type}")
            errors.extend(calibration_screen_errors(calibration_text))
            if phase_index >= PHASES.index("design_system"):
                errors.extend(calibration_production_check_errors(project, calibration, required_types))
            if "content-visual-module" in required_types:
                alpha_value = calibration.get("alpha_sample_path")
                alpha_path, alpha_error = registered_project_file(project, alpha_value, "assets")
                if alpha_error:
                    errors.append(f"design_calibration.alpha_sample_path: {alpha_error}")
                elif alpha_path:
                    if alpha_path.suffix.lower() != ".png" or not png_has_alpha(alpha_path):
                        errors.append("design_calibration.alpha_sample_path must be a PNG with a real alpha channel")
                    normalized_alpha = str(alpha_value).strip().replace("\\", "/")
                    if normalized_alpha not in calibration_text:
                        errors.append("Design calibration HTML must reference design_calibration.alpha_sample_path")
        if phase_index >= PHASES.index("design_system"):
            approval = approvals.get("design_calibration") if isinstance(approvals.get("design_calibration"), dict) else {}
            approval_id = str(calibration.get("approval_record_id") or "").strip()
            if is_approved(approvals, "design_calibration") and (not approval_id or approval.get("record_id") != approval_id):
                errors.append("design_calibration.approval_record_id must match its approval record")
            for thread in design_review.open_calibration_threads(project):
                errors.append(f"design calibration sample {thread['slide']} has an open design comment {thread['id']}; resolve it before approving")
    if phase_index >= PHASES.index("generation"):
        for relative in ("deck/deck-spec.json", "deck/slide-contracts.json", "deck/design-tokens.json"):
            if not (project / relative).is_file():
                errors.append(f"Generation requires {relative}")
        errors.extend(validate_production_plan(project, state))

    if full_deck and phase_index >= PHASES.index("visual_direction"):
        brand_visual = state.get("brand_visual") if isinstance(state.get("brand_visual"), dict) else {}
        scope_decision = str(brand_visual.get("scope_decision") or "").strip()
        if scope_decision not in {"official_brand", "visual_proxy"}:
            errors.append("brand_visual.scope_decision must be official_brand or visual_proxy")
        if not str(brand_visual.get("project_brand_name") or "").strip():
            errors.append("brand_visual.project_brand_name is required")
        if scope_decision == "visual_proxy" and not str(brand_visual.get("reference_brand_name") or "").strip():
            errors.append("brand_visual.reference_brand_name is required for visual_proxy")
        source_ids = brand_visual.get("source_ids") if isinstance(brand_visual.get("source_ids"), list) else []
        source_files = brand_visual.get("source_files") if isinstance(brand_visual.get("source_files"), list) else []
        source_ids = [str(item).strip() for item in source_ids if str(item).strip()]
        if not source_ids:
            errors.append("brand_visual.source_ids must register at least one official brand source")
        if not source_files:
            errors.append("brand_visual.source_files must register uploaded official brand visual files")
        for index, value in enumerate(source_files, start=1):
            source_path, source_error = registered_project_file(project, value, "inputs/brand-official")
            if source_error:
                errors.append(f"brand_visual.source_files[{index}]: {source_error}")
            elif source_path and source_path.suffix.lower() not in BRAND_SOURCE_SUFFIXES:
                errors.append(f"brand_visual.source_files[{index}] is not a supported visual reference: {source_path.name}")

        audit_value = brand_visual.get("audit_path") or "evidence/brand-visual-audit.md"
        audit_path, audit_error = registered_project_file(project, audit_value, "evidence")
        if audit_error:
            errors.append(f"brand_visual.audit_path: {audit_error}")
        elif audit_path:
            audit_text = audit_path.read_text(encoding="utf-8")
            for source_id in source_ids:
                if source_id not in audit_text:
                    errors.append(f"Brand visual audit does not cite source id: {source_id}")
            if any(marker in audit_text for marker in ("待确认", "待填写")):
                errors.append("Approved brand visual audit still contains unresolved placeholder markers")
            errors.extend(product_image_rule_errors(audit_text, "Brand visual audit"))

        for gate in ("brand_visual_sources", "brand_visual_audit"):
            if not is_approved(approvals, gate):
                message = f"Phase {phase} requires approved gate: {gate}"
                if message not in errors:
                    errors.append(message)

        if phase_index >= PHASES.index("generation"):
            incorporation = approvals.get("brand_visual_incorporation")
            incorporation_id = str(brand_visual.get("design_incorporation_record_id") or "").strip()
            if not is_approved(approvals, "brand_visual_incorporation"):
                message = f"Phase {phase} requires approved gate: brand_visual_incorporation"
                if message not in errors:
                    errors.append(message)
            elif not incorporation_id or incorporation.get("record_id") != incorporation_id:
                errors.append("brand_visual.design_incorporation_record_id must match its approval record")
            design_path = project / "DESIGN.md"
            if design_path.is_file():
                design_text = design_path.read_text(encoding="utf-8")
                for source_id in source_ids:
                    if source_id not in design_text:
                        errors.append(f"DESIGN.md does not cite brand visual source id: {source_id}")
                if any(marker in design_text for marker in ("待确认", "待填写")):
                    errors.append("Approved DESIGN.md still contains unresolved placeholder markers")
                for marker in DESIGN_REQUIRED_MARKERS:
                    if marker not in design_text:
                        errors.append(f"Approved DESIGN.md is missing required section: {marker}")
                errors.extend(design_content_errors(design_text))
            tokens_path = project / "deck" / "design-tokens.json"
            if tokens_path.is_file():
                try:
                    tokens = load_json(tokens_path)
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    brand_tokens = tokens.get("brand_visual") if isinstance(tokens.get("brand_visual"), dict) else {}
                    token_source_ids = brand_tokens.get("source_ids") if isinstance(brand_tokens.get("source_ids"), list) else []
                    for source_id in source_ids:
                        if source_id not in token_source_ids:
                            errors.append(f"design-tokens.json does not cite brand visual source id: {source_id}")
                    palette = brand_tokens.get("palette") if isinstance(brand_tokens.get("palette"), list) else []
                    if not palette:
                        errors.append("design-tokens.json brand_visual.palette must include the audited brand palette")
                    allowed_classes = {"official_explicit", "sampled_from_official", "proposal_choice"}
                    for index, item in enumerate(palette, start=1):
                        if not isinstance(item, dict) or item.get("classification") not in allowed_classes:
                            errors.append(f"design-tokens.json brand_visual.palette[{index}] has invalid classification")
                    page_system = tokens.get("page_system") if isinstance(tokens.get("page_system"), dict) else {}
                    if len(page_system.get("chapter_variants") or []) < 3:
                        errors.append("design-tokens.json page_system.chapter_variants must include at least three chapter variants")
                    if set(page_system.get("density_levels") or []) != {"low", "medium", "high"}:
                        errors.append("design-tokens.json page_system.density_levels must include low, medium, and high")
                    alpha_tokens = tokens.get("transparent_png") if isinstance(tokens.get("transparent_png"), dict) else {}
                    # Transparent modules are optional on top of the full-page base; when used they need real alpha.
                    if alpha_tokens.get("enabled") is True and alpha_tokens.get("alpha_required") is not True:
                        errors.append("design-tokens.json transparent_png modules, when enabled, must require real alpha channels")

    if full_deck and (phase_index >= PHASES.index("design_calibration") or is_approved(approvals, "visual_direction")):
        errors.extend(validate_visual_direction_drafts(project, state, approvals))
    if task_mode == "standalone_module" and (
        phase_index >= PHASES.index("visual_sample") or is_approved(approvals, "visual_direction")
    ):
        errors.extend(validate_visual_direction_drafts(
            project,
            state,
            approvals,
            minimum_directions=1,
        ))

    chapters = state.get("chapters") if isinstance(state.get("chapters"), list) else []
    if full_deck and phase_index >= PHASES.index("full_redteam"):
        errors.extend(validate_verified_feishu_draft(project, state, chapters))
        if not chapters:
            errors.append("At least one chapter is required before full_redteam")
        for index, chapter in enumerate(chapters, start=1):
            chapter_id = chapter.get("chapter_id") or f"chapter-{index}"
            if chapter.get("manuscript_confirmed") is not True:
                errors.append(f"{chapter_id}: manuscript is not fully confirmed")
            if not chapter.get("confirmation_record_id"):
                errors.append(f"{chapter_id}: missing confirmation_record_id")
            slides = chapter.get("slides") if isinstance(chapter.get("slides"), list) else []
            if not slides:
                errors.append(f"{chapter_id}: slides must be non-empty before full-draft review")
            source_value = chapter.get("source_path")
            _, source_error = registered_project_file(project, source_value, "content/chapters")
            if source_error:
                errors.append(f"{chapter_id}.source_path: {source_error}")

    full_review_required = full_deck and (
        phase_index >= PHASES.index("content_frozen") or is_approved(approvals, "full_redteam")
    )
    if full_review_required:
        full_review = state.get("full_redteam") if isinstance(state.get("full_redteam"), dict) else {}
        report_value = full_review.get("report_path")
        report_path, report_error = registered_project_file(project, report_value, "reviews/redteam")
        if report_error:
            errors.append(f"full_redteam.report_path: {report_error}")
        review_agent_id = str(full_review.get("review_agent_id") or "").strip()
        if (
            full_review.get("independent_agent") is not True
            or not review_agent_id
            or review_agent_id.lower().startswith(("local-main", "main-agent"))
        ):
            errors.append("full_redteam requires an independent review agent")
        if report_path:
            try:
                report = load_json(report_path)
            except ValueError as exc:
                errors.append(str(exc))
            else:
                if report.get("status") != "passed":
                    errors.append("full_redteam report status must be passed")
                if report.get("independent_agent") is not True:
                    errors.append("full_redteam report must confirm independent_agent")
                if str(report.get("review_agent_id") or "").strip() != review_agent_id:
                    errors.append("full_redteam review_agent_id must match its report")

    if phase_index >= PHASES.index("qa"):
        for index, chapter in enumerate(chapters, start=1):
            chapter_id = chapter.get("chapter_id") or f"chapter-{index}"
            if chapter.get("design_loop_passed") is not True:
                errors.append(f"{chapter_id}: design loop has not passed")
                continue
            if not chapter.get("design_loop_report"):
                errors.append(f"{chapter_id}: missing design_loop_report")
                continue
            for loop_error in validate_chapter_report(project, str(chapter_id)):
                errors.append(loop_error)

    if (full_deck and phase_index >= PHASES.index("qa")) or is_approved(approvals, "speaker_notes"):
        errors.extend(validate_speaker_notes(project, state))

    if module_mode:
        module = state.get("module_context") if isinstance(state.get("module_context"), dict) else {}
        if not module:
            errors.append("module task modes require module_context")
        if task_mode == "standalone_module" and state.get("content_authority") not in {"local", "feishu", "studio"}:
            errors.append("standalone_module content_authority must be local, feishu or studio")
        if task_mode == "inherited_module":
            if state.get("content_authority") != "inherit_parent":
                errors.append("inherited_module content_authority must be inherit_parent")
            for field in ("parent_project_id", "inherited_content_freeze_id", "inherited_design_version"):
                if not str(module.get(field) or "").strip():
                    errors.append(f"inherited_module.module_context.{field} is required")
        if phase_index >= PHASES.index("content_frozen"):
            for field in ("strategy_input", "module_claim", "strategy_output"):
                if not str(module.get(field) or "").strip():
                    errors.append(f"module_context.{field} is required before content freeze")
            if not chapters:
                errors.append("module requires at least one confirmed chapter or content block before content freeze")
            for index, chapter in enumerate(chapters, start=1):
                chapter_id = chapter.get("chapter_id") or f"module-{index}"
                if chapter.get("manuscript_confirmed") is not True:
                    errors.append(f"{chapter_id}: module manuscript is not confirmed")
                if not chapter.get("confirmation_record_id"):
                    errors.append(f"{chapter_id}: missing confirmation_record_id")
                if not (chapter.get("slides") if isinstance(chapter.get("slides"), list) else []):
                    errors.append(f"{chapter_id}: module slides must be non-empty before content freeze")
                _, source_error = registered_project_file(project, chapter.get("source_path"), "content/chapters")
                if source_error:
                    errors.append(f"{chapter_id}.source_path: {source_error}")

    for index, event in enumerate(state.get("reopen_log") or [], start=1):
        if event.get("reopened_by") != owner:
            errors.append(f"reopen_log[{index}] was not authorized by Proposal Owner {owner!r}")
        if not event.get("slide_id") or not event.get("reason"):
            errors.append(f"reopen_log[{index}] must include slide_id and reason")

    if phase_index >= PHASES.index("content_frozen") and state.get("content_freeze_id") is None:
        errors.append("content_freeze_id is required after content freeze")
    if phase_index >= PHASES.index("design_system") and not state.get("design_version"):
        errors.append("design_version is required after design approval")

    if phase_index >= PHASES.index("speaker_notes") and task_mode != "inherited_module":
        errors.extend(validate_visual_review(project, state))
    if phase == "export":
        for assembly_error in validate_assembly_ready(project, require_final=True):
            errors.append(assembly_error)
        errors.extend(validate_final_check(project, state))

    # Missing capabilities are put to the Owner before work goes past intake; never a silent downgrade.
    errors.extend(runtime_gap_errors(state, phase_index))

    # With memory switched off globally, neither memory gate applies.
    if not memory_enabled():
        return errors
    # Leaving a phase means distilling its decisions first: signals must have run in the previous phase or later.
    if phase_index > PHASES.index("manuscript"):
        receipt_phase = read_signals_receipt(project).get("phase")
        if receipt_phase not in PHASES or PHASES.index(receipt_phase) < phase_index - 1:
            errors.append(
                f"proposal memory: 离开 {PHASES[phase_index - 1]} 阶段前没有汇总记忆信号；"
                f"运行 `proposal_memory.py advance --project <项目目录> --to {phase}`，按输出把可复用的判断写成候选"
            )
    memory = receipt_problem(project, phase)
    if memory:
        errors.append(f"{MEMORY_ERROR}{memory}；校验已把当前记忆附在输出末尾，读完再运行一次校验")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Proposal project directory")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors = validate_project(project)
    try:
        errors = apply_waivers(load_json(project / "project-state.json"), errors)
    except ValueError:
        pass
    if errors:
        print("Project validation failed:")
        for error in errors:
            print(f"- {error}")
        if any(error.startswith(MEMORY_ERROR) for error in errors):
            # Put the memory in front of the agent here, so reading it never depends on remembering a step.
            phase = load_json(project / "project-state.json")["phase"]
            text, digest, _ = memory_for_phase(project, phase)
            print()
            print(text, end="")
            write_receipt(project, phase, digest, "validate")
        return 1
    print(f"Project gates valid: {project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
