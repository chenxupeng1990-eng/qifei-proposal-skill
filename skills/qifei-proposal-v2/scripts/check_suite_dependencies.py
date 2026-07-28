#!/usr/bin/env python3
"""Fail fast when required Skills from the proposal suite are missing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = SKILL_ROOT / "suite.json"


def skill_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


def check(skills_root: Path) -> tuple[list[str], list[str]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    for item in manifest.get("skills") or []:
        requirement = str(item.get("requirement") or "")
        if requirement == "optional":
            continue
        name = str(item.get("name") or "")
        entrypoint = skills_root / name / "SKILL.md"
        if not entrypoint.is_file():
            message = f"missing {requirement} Skill: {name}"
            if requirement == "required":
                errors.append(message)
            elif requirement == "recommended":
                warnings.append(message)
        elif skill_name(entrypoint) != name:
            message = f"invalid {requirement} Skill metadata: {name}"
            if requirement == "required":
                errors.append(message)
            elif requirement == "recommended":
                warnings.append(message)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skills-root",
        default=str(SKILL_ROOT.parent),
        help="Directory containing installed Skill folders",
    )
    args = parser.parse_args()
    errors, warnings = check(Path(args.skills_root).expanduser().resolve())
    if warnings:
        print("Proposal Skill suite dependency warnings:")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("Proposal Skill suite dependency check failed:")
        for error in errors:
            print(f"- {error}")
        repository = json.loads(MANIFEST.read_text(encoding="utf-8"))["repository"]
        print("\nInstall the complete suite:")
        print(f"git clone {repository}")
        print("cd qifei-proposal-skill")
        print("python3 scripts/install_skills.py --force")
        return 1
    print("PASS Proposal Skill suite: all required Skills are installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
