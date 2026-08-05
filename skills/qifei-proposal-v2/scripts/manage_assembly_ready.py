#!/usr/bin/env python3
"""Approve, reopen, or finalize explicitly confirmed company proposal pages."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

from validate_assembly_ready import load_json, validate_assembly_ready


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def safe_project_file(project: Path, relative: object, required_root: str) -> Path:
    raw = str(relative or "").strip().replace("\\", "/")
    candidate = Path(raw)
    if not raw or candidate.is_absolute() or ".." in candidate.parts:
        raise SystemExit(f"Invalid project-relative path: {raw!r}")
    root = (project / required_root).resolve()
    resolved = (project / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"Path must stay under {required_root}/: {raw}") from exc
    if not resolved.is_file():
        raise SystemExit(f"File does not exist: {raw}")
    return resolved


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_name(slide_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", slide_id).strip("-") or "slide"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise SystemExit(f"Direct review asset must be a valid PNG: {path}")
    return struct.unpack(">II", data[16:24])


def require_owner(state: dict, approved_by: str) -> None:
    owner = str(state.get("proposal_owner") or "").strip()
    if not owner or approved_by != owner:
        raise SystemExit(f"Only Proposal Owner {owner!r} can change assembly-ready state")


def load_project(project: Path) -> tuple[Path, Path, Path, dict, dict, dict]:
    state_path = project / "project-state.json"
    deck_path = project / "deck" / "deck-spec.json"
    state = load_json(state_path)
    deck = load_json(deck_path)
    assembly_state = state.get("assembly") if isinstance(state.get("assembly"), dict) else {}
    manifest_rel = assembly_state.get("manifest_path") or "deck/assembly-ready/manifest.json"
    manifest_path = project / Path(*str(manifest_rel).replace("\\", "/").split("/"))
    manifest = load_json(manifest_path)
    return state_path, deck_path, manifest_path, state, deck, manifest


def reset_final(state: dict, manifest: dict) -> None:
    manifest["final_assembly"] = {"approved": False, "by": None, "at": None, "record_id": None}
    approvals = state.setdefault("approvals", {})
    approvals["final_assembly"] = {"approved": False, "by": None, "at": None, "record_id": None}
    assembly = state.setdefault("assembly", {})
    assembly["final_approval_record_id"] = None


def sync_status(state: dict, deck: dict, manifest: dict) -> None:
    required = [str(slide.get("slide_id") or "").strip() for slide in deck.get("slides") or []]
    page_ids = {str(page.get("slide_id") or "").strip() for page in manifest.get("pages") or [] if isinstance(page, dict)}
    ordered = [slide_id for slide_id in required if slide_id in page_ids]
    status = "all_pages_confirmed" if required and ordered == required else "collecting"
    manifest["status"] = status
    assembly = state.setdefault("assembly", {})
    assembly["ready_slide_ids"] = ordered
    assembly["status"] = status


def approve(args: argparse.Namespace, project: Path) -> int:
    state_path, _deck_path, manifest_path, state, deck, manifest = load_project(project)
    require_owner(state, args.approved_by)
    if state.get("phase") not in {"review", "qa"}:
        raise SystemExit("Pages may be confirmed only during review or qa")

    freeze_id = state.get("content_freeze_id")
    design_version = state.get("design_version")
    if deck.get("content_freeze_id") != freeze_id:
        raise SystemExit("Deck spec content_freeze_id is stale")
    if deck.get("design_version") != design_version:
        raise SystemExit("Deck spec design_version is stale")
    if manifest.get("pages") and (
        manifest.get("content_freeze_id") != freeze_id or manifest.get("design_version") != design_version
    ):
        raise SystemExit("Existing assembly-ready pages use another freeze/design version; reopen them first")

    review = None
    review_path = None
    review_pages = {}
    direct_png = None
    if args.review_manifest:
        review_path = safe_project_file(project, args.review_manifest, "deck/review")
        review = load_json(review_path)
        if review.get("content_freeze_id") != freeze_id:
            raise SystemExit("Review manifest content_freeze_id is stale")
        if review.get("design_version") != design_version:
            raise SystemExit("Review manifest design_version is stale")
        review_html = safe_project_file(project, review.get("html_path"), "deck")
        if sha256(review_html) != review.get("html_sha256"):
            raise SystemExit("Review HTML changed after PNG capture; recapture the review PNGs")
        review_build = safe_project_file(project, review.get("build_manifest_path"), "deck")
        if sha256(review_build) != review.get("build_manifest_sha256"):
            raise SystemExit("Review build manifest changed after PNG capture; recapture the review PNGs")
        review_pages = {
            str(page.get("slide_id") or "").strip(): page
            for page in review.get("pages") or []
            if isinstance(page, dict)
        }
    else:
        if len(args.slide_id) != 1:
            raise SystemExit("--direct-png approves exactly one --slide-id per command")
        direct_png = safe_project_file(project, args.direct_png, "deck/review")
        width, height = png_size(direct_png)
        if width * 9 != height * 16:
            raise SystemExit(f"Direct review PNG must be 16:9, got {width}x{height}")

    deck_slides = {
        str(slide.get("slide_id") or "").strip(): slide
        for slide in deck.get("slides") or []
        if isinstance(slide, dict)
    }
    pages = [page for page in manifest.get("pages") or [] if isinstance(page, dict)]
    page_map = {str(page.get("slide_id") or "").strip(): page for page in pages}
    ready_dir = project / "deck" / "assembly-ready" / "pages"
    ready_dir.mkdir(parents=True, exist_ok=True)
    approved_at = now_iso()

    for slide_id in args.slide_id:
        if slide_id not in deck_slides:
            raise SystemExit(f"Unknown slide_id: {slide_id}")
        if review:
            review_page = review_pages.get(slide_id)
            if not review_page:
                raise SystemExit(f"Review manifest does not contain slide_id: {slide_id}")
            source_png = safe_project_file(project, review_page.get("png_path"), "deck/review")
            if sha256(source_png) != review_page.get("png_sha256"):
                raise SystemExit(f"Review PNG hash is stale: {slide_id}")
            source_type = "html"
            source_path = review.get("html_path")
        else:
            source_png = direct_png
            source_type = "direct_png"
            source_path = str(source_png.relative_to(project)).replace("\\", "/")
        destination = ready_dir / f"{safe_name(slide_id)}.png"
        temp = destination.with_name(f".{destination.name}.tmp")
        shutil.copy2(source_png, temp)
        temp.replace(destination)
        relative_destination = str(destination.relative_to(project)).replace("\\", "/")
        slide = deck_slides[slide_id]
        page_map[slide_id] = {
            "slide_id": slide_id,
            "status": "ready",
            "content_freeze_id": freeze_id,
            "design_version": design_version,
            "approved_content_hash": slide.get("approved_content_hash"),
            "source_type": source_type,
            "source_path": source_path,
            "source_sha256": sha256(source_png if source_type == "direct_png" else review_html),
            "review_manifest_path": str(review_path.relative_to(project)).replace("\\", "/") if review_path else None,
            "review_build_id": review.get("build_id") if review else None,
            "review_html_path": review.get("html_path") if review else None,
            "review_html_sha256": review.get("html_sha256") if review else None,
            "ready_png_path": relative_destination,
            "ready_png_sha256": sha256(destination),
            "approved_by": args.approved_by,
            "approved_at": approved_at,
            "approval_record_id": args.approval_id,
        }

    order = [str(slide.get("slide_id") or "").strip() for slide in deck.get("slides") or []]
    manifest["content_freeze_id"] = freeze_id
    manifest["design_version"] = design_version
    manifest["pages"] = [page_map[slide_id] for slide_id in order if slide_id in page_map]
    reset_final(state, manifest)
    sync_status(state, deck, manifest)
    atomic_json(manifest_path, manifest)
    atomic_json(state_path, state)
    print(f"Marked {len(args.slide_id)} page(s) assembly-ready: {', '.join(args.slide_id)}")
    print(f"Status: {manifest['status']}")
    return 0


def reopen(args: argparse.Namespace, project: Path) -> int:
    state_path, _deck_path, manifest_path, state, deck, manifest = load_project(project)
    require_owner(state, args.approved_by)
    remove_ids = set(args.slide_id)
    existing_ids = {
        str(page.get("slide_id") or "").strip()
        for page in manifest.get("pages") or []
        if isinstance(page, dict)
    }
    missing = [slide_id for slide_id in args.slide_id if slide_id not in existing_ids]
    if missing:
        raise SystemExit("Pages are not assembly-ready: " + ", ".join(missing))
    kept = []
    removed = []
    for page in manifest.get("pages") or []:
        slide_id = str(page.get("slide_id") or "").strip()
        if slide_id not in remove_ids:
            kept.append(page)
            continue
        removed.append(slide_id)
        raw = str(page.get("ready_png_path") or "").replace("\\", "/")
        candidate = project / Path(*raw.split("/"))
        if candidate.is_file():
            candidate.unlink()
        state.setdefault("reopen_log", []).append({
            "slide_id": slide_id,
            "reason": args.reason,
            "reopened_by": args.approved_by,
            "reopened_at": now_iso(),
            "scope": "assembly_ready",
        })
    manifest["pages"] = kept
    reset_final(state, manifest)
    sync_status(state, deck, manifest)
    if state.get("phase") in {"qa", "export"}:
        state["phase"] = "review"
    atomic_json(manifest_path, manifest)
    atomic_json(state_path, state)
    print("Reopened page(s): " + ", ".join(removed))
    return 0


def finalize(args: argparse.Namespace, project: Path) -> int:
    state_path, _deck_path, manifest_path, state, _deck, manifest = load_project(project)
    require_owner(state, args.approved_by)
    errors = validate_assembly_ready(project, require_final=False)
    if errors:
        raise SystemExit("Final assembly blocked:\n- " + "\n- ".join(errors))
    approved_at = now_iso()
    record = {
        "approved": True,
        "by": args.approved_by,
        "at": approved_at,
        "record_id": args.approval_id,
    }
    manifest["status"] = "final_approved"
    manifest["final_assembly"] = record
    state.setdefault("approvals", {})["final_assembly"] = dict(record)
    assembly = state.setdefault("assembly", {})
    assembly["status"] = "final_approved"
    assembly["final_approval_record_id"] = args.approval_id
    atomic_json(manifest_path, manifest)
    atomic_json(state_path, state)
    print(f"Final assembly approved as {args.approval_id}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    subparsers = parser.add_subparsers(dest="command", required=True)

    approve_parser = subparsers.add_parser("approve", help="Mark explicitly confirmed page(s) ready")
    source_group = approve_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--review-manifest")
    source_group.add_argument("--direct-png", help="Approved 16:9 PNG under deck/review for an image-native page")
    approve_parser.add_argument("--slide-id", action="append", required=True)
    approve_parser.add_argument("--approved-by", required=True)
    approve_parser.add_argument("--approval-id", required=True)

    reopen_parser = subparsers.add_parser("reopen", help="Remove page(s) from the ready library")
    reopen_parser.add_argument("--slide-id", action="append", required=True)
    reopen_parser.add_argument("--approved-by", required=True)
    reopen_parser.add_argument("--reason", required=True)

    finalize_parser = subparsers.add_parser("finalize", help="Approve one-time final assembly")
    finalize_parser.add_argument("--approved-by", required=True)
    finalize_parser.add_argument("--approval-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = Path(args.project).expanduser().resolve()
    if args.command == "approve":
        return approve(args, project)
    if args.command == "reopen":
        return reopen(args, project)
    return finalize(args, project)


if __name__ == "__main__":
    raise SystemExit(main())
