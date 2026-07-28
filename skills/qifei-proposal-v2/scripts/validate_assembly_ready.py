#!/usr/bin/env python3
"""Validate explicitly approved pages before final company deck assembly."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_file(project: Path, value: object, required_root: str) -> tuple[Path | None, str | None]:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None, "path is empty"
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        return None, f"path must be project-relative: {raw}"
    root = (project / required_root).resolve()
    resolved = (project / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, f"path must stay under {required_root}/: {raw}"
    if not resolved.is_file():
        return None, f"file does not exist: {raw}"
    return resolved, None


def validate_assembly_ready(project: Path, require_final: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        state = load_json(project / "project-state.json")
        deck = load_json(project / "deck" / "deck-spec.json")
    except ValueError as exc:
        return [str(exc)]

    assembly_state = state.get("assembly") if isinstance(state.get("assembly"), dict) else {}
    manifest_value = assembly_state.get("manifest_path") or "deck/assembly-ready/manifest.json"
    manifest_path, manifest_error = project_file(project, manifest_value, "deck/assembly-ready")
    if manifest_error:
        return [f"assembly.manifest_path: {manifest_error}"]
    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        return [str(exc)]

    freeze_id = state.get("content_freeze_id")
    design_version = state.get("design_version")
    pages = manifest.get("pages") if isinstance(manifest.get("pages"), list) else []
    # A newly initialized collection manifest intentionally has no freeze/design values
    # until the first explicitly approved page is copied into it. Once it holds a page,
    # version drift is a hard failure.
    if pages and (manifest.get("content_freeze_id") != freeze_id or deck.get("content_freeze_id") != freeze_id):
        errors.append("Assembly manifest, deck spec, and project state have different content_freeze_id values")
    if pages and (manifest.get("design_version") != design_version or deck.get("design_version") != design_version):
        errors.append("Assembly manifest, deck spec, and project state have different design_version values")

    slides = deck.get("slides") if isinstance(deck.get("slides"), list) else []
    required_ids = [str(slide.get("slide_id") or "").strip() for slide in slides]
    if not required_ids or any(not slide_id for slide_id in required_ids):
        errors.append("deck-spec.json must contain non-empty slide_id values")
    if len(required_ids) != len(set(required_ids)):
        errors.append("deck-spec.json contains duplicate slide_id values")
    slide_map = {str(slide.get("slide_id") or "").strip(): slide for slide in slides}

    page_map: dict[str, dict] = {}
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            errors.append(f"assembly pages[{index}] must be an object")
            continue
        slide_id = str(page.get("slide_id") or "").strip()
        if not slide_id:
            errors.append(f"assembly pages[{index}] is missing slide_id")
            continue
        if slide_id in page_map:
            errors.append(f"assembly manifest contains duplicate slide_id: {slide_id}")
            continue
        page_map[slide_id] = page

    missing = [slide_id for slide_id in required_ids if slide_id not in page_map]
    extra = [slide_id for slide_id in page_map if slide_id not in slide_map]
    if missing:
        errors.append("Pages not ready for final assembly: " + ", ".join(missing))
    if extra:
        errors.append("Assembly manifest contains unknown pages: " + ", ".join(extra))

    owner = str(state.get("proposal_owner") or "").strip()
    for slide_id, page in page_map.items():
        slide = slide_map.get(slide_id)
        if not slide:
            continue
        if page.get("status") != "ready":
            errors.append(f"{slide_id}: assembly status must be ready")
        if page.get("content_freeze_id") != freeze_id:
            errors.append(f"{slide_id}: content_freeze_id is stale")
        if page.get("design_version") != design_version:
            errors.append(f"{slide_id}: design_version is stale")
        if page.get("approved_content_hash") != slide.get("approved_content_hash"):
            errors.append(f"{slide_id}: approved content hash is stale")
        if page.get("approved_by") != owner or not page.get("approval_record_id"):
            errors.append(f"{slide_id}: missing explicit Proposal Owner approval")
        # Schema 1.0 pages predate route-aware sources. Treat their recorded
        # review HTML as the source so existing confirmed projects remain valid.
        source_type = page.get("source_type") or ("html" if page.get("review_html_path") else None)
        if source_type not in {"html", "direct_png"}:
            errors.append(f"{slide_id}: source_type must be html or direct_png")
        source_root = "deck/review" if source_type == "direct_png" else "deck"
        source_value = page.get("source_path") or page.get("review_html_path")
        source_hash = page.get("source_sha256") or page.get("review_html_sha256")
        source_path, source_error = project_file(project, source_value, source_root)
        if source_error:
            errors.append(f"{slide_id}.source_path: {source_error}")
        elif source_path and sha256(source_path) != source_hash:
            errors.append(f"{slide_id}: approved source hash does not match")
        png_path, png_error = project_file(project, page.get("ready_png_path"), "deck/assembly-ready/pages")
        if png_error:
            errors.append(f"{slide_id}.ready_png_path: {png_error}")
        elif png_path and sha256(png_path) != page.get("ready_png_sha256"):
            errors.append(f"{slide_id}: approved PNG hash does not match")

    ordered_ready = [slide_id for slide_id in required_ids if slide_id in page_map]
    if assembly_state.get("ready_slide_ids") != ordered_ready:
        errors.append("project-state assembly.ready_slide_ids does not match the manifest in deck order")

    if require_final:
        final_manifest = manifest.get("final_assembly") if isinstance(manifest.get("final_assembly"), dict) else {}
        final_state = (state.get("approvals") or {}).get("final_assembly")
        final_state = final_state if isinstance(final_state, dict) else {}
        if manifest.get("status") != "final_approved" or assembly_state.get("status") != "final_approved":
            errors.append("Final assembly has not been explicitly approved")
        if final_manifest.get("approved") is not True or final_state.get("approved") is not True:
            errors.append("Final assembly approval record is missing")
        record_id = final_manifest.get("record_id")
        if not record_id or final_state.get("record_id") != record_id or assembly_state.get("final_approval_record_id") != record_id:
            errors.append("Final assembly approval record ids do not match")
        if final_manifest.get("by") != owner or final_state.get("by") != owner:
            errors.append("Final assembly was not approved by the Proposal Owner")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--require-final", action="store_true")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors = validate_assembly_ready(project, require_final=args.require_final)
    if errors:
        print("Assembly-ready validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Assembly-ready manifest valid: {project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
