#!/usr/bin/env python3
"""Initialize a gated QIFEI proposal project without overwriting existing work."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import uuid
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"
REQUIRED_DIRS = (
    "inputs/client",
    "inputs/temporary-references",
    "evidence",
    "content/strategy",
    "content/chapters",
    "reviews/redteam",
    "assets/source",
    "assets/image2",
    "assets/approved",
    "deck",
    "exports/png",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project directory to create or adopt")
    parser.add_argument("--name", required=True, help="Human-readable project name")
    parser.add_argument("--owner", required=True, help="Proposal Owner")
    parser.add_argument("--project-id", help="Stable project id; generated when omitted")
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Create only missing files/directories in an existing project",
    )
    return parser.parse_args()


def render_template(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
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


def main() -> int:
    args = parse_args()
    target = Path(args.project).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not args.adopt_existing:
        raise SystemExit("Project directory is not empty; use --adopt-existing to add only missing files.")
    target.mkdir(parents=True, exist_ok=True)
    for relative in REQUIRED_DIRS:
        (target / relative).mkdir(parents=True, exist_ok=True)

    project_id = args.project_id or f"qfp-{uuid.uuid4().hex[:10]}"
    values = {
        "PROJECT_ID": project_id,
        "PROJECT_NAME": args.name,
        "OWNER": args.owner,
        "CREATED_AT": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    created = copy_templates(target, values, args.adopt_existing)
    print(f"Initialized proposal project: {target}")
    print(f"Project id: {project_id}")
    print(f"Created {len(created)} template file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
