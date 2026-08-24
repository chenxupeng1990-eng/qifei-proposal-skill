from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_skills.py"
CHECKER = ROOT / "skills" / "qifei-proposal" / "scripts" / "check_suite_dependencies.py"
SUITE = ROOT / "skills" / "qifei-proposal" / "suite.json"


class InstallSkillsTests(unittest.TestCase):
    def run_install(self, target: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALLER), "--target", str(target), "--skip-deps", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_manifest_declares_required_and_optional_roles(self) -> None:
        items = {item["name"]: item["requirement"] for item in json.loads(SUITE.read_text())["skills"]}
        self.assertEqual(items["qifei-proposal"], "required")
        self.assertEqual(items["grill-me-lite"], "required")
        self.assertEqual(items["proposal-ppt-production"], "recommended")
        self.assertEqual(items["ppt-html-calibration-editor"], "optional")

    def test_missing_grill_me_fails_startup_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "qifei-proposal").mkdir()
            (root / "qifei-proposal" / "SKILL.md").write_text(
                "---\nname: qifei-proposal\ndescription: test\n---\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(CHECKER), "--skills-root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required Skill: grill-me-lite", result.stdout)
            self.assertIn("python3 scripts/install_skills.py --force", result.stdout)

    def test_complete_install_has_valid_metadata_and_passes_startup_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = self.run_install(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for item in json.loads(SUITE.read_text())["skills"]:
                text = (target / item["name"] / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(f"name: {item['name']}", text)
            check = subprocess.run(
                [sys.executable, str(CHECKER), "--skills-root", str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_existing_directory_aborts_before_any_partial_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            existing = target / "grill-me-lite"
            existing.mkdir()
            marker = existing / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            result = self.run_install(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            self.assertFalse((target / "qifei-proposal").exists())
            self.assertFalse((target / "proposal-ppt-production").exists())
            self.assertFalse((target / "ppt-html-calibration-editor").exists())

    def test_v2_suite_installs_v2_entrypoint_and_passes_its_startup_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            result = self.run_install(target, "--suite", "v2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "qifei-proposal-v2" / "SKILL.md").is_file())
            self.assertFalse((target / "qifei-proposal").exists())

            checker = target / "qifei-proposal-v2" / "scripts" / "check_suite_dependencies.py"
            check = subprocess.run(
                [sys.executable, str(checker), "--skills-root", str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
