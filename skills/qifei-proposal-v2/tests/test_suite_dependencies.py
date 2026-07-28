from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CHECKER = SKILL_ROOT / "scripts" / "check_suite_dependencies.py"


class SuiteDependencyTests(unittest.TestCase):
    def write_skill(self, root: Path, name: str) -> None:
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    def test_missing_recommended_skill_warns_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_skill(root, "qifei-proposal-v2")
            self.write_skill(root, "grill-me-lite")
            result = subprocess.run(
                ["python3", str(CHECKER), "--skills-root", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("missing recommended Skill: proposal-ppt-production", result.stdout)

    def test_missing_required_skill_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["python3", str(CHECKER), "--skills-root", tmp],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required Skill", result.stdout)


if __name__ == "__main__":
    unittest.main()
