#!/usr/bin/env python3
"""Validate company proposal phase gates and required project artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from validate_assembly_ready import validate_assembly_ready
from validate_deck_spec import png_has_alpha
from validate_design_loop import validate_chapter_report


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
    "visual_sample": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction"],
    "design_calibration": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction", "visual_sample"],
    "design_system": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "visual_direction", "visual_sample", "design_calibration"],
    "generation": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "visual_sample", "design_calibration", "design", "generation_ready"],
    "review": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready"],
    "qa": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready", "design_loop"],
    "export": ["content_freeze", "brand_visual_sources", "brand_visual_audit", "brand_visual_incorporation", "design_calibration", "design", "generation_ready", "design_loop", "content_qa", "visual_qa", "final_assembly"],
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
FEISHU_DRAFT_FORMAT_VERSION = "feishu-proposal-draft-v1"
FEISHU_PAGE_SECTIONS = (
    "核心内容",
    "逻辑展开",
    "PPT上屏内容",
    "讲解方向",
    "策略与过桥",
    "视觉生成建议",
    "证据与来源",
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


def validate_verified_feishu_draft(project: Path, state: dict, chapters: list[dict]) -> list[str]:
    errors: list[str] = []
    draft = state.get("proposal_draft") if isinstance(state.get("proposal_draft"), dict) else {}
    if not draft:
        return ["full_redteam requires a verified Feishu proposal draft; local Markdown is only a temporary fallback"]
    if draft.get("authority") != "feishu" or draft.get("status") != "verified":
        errors.append("proposal_draft must use authority feishu with status verified before full_redteam")
    if draft.get("format_version") != FEISHU_DRAFT_FORMAT_VERSION:
        errors.append(f"proposal_draft.format_version must be {FEISHU_DRAFT_FORMAT_VERSION}")
    for field in ("feishu_doc_url", "document_id", "last_verified_at"):
        if not str(draft.get(field) or "").strip():
            errors.append(f"proposal_draft.{field} is required")
    revision_id = draft.get("revision_id")
    if not isinstance(revision_id, int) or revision_id <= 0:
        errors.append("proposal_draft.revision_id must be a positive integer from Feishu reread")

    snapshot_path, snapshot_error = registered_project_file(
        project,
        draft.get("verified_snapshot_path"),
        "content/feishu",
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

    if snapshot_text:
        for marker in ("**本章回答：**", "**逻辑路径：**", "**情绪方向：**"):
            if marker not in snapshot_text:
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
                if not re.search(rf"(?m)^###\s+{re.escape(section)}\s*$", page_text):
                    errors.append(f"{slide_id}: verified Feishu proposal draft is missing section: {section}")
        if re.search(r"(?m)^#{2,4}\s*(完整讲稿|逐字稿|Speaker Notes)", snapshot_text, re.IGNORECASE):
            errors.append("verified Feishu proposal draft must not contain the final full speaker script")
    return errors


def validate_visual_direction_drafts(project: Path, state: dict, approvals: dict) -> list[str]:
    errors: list[str] = []
    visual_direction = state.get("visual_direction") if isinstance(state.get("visual_direction"), dict) else {}
    directions = visual_direction.get("directions") if isinstance(visual_direction.get("directions"), list) else []
    if not 2 <= len(directions) <= 3:
        errors.append("visual_direction.directions must contain 2-3 generated visual directions")
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
    if phase_index >= PHASES.index("generation"):
        for relative in ("deck/deck-spec.json", "deck/slide-contracts.json", "deck/design-tokens.json"):
            if not (project / relative).is_file():
                errors.append(f"Generation requires {relative}")

    if phase_index >= PHASES.index("visual_direction"):
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

    if phase_index >= PHASES.index("visual_sample") or is_approved(approvals, "visual_direction"):
        errors.extend(validate_visual_direction_drafts(project, state, approvals))

    chapters = state.get("chapters") if isinstance(state.get("chapters"), list) else []
    if phase_index >= PHASES.index("full_redteam"):
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

    full_review_required = phase_index >= PHASES.index("content_frozen") or is_approved(approvals, "full_redteam")
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

    for index, event in enumerate(state.get("reopen_log") or [], start=1):
        if event.get("reopened_by") != owner:
            errors.append(f"reopen_log[{index}] was not authorized by Proposal Owner {owner!r}")
        if not event.get("slide_id") or not event.get("reason"):
            errors.append(f"reopen_log[{index}] must include slide_id and reason")

    if phase_index >= PHASES.index("content_frozen") and state.get("content_freeze_id") is None:
        errors.append("content_freeze_id is required after content freeze")
    if phase_index >= PHASES.index("design_system") and not state.get("design_version"):
        errors.append("design_version is required after design approval")

    if phase == "export":
        for assembly_error in validate_assembly_ready(project, require_final=True):
            errors.append(assembly_error)

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
