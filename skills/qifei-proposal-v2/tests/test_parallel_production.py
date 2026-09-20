from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_production_plan import validate_production_plan  # noqa: E402


class ParallelProductionTests(unittest.TestCase):
    @staticmethod
    def approved(record_id: str) -> dict:
        return {
            "approved": True,
            "by": "Owner",
            "at": "2026-08-25T10:00:00+08:00",
            "record_id": record_id,
        }

    def state(self) -> dict:
        return {
            "project_id": "project-001",
            "task_mode": "full_deck",
            "content_freeze_id": "CF-001",
            "design_version": "DESIGN-001",
            "proposal_draft": {
                "authority": "feishu",
                "status": "verified",
                "format_version": "feishu-proposal-draft-v1",
                "feishu_doc_url": "https://example.feishu.cn/docx/doc-001",
                "document_id": "doc-001",
                "revision_id": 12,
                "last_verified_at": "2026-08-25T10:00:00+08:00",
                "verified_snapshot_path": "content/feishu/proposal-draft.md",
                "verified_snapshot_sha256": None,
                "verified_slide_ids": ["S01", "S02"],
            },
            "chapters": [{"chapter_id": "CH01", "slides": ["S01", "S02"]}],
            "reopen_log": [],
            "production": {
                "mode": "parallel_after_gates",
                "max_agents": 3,
                "plan_path": "deck/production/plan.json",
                "status": "ready",
            },
            "approvals": {
                "content_freeze": self.approved("CF-APPROVAL"),
                "design": self.approved("DESIGN-APPROVAL"),
                "generation_ready": self.approved("GEN-APPROVAL"),
            },
        }

    @staticmethod
    def valid_plan() -> dict:
        return {
            "schema_version": "1.0",
            "project_id": "project-001",
            "content_freeze_id": "CF-001",
            "design_version": "DESIGN-001",
            "manuscript_revision_id": 12,
            "max_agents": 3,
            "integration_owner": "main-agent",
            "shared_read_only": [
                "project-state.json",
                "AGENTS.md",
                "DESIGN.md",
                "deck/deck-spec.json",
                "deck/design-tokens.json",
                "deck/slide-contracts.json",
                "content/proposal-brief.md",
                "content/feishu/proposal-draft.md",
                "content/strategy/",
                "reviews/redteam/",
                "reviews/design-loop/",
                "deck/assembly-ready/",
            ],
            "waves": [{
                "wave_id": "W1",
                "status": "ready",
                "agents": [
                    {
                        "agent_id": "production-01",
                        "slide_ids": ["S01"],
                        "write_paths": [
                            "deck/chapters/CH01.html",
                            "deck/review/CH01/S01.png",
                        ],
                        "status": "ready",
                    },
                    {
                        "agent_id": "production-02",
                        "slide_ids": ["S02"],
                        "write_paths": [
                            "deck/chapters/CH02.html",
                            "deck/review/CH02/S02.png",
                        ],
                        "status": "ready",
                    },
                ],
            }],
            "verification": {
                "status": "pending",
                "verified_slide_ids": [],
                "last_verified_at": None,
            },
        }

    def write_fixture(self, root: Path, state: dict, plan: dict) -> None:
        plan_path = root / "deck" / "production" / "plan.json"
        plan_path.parent.mkdir(parents=True)
        snapshot_path = root / "content" / "feishu" / "proposal-draft.md"
        snapshot_path.parent.mkdir(parents=True)
        snapshot_bytes = b"# Confirmed Feishu proposal snapshot\n"
        snapshot_path.write_bytes(snapshot_bytes)
        state["proposal_draft"]["verified_snapshot_sha256"] = hashlib.sha256(snapshot_bytes).hexdigest()
        deck_path = root / "deck" / "deck-spec.json"
        deck_path.parent.mkdir(parents=True, exist_ok=True)
        deck_path.write_text(
            json.dumps({"slides": [{"slide_id": "S01"}, {"slide_id": "S02"}]}),
            encoding="utf-8",
        )
        (root / "project-state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    def test_valid_parallel_plan_passes_after_entry_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.write_fixture(project, self.state(), self.valid_plan())
            self.assertEqual(validate_production_plan(project), [])

    def test_parallel_plan_requires_content_design_and_generation_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.state()
            state["approvals"]["design"]["approved"] = False
            self.write_fixture(project, state, self.valid_plan())
            errors = validate_production_plan(project)
            self.assertTrue(any("design" in error for error in errors))

    def test_parallel_plan_rejects_more_than_six_agents_and_overlapping_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            plan = self.valid_plan()
            plan["max_agents"] = 7
            plan["waves"][0]["agents"][1]["slide_ids"] = ["S01"]
            plan["waves"][0]["agents"][1]["write_paths"] = ["deck/chapters/CH01.html"]
            self.write_fixture(project, self.state(), plan)
            errors = validate_production_plan(project)
            self.assertTrue(any("maximum is 6" in error for error in errors))
            self.assertTrue(any("slide id S01 is assigned more than once" in error for error in errors))
            self.assertTrue(any("write path" in error and "more than once" in error for error in errors))

    def test_parallel_plan_rejects_shared_authority_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            plan = self.valid_plan()
            plan["waves"][0]["agents"][0]["write_paths"].append("project-state.json")
            self.write_fixture(project, self.state(), plan)
            errors = validate_production_plan(project)
            self.assertTrue(any("reserved shared file" in error for error in errors))

    def test_verified_wave_requires_reverification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.state()
            state["production"]["status"] = "verified"
            plan = self.valid_plan()
            plan["verification"] = {
                "status": "passed",
                "verified_slide_ids": ["S01"],
                "last_verified_at": "2026-08-25T10:30:00+08:00",
            }
            self.write_fixture(project, state, plan)
            errors = validate_production_plan(project)
            self.assertTrue(any("verified_slide_ids" in error for error in errors))

    def test_abandoned_wave_can_reassign_its_slide_in_a_new_wave(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.state()
            plan = self.valid_plan()
            plan["waves"][0]["agents"][1]["status"] = "abandoned"
            plan["waves"].append({
                "wave_id": "W2",
                "status": "ready",
                "agents": [{
                    "agent_id": "production-03",
                    "slide_ids": ["S02"],
                    "write_paths": [
                        "deck/chapters/CH02.html",
                        "deck/review/CH02/S02.png",
                    ],
                    "status": "ready",
                }],
            })
            self.write_fixture(project, state, plan)
            self.assertEqual(validate_production_plan(project), [])

    def test_parallel_plan_must_cover_exact_deck_slide_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            plan = self.valid_plan()
            plan["waves"][0]["agents"][1]["slide_ids"] = ["S03"]
            self.write_fixture(project, self.state(), plan)
            errors = validate_production_plan(project)
            self.assertTrue(any("deck-spec" in error and "slide" in error for error in errors))

    def test_parallel_plan_requires_feishu_snapshot_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.state()
            state["proposal_draft"]["revision_id"] = None
            state["proposal_draft"]["verified_snapshot_path"] = None
            state["proposal_draft"]["verified_snapshot_sha256"] = None
            self.write_fixture(project, state, self.valid_plan())
            errors = validate_production_plan(project)
            self.assertTrue(any("revision_id" in error for error in errors))
            self.assertTrue(any("verified_snapshot_path" in error for error in errors))

    def test_verified_production_requires_completed_wave_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.state()
            state["production"]["status"] = "verified"
            plan = self.valid_plan()
            plan["verification"] = {
                "status": "passed",
                "verified_slide_ids": ["S01", "S02"],
                "last_verified_at": "2026-08-25T10:30:00+08:00",
            }
            self.write_fixture(project, state, plan)
            errors = validate_production_plan(project)
            self.assertTrue(any("wave" in error and "verified" in error for error in errors))

    def test_reopen_after_verification_invalidates_production(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.state()
            state["production"]["status"] = "verified"
            state["reopen_log"] = [{
                "slide_id": "S01",
                "reason": "Owner requested a visual correction",
                "reopened_by": "Owner",
                "reopened_at": "2026-08-25T11:00:00+08:00",
                "scope": "page",
            }]
            plan = self.valid_plan()
            plan["waves"][0]["status"] = "verified"
            for agent in plan["waves"][0]["agents"]:
                agent["status"] = "verified"
            plan["verification"] = {
                "status": "passed",
                "verified_slide_ids": ["S01", "S02"],
                "last_verified_at": "2026-08-25T10:30:00+08:00",
            }
            self.write_fixture(project, state, plan)
            errors = validate_production_plan(project)
            self.assertTrue(any("reopen_log" in error for error in errors))

    def test_parallel_plan_rejects_case_insensitive_path_collision_and_duplicate_wave_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            plan = self.valid_plan()
            plan["waves"][0]["wave_id"] = "DUPLICATE"
            plan["waves"].append({
                "wave_id": "DUPLICATE",
                "status": "ready",
                "agents": [{
                    "agent_id": "production-03",
                    "slide_ids": ["S02"],
                    "write_paths": ["deck/review/CH01/s01.PNG"],
                    "status": "ready",
                }],
            })
            self.write_fixture(project, self.state(), plan)
            errors = validate_production_plan(project)
            self.assertTrue(any("wave_id" in error and "unique" in error for error in errors))
            self.assertTrue(any("write path" in error and "more than once" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
