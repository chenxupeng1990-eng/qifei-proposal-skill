#!/usr/bin/env python3
"""Install locked runtime dependencies and run the repository self-test."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NODE_PACKAGES = {
    "v1": (
        ROOT / "skills" / "qifei-proposal",
        ROOT / "skills" / "ppt-html-calibration-editor",
    ),
    "v2": (
        ROOT / "skills" / "qifei-proposal-v2",
        ROOT / "skills" / "ppt-html-calibration-editor",
    ),
}


def run(command: list[str], cwd: Path | None = None) -> None:
    print(f"\n$ {' '.join(command)}")
    completed = subprocess.run(command, cwd=cwd or ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=sorted(NODE_PACKAGES),
        default="v1",
        help="Runtime suite to prepare; defaults to V1 compatibility",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm ci and only run the self-test",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Also require a clean Git worktree",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 9):
        raise SystemExit(f"Python 3.9+ is required; found {sys.version.split()[0]}")

    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        raise SystemExit("Node.js 18+ and npm are required")

    if not args.skip_install:
        for package in NODE_PACKAGES[args.suite]:
            lockfile = package / "package-lock.json"
            if not lockfile.is_file():
                raise SystemExit(f"Missing lockfile: {lockfile}")
            run([npm, "ci", "--no-audit", "--no-fund"], cwd=package)

    if args.suite == "v1":
        command = [sys.executable, str(ROOT / "scripts" / "self_test.py")]
        if args.release:
            command.append("--release")
        run(command)
    else:
        v2 = ROOT / "skills" / "qifei-proposal-v2"
        run(["node", str(v2 / "scripts" / "check_environment.mjs")], cwd=v2)
        run([
            sys.executable, "-m", "unittest", "discover",
            "-s", str(v2 / "tests"), "-p", "test_*.py",
        ])
        run([
            sys.executable, "-m", "unittest", "discover",
            "-s", str(ROOT / "tests"), "-p", "test_*.py",
        ])
        if args.release:
            completed = subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
            )
            if completed.stdout.strip():
                raise SystemExit("Release check requires a clean Git worktree")
    print("\nBootstrap complete. The Skill suite is ready for installation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
