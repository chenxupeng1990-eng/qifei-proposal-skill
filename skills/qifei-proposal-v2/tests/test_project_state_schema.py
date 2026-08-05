from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_project import validate_project  # noqa: E402


class ProjectStateSchemaTests(unittest.TestCase):
    def initialize(self, project: Path) -> dict:
        result = subprocess.run(
            [
                "python3",
                str(SCRIPTS / "init_project.py"),
                "--project",
                str(project),
                "--name",
                "Schema Fixture",
                "--owner",
                "Owner",
                "--project-id",
                "fixture-001",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads((project / "project-state.json").read_text(encoding="utf-8"))

    def test_initialized_project_passes_schema_and_intake_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            self.initialize(project)
            self.assertEqual(validate_project(project), [])

    def test_schema_rejects_unknown_state_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["silent_drift"] = True
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertTrue(any("unexpected property 'silent_drift'" in error for error in errors))

    def test_schema_rejects_wrong_nested_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["assembly"]["ready_slide_ids"] = "P01"
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertTrue(any("$.assembly.ready_slide_ids: expected type array" in error for error in errors))

    def test_schema_rejects_empty_chapter_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["chapters"] = [{}]
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertTrue(any("missing required property 'chapter_id'" in error for error in errors))
            self.assertTrue(any("missing required property 'slides'" in error for error in errors))

    def test_schema_rejects_non_iso_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["created_at"] = "today"
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertTrue(any("$.created_at: string does not match pattern" in error for error in errors))

    def test_schema_accepts_runtime_final_assembly_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["assembly"]["status"] = "final_approved"
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
            self.assertFalse(any("$.assembly.status" in error for error in validate_project(project)))

    def test_schema_accepts_runtime_reopen_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["reopen_log"] = [{
                "reopened_at": "2026-08-05T10:00:00+08:00",
                "scope": "assembly_ready",
                "slide_id": "P01",
                "reason": "调整临时插页",
                "reopened_by": "Owner",
            }]
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
            self.assertFalse(any("$.reopen_log" in error for error in validate_project(project)))

    def test_schema_accepts_design_loop_record_id_on_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["chapters"] = [{
                "chapter_id": "C1",
                "slides": ["P01"],
                "design_loop_record_id": "APR-DESIGN-C1",
            }]
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )
            self.assertFalse(any("design_loop_record_id" in error for error in validate_project(project)))

    def test_verified_speaker_notes_must_match_final_slide_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            deck_path = project / "deck" / "deck-spec.json"
            deck = json.loads(deck_path.read_text(encoding="utf-8"))
            deck["slides"] = [{"slide_id": "P01"}, {"slide_id": "P02"}]
            deck_path.write_text(json.dumps(deck), encoding="utf-8")
            notes_path = project / "content" / "speaker-notes.md"
            notes_path.write_text("P01\nP02\n", encoding="utf-8")
            state["speaker_notes"].update({
                "status": "verified",
                "final_slide_count": 2,
                "final_order_hash": hashlib.sha256(b"P01\nP02").hexdigest(),
                "feishu_doc_url": "https://example.feishu.cn/docx/notes",
            })
            state["approvals"]["speaker_notes"] = {
                "approved": True,
                "by": "Owner",
                "at": "2026-08-05T10:00:00+08:00",
                "record_id": "APR-NOTES",
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            self.assertFalse(any("speaker_notes." in error for error in validate_project(project)))

            state["speaker_notes"]["final_order_hash"] = "stale"
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            self.assertTrue(any("final_order_hash" in error for error in validate_project(project)))

    def test_project_agents_phase_blocks_required_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            state = self.initialize(project)
            state["phase"] = "project_agents"
            for gate in (
                "materials_scope",
                "brief_grill",
                "proposal_brief",
                "requirements",
                "strategy",
                "outline",
            ):
                state["approvals"][gate] = {
                    "approved": True,
                    "by": "Owner",
                    "at": "2026-07-29T10:00:00+08:00",
                    "record_id": f"APR-{gate}",
                }
            (project / "content" / "proposal-brief.md").write_text(
                "已确认的项目策划书。",
                encoding="utf-8",
            )
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertTrue(any("PROJECT_AGENTS:CLIENT_NAME" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
