#!/usr/bin/env python3
"""Validate the evidence fields of a reread Feishu proposal snapshot."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


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


def validate_feishu_draft_evidence(project: Path, state: dict[str, Any]) -> list[str]:
    """Validate metadata and hash evidence shared by all production gates."""

    errors: list[str] = []
    draft = state.get("proposal_draft") if isinstance(state.get("proposal_draft"), dict) else {}
    if not draft:
        return [
            "full_redteam requires a verified Feishu proposal draft; local Markdown is only a temporary fallback"
        ]
    if draft.get("authority") != "feishu" or draft.get("status") != "verified":
        errors.append("proposal_draft must use authority feishu with status verified before production")
    if draft.get("format_version") != FEISHU_DRAFT_FORMAT_VERSION:
        errors.append(f"proposal_draft.format_version must be {FEISHU_DRAFT_FORMAT_VERSION}")
    for field in ("feishu_doc_url", "document_id", "last_verified_at"):
        if not str(draft.get(field) or "").strip():
            errors.append(f"proposal_draft.{field} is required")
    revision_id = draft.get("revision_id")
    if not isinstance(revision_id, int) or isinstance(revision_id, bool) or revision_id <= 0:
        errors.append("proposal_draft.revision_id must be a positive integer from Feishu reread")

    snapshot_path, snapshot_error = registered_project_file(
        project,
        draft.get("verified_snapshot_path"),
        "content/feishu",
    )
    if snapshot_error:
        errors.append(f"proposal_draft.verified_snapshot_path: {snapshot_error}")
    elif snapshot_path:
        try:
            snapshot_bytes = snapshot_path.read_bytes()
            snapshot_bytes.decode("utf-8")
        except UnicodeDecodeError:
            errors.append("proposal_draft.verified_snapshot_path must be UTF-8 text")
        else:
            actual_hash = hashlib.sha256(snapshot_bytes).hexdigest()
            if draft.get("verified_snapshot_sha256") != actual_hash:
                errors.append("proposal_draft.verified_snapshot_sha256 does not match the reread snapshot")
    return errors
