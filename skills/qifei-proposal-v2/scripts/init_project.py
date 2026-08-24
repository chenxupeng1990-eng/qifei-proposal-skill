#!/usr/bin/env python3
"""Initialize a gated company proposal project without overwriting existing work."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import uuid
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"
MODULE_TEMPLATE_ROOT = SKILL_ROOT / "assets" / "module-template"
REQUIRED_DIRS = (
    "inputs/client",
    "inputs/brand-official",
    "inputs/temporary-references",
    "evidence",
    "content/strategy",
    "content/chapters",
    "reviews/redteam",
    "reviews/design-loop",
    "assets/source",
    "assets/image2",
    "assets/image2/alpha",
    "assets/approved",
    "assets/approved/alpha",
    "deck",
    "deck/chapters",
    "deck/review",
    "deck/assembly-ready/pages",
    "exports/png",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project directory to create or adopt")
    parser.add_argument("--name", required=True, help="Human-readable project name")
    parser.add_argument("--owner", required=True, help="Proposal Owner")
    parser.add_argument("--project-id", help="Stable project id; generated when omitted")
    parser.add_argument(
        "--task-mode",
        choices=("full_deck", "inherited_module", "standalone_module"),
        default="full_deck",
        help="Governance scope for a full deck or a bounded content module",
    )
    parser.add_argument(
        "--deliverable-level",
        choices=("content", "slides", "export"),
        help="Stop at confirmed content, reviewed slides, or final export",
    )
    parser.add_argument(
        "--content-authority",
        choices=("feishu", "local"),
        help="Override the default content authority for full or standalone work",
    )
    parser.add_argument(
        "--parent-project",
        help="Existing governed project to inherit strategy and design from",
    )
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Create only missing files/directories in an existing project",
    )
    return parser.parse_args()


def render_template(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{INIT:" + key + "}}", value)
    return text


def copy_templates(target: Path, values: dict[str, str], adopt_existing: bool) -> list[str]:
    created: list[str] = []
    for source in TEMPLATE_ROOT.rglob("*"):
        if source.is_dir():
            continue
        relative = source.relative_to(TEMPLATE_ROOT)
        destination = target / relative
        if destination.exists():
            if adopt_existing:
                continue
            raise FileExistsError(f"Refusing to overwrite existing file: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(source, destination)
        else:
            destination.write_text(render_template(text, values), encoding="utf-8")
        created.append(str(relative).replace("\\", "/"))
    return created


def overlay_module_templates(
    target: Path,
    values: dict[str, str],
    allowed_paths: set[str],
) -> list[str]:
    overlaid: list[str] = []
    for source in MODULE_TEMPLATE_ROOT.rglob("*"):
        if source.is_dir():
            continue
        relative = source.relative_to(MODULE_TEMPLATE_ROOT)
        normalized = str(relative).replace("\\", "/")
        if normalized not in allowed_paths:
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render_template(source.read_text(encoding="utf-8"), values),
            encoding="utf-8",
        )
        overlaid.append(normalized)
    return overlaid


def main() -> int:
    args = parse_args()
    if args.task_mode == "inherited_module" and not args.parent_project:
        raise SystemExit("inherited_module requires --parent-project")
    if args.task_mode != "inherited_module" and args.parent_project:
        raise SystemExit("--parent-project is only valid for inherited_module")

    parent_state: dict = {}
    parent_root: Path | None = None
    if args.parent_project:
        parent_root = Path(args.parent_project).expanduser().resolve()
        state_path = parent_root / "project-state.json"
        if not state_path.is_file():
            raise SystemExit(f"Parent project is missing project-state.json: {parent_root}")
        parent_state = json.loads(state_path.read_text(encoding="utf-8"))
        if not parent_state.get("content_freeze_id") or not parent_state.get("design_version"):
            raise SystemExit("inherited_module requires a parent content freeze and approved design version")
    target = Path(args.project).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not args.adopt_existing:
        raise SystemExit("Project directory is not empty; use --adopt-existing to add only missing files.")
    target.mkdir(parents=True, exist_ok=True)
    for relative in REQUIRED_DIRS:
        (target / relative).mkdir(parents=True, exist_ok=True)

    project_id = args.project_id or f"qfp-{uuid.uuid4().hex[:10]}"
    deliverable_level = args.deliverable_level or ("export" if args.task_mode == "full_deck" else "slides")
    if args.task_mode == "inherited_module":
        content_authority = "inherit_parent"
    else:
        content_authority = args.content_authority or ("feishu" if args.task_mode == "full_deck" else "local")
    values = {
        "PROJECT_ID": project_id,
        "PROJECT_NAME": args.name,
        "OWNER": args.owner,
        "CREATED_AT": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "TASK_MODE": args.task_mode,
        "DELIVERABLE_LEVEL": deliverable_level,
        "CONTENT_AUTHORITY": content_authority,
    }
    created = copy_templates(target, values, args.adopt_existing)
    if args.task_mode != "full_deck":
        created.extend(overlay_module_templates(target, values, set(created)))
    state_path = target / "project-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update({
        "task_mode": args.task_mode,
        "deliverable_level": deliverable_level,
        "content_authority": content_authority,
        "module_context": None,
    })
    if content_authority == "local":
        state["proposal_draft"]["authority"] = "local"
    if args.task_mode != "full_deck":
        state["module_context"] = {
            "module_id": project_id,
            "parent_project_id": parent_state.get("project_id") if parent_state else None,
            "inherited_content_freeze_id": parent_state.get("content_freeze_id") if parent_state else None,
            "inherited_design_version": parent_state.get("design_version") if parent_state else None,
            "strategy_input": None,
            "module_claim": None,
            "strategy_output": None,
        }
    if parent_state:
        state["content_freeze_id"] = parent_state["content_freeze_id"]
        state["design_version"] = parent_state["design_version"]
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if parent_root:
        for relative in ("DESIGN.md", "deck/design-tokens.json"):
            source = parent_root / relative
            if not source.is_file():
                raise SystemExit(f"Parent project is missing inherited design artifact: {relative}")
            shutil.copy2(source, target / relative)
    print(f"Initialized proposal project: {target}")
    print(f"Project id: {project_id}")
    print(f"Task mode: {args.task_mode}; deliverable level: {deliverable_level}")
    print(f"Created {len(created)} template file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
