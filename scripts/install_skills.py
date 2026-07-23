#!/usr/bin/env python3
"""Install the complete proposal Skill suite into a Codex skills directory."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SUITE_MANIFEST = ROOT / "skills" / "qifei-proposal" / "suite.json"


def ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        name
        for name in names
        if name in {"node_modules", "__pycache__", ".DS_Store", "tmp", "exports"}
        or name.endswith(".pyc")
    }
    return ignored


def install_dependencies(skill: Path) -> None:
    package = skill / "package.json"
    if not package.is_file():
        return
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm is required to install Skill runtime dependencies")
    command = [npm, "ci", "--no-audit", "--no-fund"] if (skill / "package-lock.json").is_file() else [npm, "install", "--no-audit", "--no-fund"]
    print(f"$ {' '.join(command)}  # {skill.name}")
    completed = subprocess.run(command, cwd=skill, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def load_suite() -> list[str]:
    data = json.loads(SUITE_MANIFEST.read_text(encoding="utf-8"))
    skills = [str(item["name"]) for item in data.get("skills") or []]
    if not skills:
        raise SystemExit(f"Suite manifest contains no Skills: {SUITE_MANIFEST}")
    return skills


def validate_skill(skill: Path, expected_name: str) -> None:
    entrypoint = skill / "SKILL.md"
    if not entrypoint.is_file():
        raise SystemExit(f"Invalid Skill source: {skill}")
    text = entrypoint.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)
    if not match or match.group(1) != expected_name:
        raise SystemExit(f"Invalid Skill metadata for {expected_name}: {entrypoint}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        default=str(Path.home() / ".codex" / "skills"),
        help="Codex skills directory; defaults to ~/.codex/skills",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing directories with the same Skill names",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Copy files without installing Node dependencies",
    )
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    skills = load_suite()
    sources = {name: ROOT / "skills" / name for name in skills}
    destinations = {name: target / name for name in skills}
    for name, source in sources.items():
        validate_skill(source, name)
    existing = [path for path in destinations.values() if path.exists()]
    if existing and not args.force:
        joined = "\n- ".join(str(path) for path in existing)
        raise SystemExit(
            f"Refusing to replace existing Skill directories:\n- {joined}\n"
            "Rerun with --force after reviewing them. No files were installed."
        )

    transaction = Path(tempfile.mkdtemp(prefix=".proposal-suite-install-", dir=target))
    staged = transaction / "staged"
    backup = transaction / "backup"
    installed: list[str] = []
    moved_backups: list[str] = []
    try:
        for name, source in sources.items():
            stage = staged / name
            shutil.copytree(source, stage, ignore=ignore)
            validate_skill(stage, name)
            if not args.skip_deps:
                install_dependencies(stage)
        for name, destination in destinations.items():
            if destination.exists():
                backup.mkdir(parents=True, exist_ok=True)
                os.replace(destination, backup / name)
                moved_backups.append(name)
            os.replace(staged / name, destination)
            installed.append(name)
            print(f"Installed {name} -> {destination}")
    except BaseException:
        for name in reversed(installed):
            destination = destinations[name]
            if destination.exists():
                shutil.rmtree(destination)
        for name in moved_backups:
            saved = backup / name
            if saved.exists():
                os.replace(saved, destinations[name])
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)

    print("\nInstallation complete. Restart Codex, then invoke $qifei-proposal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
