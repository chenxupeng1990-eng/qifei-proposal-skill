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
    "design_system",
    "generation",
    "review",
    "qa",
    "export",
]

GATES = {
    "requirements": ["materials_scope"],
    "strategy": ["materials_scope", "requirements"],
    "project_agents": ["materials_scope", "requirements", "strategy", "outline"],
    "manuscript": ["materials_scope", "requirements", "strategy", "outline", "project_agents"],
    "chapter_redteam": ["project_agents"],
    "full_redteam": ["project_agents"],
    "content_frozen": ["full_redteam", "content_freeze"],
    "visual_direction": ["content_freeze"],
    "visual_sample": ["content_freeze", "visual_direction"],
    "design_system": ["content_freeze", "visual_direction", "visual_sample"],
    "generation": ["content_freeze", "visual_sample", "design", "generation_ready"],
    "review": ["content_freeze", "design", "generation_ready"],
    "qa": ["content_freeze", "design", "generation_ready"],
    "export": ["content_freeze", "design", "generation_ready", "content_qa", "visual_qa"],
}


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
    if phase_index >= PHASES.index("project_agents") and not (project / "AGENTS.md").is_file():
        errors.append("AGENTS.md is required after outline confirmation")
    if phase_index >= PHASES.index("design_system") and not (project / "DESIGN.md").is_file():
        errors.append("DESIGN.md is required after visual sample confirmation")
    if phase_index >= PHASES.index("generation"):
        for relative in ("deck/deck-spec.json", "deck/slide-contracts.json", "deck/design-tokens.json"):
            if not (project / relative).is_file():
                errors.append(f"Generation requires {relative}")

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
