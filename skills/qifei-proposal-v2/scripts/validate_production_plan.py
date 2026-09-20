#!/usr/bin/env python3
"""Validate the bounded parallel-production plan for a governed project."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path, PurePosixPath
from typing import Any

from validate_feishu_draft import validate_feishu_draft_evidence
from validate_json_schema import validate_json_schema

MAX_PARALLEL_AGENTS = 6
PLAN_SCHEMA_VERSION = "1.0"
PRODUCTION_PLAN_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "production-plan.schema.json"
PRODUCTION_MODES = {"sequential", "parallel_after_gates"}
PRODUCTION_STATUSES = {
    "not_started",
    "ready",
    "in_flight",
    "awaiting_reverify",
    "verified",
    "blocked",
}
WAVE_STATUSES = {"ready", "in_flight", "awaiting_reverify", "verified", "abandoned"}
AGENT_STATUSES = {"ready", "in_flight", "verified", "abandoned"}
ALLOWED_WRITE_ROOTS = (
    "deck/chapters/",
    "deck/review/",
    "deck/production/results/",
    "assets/image2/",
)
RESERVED_SHARED_PREFIXES = (
    "content/feishu/",
    "content/strategy/",
    "reviews/redteam/",
    "reviews/design-loop/",
    "deck/assembly-ready/",
)
RESERVED_SHARED_FILES = {
    "project-state.json",
    "AGENTS.md",
    "DESIGN.md",
    "deck/deck-spec.json",
    "deck/slide-contracts.json",
    "deck/design-tokens.json",
    "content/proposal-brief.md",
}
REQUIRED_SHARED_READ_ONLY = {
    "project-state.json",
    "AGENTS.md",
    "DESIGN.md",
    "deck/deck-spec.json",
    "deck/slide-contracts.json",
    "deck/design-tokens.json",
    "content/proposal-brief.md",
    "content/feishu/proposal-draft.md",
    "content/strategy",
    "reviews/redteam",
    "reviews/design-loop",
    "deck/assembly-ready",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def is_approved(approvals: dict[str, Any], key: str) -> bool:
    item = approvals.get(key)
    return (
        isinstance(item, dict)
        and item.get("approved") is True
        and bool(item.get("by"))
        and bool(item.get("at"))
        and bool(item.get("record_id"))
    )


def normalize_relative_path(value: Any) -> str | None:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    normalized = str(path)
    return None if normalized in {"", "."} else normalized


def path_overlaps(left: str, right: str) -> bool:
    left_key = left.casefold()
    right_key = right.casefold()
    return (
        left_key == right_key
        or left_key.startswith(right_key + "/")
        or right_key.startswith(left_key + "/")
    )


def timestamp_value(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def validate_approval_entry(approvals: dict[str, Any], key: str, errors: list[str]) -> None:
    if not is_approved(approvals, key):
        errors.append(f"parallel production requires approved gate: {key}")


def validate_production_plan(project: Path, state: dict[str, Any] | None = None) -> list[str]:
    """Return objective errors for the production wave plan.

    A project without the parallel mode keeps the existing sequential route. The
    validator is intentionally limited to the production hand-off and does not
    re-judge strategy, content, design, or Owner decisions.
    """

    errors: list[str] = []
    if state is None:
        try:
            state = load_json(project / "project-state.json")
        except ValueError as exc:
            return [str(exc)]

    production = state.get("production") if isinstance(state.get("production"), dict) else {}
    mode = str(production.get("mode") or "sequential").strip()
    if mode == "sequential":
        return []
    if mode not in PRODUCTION_MODES:
        return [f"production.mode must be sequential or parallel_after_gates, got {mode!r}"]
    if mode != "parallel_after_gates":
        return []

    production_status = str(production.get("status") or "").strip()
    if production_status not in PRODUCTION_STATUSES:
        errors.append(f"production.status is invalid: {production_status!r}")

    state_max_agents = production.get("max_agents")
    if not isinstance(state_max_agents, int) or isinstance(state_max_agents, bool):
        errors.append("production.max_agents must be an integer")
    elif state_max_agents < 1 or state_max_agents > MAX_PARALLEL_AGENTS:
        errors.append(f"production.max_agents maximum is {MAX_PARALLEL_AGENTS}")

    task_mode = str(state.get("task_mode") or "full_deck").strip()
    approvals = state.get("approvals") if isinstance(state.get("approvals"), dict) else {}
    validate_approval_entry(approvals, "content_freeze", errors)
    validate_approval_entry(approvals, "generation_ready", errors)
    if task_mode != "inherited_module":
        validate_approval_entry(approvals, "design", errors)

    if not str(state.get("content_freeze_id") or "").strip():
        errors.append("parallel production requires content_freeze_id")
    if not str(state.get("design_version") or "").strip():
        errors.append("parallel production requires design_version")

    draft = state.get("proposal_draft") if isinstance(state.get("proposal_draft"), dict) else {}
    if task_mode == "full_deck":
        errors.extend(validate_feishu_draft_evidence(project, state))
    elif task_mode != "inherited_module" and draft.get("status") != "verified":
        errors.append("module parallel production requires a verified proposal draft")

    plan_relative = normalize_relative_path(production.get("plan_path"))
    if plan_relative is None:
        errors.append("production.plan_path must be a project-relative path")
        return errors
    if not plan_relative.startswith("deck/production/"):
        errors.append("production.plan_path must stay under deck/production/")
        return errors

    try:
        project_root = project.resolve()
        plan_path = (project_root / plan_relative).resolve()
        try:
            plan_path.relative_to(project_root)
        except ValueError:
            errors.append("production.plan_path must resolve inside the project")
            return errors
        plan = load_json(plan_path)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    schema_errors = validate_json_schema(plan, load_json(PRODUCTION_PLAN_SCHEMA))
    errors.extend(f"production plan schema: {error}" for error in schema_errors)

    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        errors.append(f"production plan schema_version must be {PLAN_SCHEMA_VERSION}")
    if plan.get("project_id") != state.get("project_id"):
        errors.append("production plan project_id must match project-state.json")
    if plan.get("content_freeze_id") != state.get("content_freeze_id"):
        errors.append("production plan content_freeze_id must match project-state.json")
    if plan.get("design_version") != state.get("design_version"):
        errors.append("production plan design_version must match project-state.json")

    state_revision = draft.get("revision_id")
    if isinstance(state_revision, int) and plan.get("manuscript_revision_id") != state_revision:
        errors.append("production plan manuscript_revision_id must match the verified manuscript revision")

    plan_max_agents = plan.get("max_agents")
    if not isinstance(plan_max_agents, int) or isinstance(plan_max_agents, bool):
        errors.append("production plan max_agents must be an integer")
    else:
        if plan_max_agents < 1 or plan_max_agents > MAX_PARALLEL_AGENTS:
            errors.append(f"production plan max_agents maximum is {MAX_PARALLEL_AGENTS}")
        if isinstance(state_max_agents, int) and plan_max_agents != state_max_agents:
            errors.append("production plan max_agents must match project-state.json")

    if not str(plan.get("integration_owner") or "").strip():
        errors.append("production plan integration_owner is required")

    shared_read_only = plan.get("shared_read_only")
    if not isinstance(shared_read_only, list) or not shared_read_only:
        errors.append("production plan shared_read_only must be a non-empty list")
    else:
        normalized_shared: set[str] = set()
        for index, value in enumerate(shared_read_only, start=1):
            normalized = normalize_relative_path(value)
            if normalized is None:
                errors.append(f"production plan shared_read_only[{index}] must be project-relative")
                continue
            normalized_shared.add(normalized.casefold())
        for required in sorted(REQUIRED_SHARED_READ_ONLY):
            if required.casefold() not in normalized_shared:
                errors.append(f"production plan shared_read_only is missing {required}")

    waves = plan.get("waves")
    if not isinstance(waves, list) or not waves:
        errors.append("production plan waves must be a non-empty list")
        return errors

    seen_slides: dict[str, str] = {}
    seen_agents: dict[str, str] = {}
    seen_paths: dict[str, tuple[str, str]] = {}
    seen_wave_ids: set[str] = set()
    all_slide_ids: list[str] = []

    for wave_index, wave in enumerate(waves, start=1):
        scope = f"production plan waves[{wave_index}]"
        if not isinstance(wave, dict):
            errors.append(f"{scope} must be an object")
            continue
        wave_id = str(wave.get("wave_id") or "").strip()
        if not wave_id:
            errors.append(f"{scope}.wave_id is required")
            wave_id = f"wave-{wave_index}"
        elif wave_id.casefold() in seen_wave_ids:
            errors.append(f"wave_id {wave_id} must be unique")
        seen_wave_ids.add(wave_id.casefold())
        wave_status = str(wave.get("status") or "").strip()
        if wave_status not in WAVE_STATUSES:
            errors.append(f"{scope}.status is invalid: {wave_status!r}")
        agents = wave.get("agents")
        if not isinstance(agents, list) or not agents:
            errors.append(f"{scope}.agents must be a non-empty list")
            continue
        if isinstance(plan_max_agents, int) and len(agents) > plan_max_agents:
            errors.append(f"{scope} exceeds the configured parallel agent limit")

        for agent_index, agent in enumerate(agents, start=1):
            agent_scope = f"{scope}.agents[{agent_index}]"
            if not isinstance(agent, dict):
                errors.append(f"{agent_scope} must be an object")
                continue
            agent_id = str(agent.get("agent_id") or "").strip()
            agent_status = str(agent.get("status") or "").strip()
            assignment_active = wave_status != "abandoned" and agent_status != "abandoned"
            if not agent_id:
                errors.append(f"{agent_scope}.agent_id is required")
            elif assignment_active and agent_id.casefold() in seen_agents:
                errors.append(f"agent id {agent_id} is assigned more than once")
            elif assignment_active:
                seen_agents[agent_id.casefold()] = wave_id

            if agent_status not in AGENT_STATUSES:
                errors.append(f"{agent_scope}.status is invalid: {agent_status!r}")

            slide_ids = agent.get("slide_ids")
            if not isinstance(slide_ids, list) or not slide_ids:
                errors.append(f"{agent_scope}.slide_ids must be a non-empty list")
                slide_ids = []
            for slide_id_value in slide_ids:
                slide_id = str(slide_id_value or "").strip()
                if not slide_id:
                    errors.append(f"{agent_scope}.slide_ids cannot contain empty values")
                    continue
                if assignment_active and slide_id in seen_slides:
                    errors.append(f"slide id {slide_id} is assigned more than once")
                elif assignment_active:
                    seen_slides[slide_id] = agent_id or agent_scope
                    all_slide_ids.append(slide_id)

            write_paths = agent.get("write_paths")
            if not isinstance(write_paths, list) or not write_paths:
                errors.append(f"{agent_scope}.write_paths must be a non-empty list")
                write_paths = []
            for path_value in write_paths:
                normalized = normalize_relative_path(path_value)
                if normalized is None:
                    errors.append(f"{agent_scope} write path must be project-relative: {path_value!r}")
                    continue
                if (
                    normalized in RESERVED_SHARED_FILES
                    or any(normalized.startswith(prefix) for prefix in RESERVED_SHARED_PREFIXES)
                ):
                    errors.append(f"{agent_scope} write path is a reserved shared file: {normalized}")
                if not any(normalized.startswith(root) for root in ALLOWED_WRITE_ROOTS):
                    errors.append(f"{agent_scope} write path is outside the allowed production roots: {normalized}")
                normalized_key = normalized.casefold()
                if assignment_active and normalized_key in seen_paths:
                    errors.append(f"write path {normalized} is assigned more than once")
                elif assignment_active:
                    for existing_path, existing_owner in seen_paths.values():
                        if path_overlaps(normalized, existing_path):
                            errors.append(
                                f"write path {normalized} overlaps {existing_path} assigned to {existing_owner}"
                            )
                            break
                    seen_paths[normalized_key] = (normalized, agent_id or agent_scope)

    try:
        deck = load_json(project / "deck" / "deck-spec.json")
    except ValueError as exc:
        errors.append(f"production plan deck coverage: {exc}")
    else:
        deck_slides = deck.get("slides") if isinstance(deck.get("slides"), list) else []
        deck_slide_ids = [
            str(slide.get("slide_id") or "").strip()
            for slide in deck_slides
            if isinstance(slide, dict) and str(slide.get("slide_id") or "").strip()
        ]
        if not deck_slide_ids:
            errors.append("production plan deck coverage: deck-spec.json has no slide ids")
        elif set(all_slide_ids) != set(deck_slide_ids):
            missing_from_plan = [slide_id for slide_id in deck_slide_ids if slide_id not in all_slide_ids]
            unknown_to_deck = [slide_id for slide_id in all_slide_ids if slide_id not in deck_slide_ids]
            errors.append(
                "production plan slide ids must exactly match deck-spec.json slides"
                + (f"; missing: {', '.join(missing_from_plan)}" if missing_from_plan else "")
                + (f"; unknown: {', '.join(unknown_to_deck)}" if unknown_to_deck else "")
            )

    verification = plan.get("verification") if isinstance(plan.get("verification"), dict) else {}
    verified_slide_ids = verification.get("verified_slide_ids")
    if not isinstance(verified_slide_ids, list):
        verified_slide_ids = []
    if production_status == "verified":
        if verification.get("status") != "passed":
            errors.append("verified production requires verification.status passed")
        if set(str(item).strip() for item in verified_slide_ids) != set(all_slide_ids):
            errors.append("verified production requires verification.verified_slide_ids to match all planned slides")
        last_verified_at = timestamp_value(verification.get("last_verified_at"))
        if last_verified_at is None:
            errors.append("verified production requires verification.last_verified_at")
        for wave in waves:
            if not isinstance(wave, dict) or str(wave.get("status") or "").strip() == "abandoned":
                continue
            if str(wave.get("status") or "").strip() != "verified":
                errors.append("verified production requires every active wave to be verified")
            for agent in wave.get("agents") if isinstance(wave.get("agents"), list) else []:
                if not isinstance(agent, dict) or str(agent.get("status") or "").strip() == "abandoned":
                    continue
                if str(agent.get("status") or "").strip() != "verified":
                    errors.append("verified production requires every active agent to be verified")
        if last_verified_at is not None:
            for event in state.get("reopen_log") if isinstance(state.get("reopen_log"), list) else []:
                if not isinstance(event, dict):
                    continue
                reopened_at = timestamp_value(event.get("reopened_at"))
                if reopened_at is not None and reopened_at > last_verified_at:
                    errors.append(
                        "verified production is stale because reopen_log contains an event after last_verified_at"
                    )
                    break

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Proposal project directory")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors = validate_production_plan(project)
    if errors:
        print("Production plan validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Production plan valid: {project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
