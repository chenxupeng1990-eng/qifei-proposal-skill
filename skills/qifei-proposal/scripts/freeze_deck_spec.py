#!/usr/bin/env python3
"""Freeze confirmed slide content and record stable approval hashes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from slide_hash import content_hash
from validate_project import validate_project


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def approved(item: object) -> bool:
    return isinstance(item, dict) and item.get("approved") is True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approval-id", required=True)
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    project_errors = validate_project(project)
    if project_errors:
        raise SystemExit("Project gates block content freeze:\n- " + "\n- ".join(project_errors))
    state_path = project / "project-state.json"
    deck_path = project / "deck" / "deck-spec.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    deck = json.loads(deck_path.read_text(encoding="utf-8"))

    owner = state.get("proposal_owner")
    if args.approved_by != owner:
        raise SystemExit(f"Only Proposal Owner {owner!r} can freeze content")
    if state.get("phase") not in {"full_redteam", "content_frozen"}:
        raise SystemExit("Content can be frozen only from full_redteam or content_frozen phase")
    if not approved((state.get("approvals") or {}).get("full_redteam")):
        raise SystemExit("Full-deck red-team approval is required before content freeze")
    for chapter in state.get("chapters") or []:
        if chapter.get("manuscript_confirmed") is not True or chapter.get("redteam_passed") is not True:
            raise SystemExit(f"Chapter not ready for freeze: {chapter.get('chapter_id')}")

    slides = deck.get("slides") if isinstance(deck.get("slides"), list) else []
    if not slides:
        raise SystemExit("deck-spec.json must contain at least one slide")
    seen: set[str] = set()
    for slide in slides:
        slide_id = str(slide.get("slide_id") or "").strip()
        if not slide_id or slide_id in seen:
            raise SystemExit(f"Missing or duplicate slide_id: {slide_id!r}")
        seen.add(slide_id)
        slide["status"] = "content_frozen"
        slide["approved_content_hash"] = content_hash(slide)

    now = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    deck["content_freeze_id"] = args.approval_id
    state["phase"] = "content_frozen"
    state["content_freeze_id"] = args.approval_id
    state.setdefault("approvals", {})["content_freeze"] = {
        "approved": True,
        "by": args.approved_by,
        "at": now,
        "record_id": args.approval_id,
    }
    atomic_json(deck_path, deck)
    atomic_json(state_path, state)
    print(f"Frozen {len(slides)} slide(s) as {args.approval_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
