#!/usr/bin/env python3
"""Run cross-platform structural, runtime, and clean-project smoke tests."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILLS = (
    "qifei-proposal",
    "grill-me-lite",
    "proposal-ppt-production",
    "ppt-html-calibration-editor",
)
IGNORED_PARTS = {".git", "node_modules", "tmp", "dist", "__pycache__", "exports"}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".svg",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_TEXT = (
    "伊" + "利",
    "yili" + "-bone",
    "/Users/" + "allbychen",
    "my.feishu.cn/" + "docx/",
)
FORBIDDEN_TRACKED_SUFFIXES = (".pdf", ".ppt", ".pptx", ".key")


def command_path(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Required command not found: {name}")
    return path


def run(label: str, command: list[str], cwd: Path | None = None) -> None:
    print(f"\n[{label}]")
    completed = subprocess.run(command, cwd=cwd or ROOT, check=False)
    if completed.returncode:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def check_skill_frontmatter() -> None:
    errors: list[str] = []
    for skill in SKILLS:
        path = ROOT / "skills" / skill / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not match:
            errors.append(f"invalid frontmatter in {path.relative_to(ROOT)}")
            continue
        header = match.group(1)
        if not re.search(rf"^name:\s*{re.escape(skill)}\s*$", header, re.MULTILINE):
            errors.append(f"name mismatch in {path.relative_to(ROOT)}")
        if not re.search(r"^description:\s*\S", header, re.MULTILINE):
            errors.append(f"missing description in {path.relative_to(ROOT)}")
    if errors:
        raise SystemExit("Skill metadata check failed:\n- " + "\n- ".join(errors))
    print(f"PASS Skill metadata: {len(SKILLS)} skills")


def iter_release_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"VERSION"}:
            files.append(path)
    return files


def check_release_content() -> None:
    errors: list[str] = []
    for path in iter_release_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for forbidden in FORBIDDEN_TEXT:
            if forbidden in text:
                errors.append(f"{path.relative_to(ROOT)} contains {forbidden!r}")

    git = shutil.which("git")
    if git and (ROOT / ".git").exists():
        listed = subprocess.run(
            [git, "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        for name in listed:
            if name.lower().endswith(FORBIDDEN_TRACKED_SUFFIXES):
                errors.append(f"tracked customer/delivery artifact: {name}")

    if errors:
        raise SystemExit("Release-content check failed:\n- " + "\n- ".join(errors))
    print("PASS Release content: no customer identifiers, local paths, or tracked delivery files")


def check_json_files() -> None:
    targets = (
        ROOT / "skills" / "qifei-proposal" / "references" / "company-facts.json",
        ROOT / "skills" / "proposal-ppt-production" / "assets" / "page-contract.example.json",
    )
    for path in targets:
        json.loads(path.read_text(encoding="utf-8"))
    print(f"PASS JSON parse: {len(targets)} files")


def check_clean_worktree() -> None:
    git = command_path("git")
    completed = subprocess.run(
        [git, "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip():
        raise SystemExit("Release check requires a clean Git worktree")
    print("PASS Git worktree: clean")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release",
        action="store_true",
        help="Require a clean Git worktree after all other checks",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 9):
        raise SystemExit(f"Python 3.9+ is required; found {sys.version.split()[0]}")

    node = command_path("node")
    npm = command_path("npm")

    check_skill_frontmatter()
    check_release_content()
    check_json_files()

    qifei = ROOT / "skills" / "qifei-proposal"
    editor = ROOT / "skills" / "ppt-html-calibration-editor"
    production = ROOT / "skills" / "proposal-ppt-production"

    run("Environment", [npm, "run", "check:env"], cwd=qifei)
    run(
        "Python tests",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(qifei / "tests"),
            "-p",
            "test_*.py",
        ],
    )
    run("HTML editor contract", [npm, "test"], cwd=editor)
    run(
        "Page-contract validator",
        [
            node,
            str(production / "scripts" / "validate_page_contracts.mjs"),
            str(production / "assets" / "page-contract.example.json"),
        ],
    )
    run(
        "JavaScript syntax",
        [node, "--check", str(qifei / "scripts" / "export_deck.mjs")],
    )
    run(
        "Editable PPTX compiler syntax",
        [node, "--check", str(qifei / "scripts" / "compile_editable_pptx.mjs")],
    )

    with tempfile.TemporaryDirectory(prefix="proposal-skill-smoke-") as temp:
        temp_root = Path(temp)
        project = temp_root / "clean-project"
        run(
            "Fresh project initialization",
            [
                sys.executable,
                str(qifei / "scripts" / "init_project.py"),
                "--project",
                str(project),
                "--name",
                "Clean Install Smoke Test",
                "--owner",
                "Test Owner",
            ],
        )
        run(
            "Fresh project validation",
            [sys.executable, str(qifei / "scripts" / "validate_project.py"), str(project)],
        )
        install_target = temp_root / "installed-skills"
        run(
            "Skill installation",
            [
                sys.executable,
                str(ROOT / "scripts" / "install_skills.py"),
                "--target",
                str(install_target),
                "--skip-deps",
            ],
        )
        installed = sorted(path.name for path in install_target.iterdir() if path.is_dir())
        if installed != sorted(SKILLS):
            raise SystemExit(f"Installed Skill set mismatch: {installed}")

    if args.release:
        check_clean_worktree()

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
