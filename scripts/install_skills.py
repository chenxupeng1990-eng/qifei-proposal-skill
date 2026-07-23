#!/usr/bin/env python3
"""Install the complete proposal Skill suite into a Codex skills directory."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILLS = (
    "qifei-proposal",
    "grill-me-lite",
    "proposal-ppt-production",
    "ppt-html-calibration-editor",
)


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

    for name in SKILLS:
        source = ROOT / "skills" / name
        destination = target / name
        if not (source / "SKILL.md").is_file():
            raise SystemExit(f"Invalid Skill source: {source}")
        if destination.exists():
            if not args.force:
                raise SystemExit(
                    f"Refusing to replace {destination}; rerun with --force after reviewing it"
                )
            shutil.rmtree(destination)
        shutil.copytree(source, destination, ignore=ignore)
        print(f"Installed {name} -> {destination}")
        if not args.skip_deps:
            install_dependencies(destination)

    print("\nInstallation complete. Restart Codex, then invoke $qifei-proposal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
