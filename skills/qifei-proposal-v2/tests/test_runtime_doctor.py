from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DOCTOR = SKILL_ROOT / "scripts" / "doctor.py"


def load_doctor_module():
    spec = importlib.util.spec_from_file_location("qifei_runtime_doctor", DOCTOR)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RuntimeDoctorTests(unittest.TestCase):
    def test_lark_auth_status_accepts_ready_or_refreshable_user_identity(self) -> None:
        doctor = load_doctor_module()
        self.assertTrue(
            doctor.lark_auth_is_ready(
                {
                    "identity": "user",
                    "identities": {
                        "user": {"available": True, "status": "needs_refresh"},
                        "bot": {"available": True, "status": "ready"},
                    },
                }
            )
        )

    def run_doctor(self, capabilities: dict, task_mode: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "capabilities.json"
            source.write_text(json.dumps(capabilities), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(DOCTOR),
                    "--json",
                    "--task-mode",
                    task_mode,
                    "--capabilities",
                    str(source),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_api_agent_with_image_and_local_runtime_gets_full_module_production(self) -> None:
        result = self.run_doctor(
            {
                "agent_host": "generic_api_agent",
                "filesystem": True,
                "shell": True,
                "python": True,
                "node": True,
                "npm": True,
                "browser": True,
                "image_generation": True,
                "visual_understanding": True,
                "feishu_cli": False,
                "feishu_authorized": False,
            },
            "standalone_module",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["runtime_profile"], "api_full")
        self.assertEqual(report["adapters"]["review"], "local_review_bundle")
        self.assertEqual(report["adapters"]["content_authority"], "local")
        self.assertTrue(report["deliverables"]["formal_visuals"])
        self.assertTrue(report["deliverables"]["pptx_export"])
        self.assertFalse(report["blockers"])

    def test_text_only_agent_declares_visual_and_export_boundaries(self) -> None:
        result = self.run_doctor(
            {
                "agent_host": "generic_agent",
                "filesystem": True,
                "shell": False,
                "python": False,
                "node": False,
                "npm": False,
                "browser": False,
                "image_generation": False,
                "visual_understanding": False,
                "feishu_cli": False,
                "feishu_authorized": False,
            },
            "standalone_module",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["runtime_profile"], "content_only")
        self.assertTrue(report["deliverables"]["strategy_and_manuscript"])
        self.assertFalse(report["deliverables"]["formal_visuals"])
        self.assertFalse(report["deliverables"]["pptx_export"])
        self.assertIn(
            "formal visual direction and formal page generation cannot be approved",
            report["boundaries"],
        )

    def test_missing_feishu_blocks_manuscript_confirmation_not_early_strategy(self) -> None:
        result = self.run_doctor(
            {
                "agent_host": "generic_api_agent",
                "filesystem": True,
                "shell": True,
                "python": True,
                "node": True,
                "npm": True,
                "browser": True,
                "image_generation": True,
                "visual_understanding": True,
                "feishu_cli": False,
                "feishu_authorized": False,
            },
            "full_deck",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["blockers"])
        self.assertIn("manuscript_confirmation", report["stage_blockers"])
        self.assertNotIn("strategy", report["stage_blockers"])


if __name__ == "__main__":
    unittest.main()
