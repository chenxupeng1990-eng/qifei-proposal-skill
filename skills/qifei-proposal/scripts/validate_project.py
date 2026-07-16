#!/usr/bin/env python3
"""Validate QIFEI proposal phase gates and required project artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PHASES = [
    "intake",
    "requirements",
    "strategy",
    "project_agents",
    "manuscript",
    "chapter_redteam",
    "full_redteam",
    "content_frozen",
    "visual_direction",
    "visual_sample",
    "design_calibration",
    "design_system",
    "generation",
    "review",
    "qa",
    "export",
]

GATES = {
    "requirements": ["materials_scope"],
    "strategy": ["materials_scope", "brief_grill", "proposal_brief", "requirements"],
    "project_agents": ["materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline"],
    "manuscript": ["materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline", "project_agents"],
    "chapter_redteam": ["project_agents"],
    "full_redteam": ["project_agents"],
    "content_frozen": ["full_redteam", "content_freeze"],
    "visual_direction": ["content_freeze", "brand_visual_sources", "brand_visual_audit"],
    "visual_sample": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction"],
    "design_calibration": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction", "visual_sample"],
    "design_system": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction", "visual_sample", "design_calibration"],
    "generation": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "visual_sample", "design_calibration", "design", "generation_ready"],
    "review": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready"],
    "qa": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready"],
    "export": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready", "content_qa", "visual_qa"],
}

BRAND_SOURCE_SUFFIXES = {".ai", ".eps", ".jpg", ".jpeg", ".key", ".pdf", ".png", ".ppt", ".pptx", ".svg", ".webp"}
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


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def is_approved(approvals: dict, key: str) -> bool:
    item = approvals.get(key)
    return isinstance(item, dict) and item.get("approved") is True and bool(item.get("by")) and bool(item.get("record_id"))


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


def validate_project(project: Path) -> list[str]:
    errors: list[str] = []
    state_path = project / "project-state.json"
    try:
        state = load_json(state_path)
    except ValueError as exc:
        return [str(exc)]

    phase = state.get("phase")
    if phase not in PHASES:
        errors.append(f"Unknown phase: {phase!r}")
        return errors

    owner = str(state.get("proposal_owner") or "").strip()
    if not owner:
        errors.append("project-state.json is missing proposal_owner")

    approvals = state.get("approvals") if isinstance(state.get("approvals"), dict) else {}
    for gate in GATES.get(phase, []):
        if not is_approved(approvals, gate):
            errors.append(f"Phase {phase} requires approved gate: {gate}")

    phase_index = PHASES.index(phase)
    if phase_index >= PHASES.index("strategy"):
        brief_path = project / "content" / "proposal-brief.md"
        if not brief_path.is_file():
            errors.append("content/proposal-brief.md is required before strategy")
        else:
            brief_text = brief_path.read_text(encoding="utf-8")
            if any(marker in brief_text for marker in ("待确认", "待填写")):
                errors.append("Approved proposal brief still contains unresolved placeholder markers")
        for gate in ("brief_grill", "proposal_brief"):
            if not is_approved(approvals, gate):
                message = f"Phase {phase} requires approved gate: {gate}"
                if message not in errors:
                    errors.append(message)
    if phase_index >= PHASES.index("project_agents") and not (project / "AGENTS.md").is_file():
        errors.append("AGENTS.md is required after outline confirmation")
    if phase_index >= PHASES.index("design_system") and not (project / "DESIGN.md").is_file():
        errors.append("DESIGN.md is required after design calibration confirmation")
    if phase_index >= PHASES.index("design_calibration"):
        calibration = state.get("design_calibration") if isinstance(state.get("design_calibration"), dict) else {}
        calibration_value = calibration.get("path") or "deck/design-calibration.html"
        calibration_path, calibration_error = registered_project_file(project, calibration_value, "deck")
        if calibration_error:
            errors.append(f"design_calibration.path: {calibration_error}")
        elif calibration_path:
            calibration_text = calibration_path.read_text(encoding="utf-8")
            configured_types = calibration.get("required_sample_types")
            required_types = configured_types if isinstance(configured_types, list) and configured_types else DEFAULT_DESIGN_SAMPLE_TYPES
            for sample_type in required_types:
                marker_double = f'data-design-sample="{sample_type}"'
                marker_single = f"data-design-sample='{sample_type}'"
                if marker_double not in calibration_text and marker_single not in calibration_text:
                    errors.append(f"Design calibration is missing required sample type: {sample_type}")
        if phase_index >= PHASES.index("design_system"):
            approval = approvals.get("design_calibration") if isinstance(approvals.get("design_calibration"), dict) else {}
            approval_id = str(calibration.get("approval_record_id") or "").strip()
            if is_approved(approvals, "design_calibration") and (not approval_id or approval.get("record_id") != approval_id):
                errors.append("design_calibration.approval_record_id must match its approval record")
    if phase_index >= PHASES.index("generation"):
        for relative in ("deck/deck-spec.json", "deck/slide-contracts.json", "deck/design-tokens.json"):
            if not (project / relative).is_file():
                errors.append(f"Generation requires {relative}")

    if phase_index >= PHASES.index("visual_direction"):
        brand_visual = state.get("brand_visual") if isinstance(state.get("brand_visual"), dict) else {}
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
                    if alpha_tokens.get("enabled") is not True or alpha_tokens.get("alpha_required") is not True:
                        errors.append("design-tokens.json transparent_png must enable real alpha-channel modules")

    chapters = state.get("chapters") if isinstance(state.get("chapters"), list) else []
    if phase_index >= PHASES.index("full_redteam"):
        if not chapters:
            errors.append("At least one chapter is required before full_redteam")
        for index, chapter in enumerate(chapters, start=1):
            chapter_id = chapter.get("chapter_id") or f"chapter-{index}"
            if chapter.get("manuscript_confirmed") is not True:
                errors.append(f"{chapter_id}: manuscript is not fully confirmed")
            if chapter.get("redteam_passed") is not True:
                errors.append(f"{chapter_id}: chapter red-team has not passed")
            if not chapter.get("confirmation_record_id"):
                errors.append(f"{chapter_id}: missing confirmation_record_id")
            if not chapter.get("redteam_report"):
                errors.append(f"{chapter_id}: missing redteam_report")

    for index, event in enumerate(state.get("reopen_log") or [], start=1):
        if event.get("reopened_by") != owner:
            errors.append(f"reopen_log[{index}] was not authorized by Proposal Owner {owner!r}")
        if not event.get("slide_id") or not event.get("reason"):
            errors.append(f"reopen_log[{index}] must include slide_id and reason")

    if phase_index >= PHASES.index("content_frozen") and state.get("content_freeze_id") is None:
        errors.append("content_freeze_id is required after content freeze")
    if phase_index >= PHASES.index("design_system") and not state.get("design_version"):
        errors.append("design_version is required after design approval")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Proposal project directory")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors = validate_project(project)
    if errors:
        print("Project validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Project gates valid: {project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
