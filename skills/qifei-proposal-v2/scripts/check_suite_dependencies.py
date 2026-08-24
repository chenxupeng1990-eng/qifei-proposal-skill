#!/usr/bin/env python3
"""Fail fast when required Skills from the proposal suite are missing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = SKILL_ROOT / "suite.json"
CONTRACTS = SKILL_ROOT / "references" / "integration-contracts.json"


def skill_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


def check(skills_root: Path) -> tuple[list[str], list[str]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract_manifest = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    contracts = contract_manifest.get("contracts") if isinstance(contract_manifest.get("contracts"), dict) else {}
    errors: list[str] = []
    warnings: list[str] = []
    installed_self = skills_root / "qifei-proposal-v2"
    for relative in (manifest.get("self_integrity") or {}).get("required_files") or []:
        if not (installed_self / str(relative)).is_file():
            errors.append(f"incomplete qifei-proposal-v2 installation: missing {relative}")
    for item in manifest.get("skills") or []:
        requirement = str(item.get("requirement") or "")
        name = str(item.get("name") or "")
        contract_id = str(item.get("interface_contract") or "")
        if name != "qifei-proposal-v2":
            contract = contracts.get(contract_id)
            if not contract_id or not isinstance(contract, dict):
                errors.append(f"missing interface contract for Skill: {name}")
            elif (
                contract.get("provider_skill") != name
                or not contract.get("fallback")
                or contract.get("contract_version") != item.get("contract_version")
            ):
                errors.append(f"invalid interface contract {contract_id}: {name}")
        if requirement == "optional":
            continue
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
        print("python3 scripts/install_skills.py --suite v2 --force")
        return 1
    print("PASS Proposal Skill suite: all required Skills are installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
