from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from freeze_deck_spec import content_hash  # noqa: E402
from validate_deck_spec import valid_local_media, visual_length  # noqa: E402
from validate_project import validate_project  # noqa: E402


class ContractTests(unittest.TestCase):
    def test_visual_length_weights_cjk_more_than_ascii(self) -> None:
        self.assertEqual(visual_length("中文AB"), 3.0)

    def test_content_hash_changes_with_public_copy(self) -> None:
        slide = {
            "chapter": "A",
            "role": "statement",
            "layout": "statement",
            "title": "结论一",
            "subtitle": "",
            "kicker": "",
            "blocks": [],
            "visual": {},
            "evidence_ids": [],
            "speaker_doc_anchor": "demo://P01",
        }
        original = content_hash(slide)
        slide["title"] = "结论二"
        self.assertNotEqual(original, content_hash(slide))

    def test_media_must_be_local_and_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            asset = project / "assets" / "image2" / "hero.png"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"png")
            self.assertIsNone(valid_local_media(project, "assets/image2/hero.png"))
            self.assertIsNotNone(valid_local_media(project, "https://example.com/hero.png"))
            self.assertIsNotNone(valid_local_media(project, "../hero.png"))

    def test_export_phase_requires_both_qa_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            state = {
                "phase": "export",
                "proposal_owner": "Owner",
                "content_freeze_id": "freeze-v1",
                "design_version": "design-v1",
                "approvals": {},
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("content_qa" in error for error in errors))
            self.assertTrue(any("visual_qa" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
