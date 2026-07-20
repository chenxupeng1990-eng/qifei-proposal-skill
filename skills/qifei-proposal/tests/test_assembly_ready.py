from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
MANAGER = SKILL_ROOT / "scripts" / "manage_assembly_ready.py"
INIT_PROJECT = SKILL_ROOT / "scripts" / "init_project.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_assembly_ready import validate_assembly_ready  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AssemblyReadyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        write_json(
            self.project / "project-state.json",
            {
                "project_id": "test-project",
                "proposal_owner": "Owner",
                "phase": "review",
                "content_freeze_id": "freeze-1",
                "design_version": "design-1",
                "assembly": {
                    "manifest_path": "deck/assembly-ready/manifest.json",
                    "status": "collecting",
                    "ready_slide_ids": [],
                    "final_approval_record_id": None,
                },
                "approvals": {
                    "final_assembly": {"approved": False, "by": None, "at": None, "record_id": None}
                },
                "reopen_log": [],
            },
        )
        write_json(
            self.project / "deck" / "deck-spec.json",
            {
                "content_freeze_id": "freeze-1",
                "design_version": "design-1",
                "slides": [
                    {"slide_id": "S01", "approved_content_hash": "hash-01"},
                    {"slide_id": "S02", "approved_content_hash": "hash-02"},
                ],
            },
        )
        write_json(
            self.project / "deck" / "assembly-ready" / "manifest.json",
            {
                "schema_version": "1.0",
                "project_id": "test-project",
                "content_freeze_id": None,
                "design_version": None,
                "status": "collecting",
                "pages": [],
                "final_assembly": {"approved": False, "by": None, "at": None, "record_id": None},
            },
        )
        html = self.project / "deck" / "chapters" / "C1.html"
        html.parent.mkdir(parents=True, exist_ok=True)
        html.write_text("<html>review</html>\n", encoding="utf-8")
        build = self.project / "deck" / "chapters" / "C1.build-manifest.json"
        write_json(build, {"build_id": "build-1"})
        review_dir = self.project / "deck" / "review" / "C1"
        review_dir.mkdir(parents=True, exist_ok=True)
        review_pages = []
        for slide_id in ("S01", "S02"):
            png = review_dir / f"{slide_id}.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + slide_id.encode("ascii"))
            review_pages.append(
                {
                    "slide_id": slide_id,
                    "png_path": str(png.relative_to(self.project)).replace("\\", "/"),
                    "png_sha256": sha256(png),
                }
            )
        self.review_manifest = review_dir / "review-manifest.json"
        write_json(
            self.review_manifest,
            {
                "schema_version": "1.0",
                "project_id": "test-project",
                "build_id": "build-1",
                "content_freeze_id": "freeze-1",
                "design_version": "design-1",
                "html_path": "deck/chapters/C1.html",
                "html_sha256": sha256(html),
                "build_manifest_path": "deck/chapters/C1.build-manifest.json",
                "build_manifest_sha256": sha256(build),
                "pages": review_pages,
            },
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_manager(self, *args: str, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(MANAGER), str(self.project), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if expect_ok and result.returncode != 0:
            self.fail(result.stdout + result.stderr)
        if not expect_ok and result.returncode == 0:
            self.fail("Command unexpectedly succeeded")
        return result

    def test_explicit_page_approval_finalization_and_reopen(self) -> None:
        review_rel = str(self.review_manifest.relative_to(self.project)).replace("\\", "/")
        self.run_manager(
            "approve", "--review-manifest", review_rel, "--slide-id", "S01",
            "--approved-by", "Owner", "--approval-id", "page-approval-1",
        )
        self.assertTrue(any("S02" in error for error in validate_assembly_ready(self.project)))
        self.run_manager(
            "finalize", "--approved-by", "Owner", "--approval-id", "final-too-early", expect_ok=False,
        )

        self.run_manager(
            "approve", "--review-manifest", review_rel, "--slide-id", "S02",
            "--approved-by", "Owner", "--approval-id", "page-approval-2",
        )
        self.assertEqual(validate_assembly_ready(self.project), [])
        self.run_manager(
            "finalize", "--approved-by", "Owner", "--approval-id", "final-approval-1",
        )
        self.assertEqual(validate_assembly_ready(self.project, require_final=True), [])

        self.run_manager(
            "reopen", "--slide-id", "S01", "--approved-by", "Owner", "--reason", "layout revision",
        )
        errors = validate_assembly_ready(self.project, require_final=True)
        self.assertTrue(any("S01" in error for error in errors))
        state = json.loads((self.project / "project-state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["approvals"]["final_assembly"]["approved"])

    def test_initialized_project_has_an_empty_assembly_library(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "proposal"
            result = subprocess.run(
                [
                    sys.executable,
                    str(INIT_PROJECT),
                    "--project", str(target),
                    "--name", "Assembly Template Test",
                    "--owner", "Owner",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = json.loads((target / "project-state.json").read_text(encoding="utf-8"))
            manifest = json.loads((target / "deck" / "assembly-ready" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(state["assembly"]["manifest_path"], "deck/assembly-ready/manifest.json")
            self.assertEqual(state["assembly"]["status"], "collecting")
            self.assertEqual(manifest["pages"], [])
            self.assertFalse(state["approvals"]["final_assembly"]["approved"])


if __name__ == "__main__":
    unittest.main()
