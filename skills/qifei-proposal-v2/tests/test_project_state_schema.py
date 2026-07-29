from __future__ import annotations

import json
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
