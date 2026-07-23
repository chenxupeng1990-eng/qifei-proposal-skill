from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CHECK = SKILL_ROOT / "scripts" / "check_environment.mjs"
REAL_MODULES = SKILL_ROOT / "node_modules"
PACKAGES = ("playwright-core", "pdf-lib", "pptxgenjs", "jszip")


class EnvironmentCheckTests(unittest.TestCase):
    def run_check(self, root: Path, **extra_env: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PROPOSAL_ENV_ROOT"] = str(root)
        env.update(extra_env)
        return subprocess.run(
            ["node", str(CHECK)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def fixture(self, root: Path, missing: str | None = None) -> None:
        (root / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
        modules = root / "node_modules"
        modules.mkdir()
        for package in PACKAGES:
            if package != missing:
                (modules / package).symlink_to(REAL_MODULES / package, target_is_directory=True)

    def test_missing_node_modules_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
            result = self.run_check(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL node_modules", result.stdout)

    def test_each_missing_package_is_named(self) -> None:
        for package in PACKAGES:
            with self.subTest(package=package), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, missing=package)
                result = self.run_check(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"FAIL Node package {package}", result.stdout)

    def test_existing_but_unlaunchable_browser_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            fake = root / "fake-browser"
            fake.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            result = self.run_check(root, CHROME_PATH=str(fake), EDGE_PATH="")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL Chromium launch", result.stdout)

    @unittest.skipUnless(
        shutil.which("npm") and (
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").is_file()
            or Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge").is_file()
        ),
        "requires npm and an installed Chromium browser",
    )
    def test_real_runtime_passes(self) -> None:
        result = self.run_check(SKILL_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for package in PACKAGES:
            self.assertIn(f"PASS Node package {package}", result.stdout)
        self.assertIn("PASS Chromium launch", result.stdout)


if __name__ == "__main__":
    unittest.main()
