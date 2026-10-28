from __future__ import annotations

import os
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
os.environ["QIFEI_MEMORY_HOME"] = tempfile.mkdtemp(prefix="qifei-memory-test-")  # never read or write real memory
os.environ["QIFEI_RUNTIME_FILE"] = str(Path(tempfile.mkdtemp(prefix="qifei-runtime-test-")) / "runtime.json")  # never the real one


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

    def test_missing_feishu_does_not_block_a_full_deck(self) -> None:
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
        # The local draft studio is the content authority, so Feishu is optional.
        self.assertNotIn("manuscript_confirmation", report["stage_blockers"])
        self.assertNotIn("strategy", report["stage_blockers"])
        self.assertEqual(report["adapters"]["content_authority"], "studio")


if __name__ == "__main__":
    unittest.main()


class DeclaredCapabilityTests(unittest.TestCase):
    """doctor cannot see the agent's tools; the agent declares them, and the declaration can be saved."""

    def setUp(self) -> None:
        self.doctor = load_doctor_module()
        self.saved_env = {k: os.environ.pop(k, None) for k in (
            "PROPOSAL_IMAGE_PROVIDER", "PROPOSAL_VISUAL_UNDERSTANDING", "PROPOSAL_CODEX_NATIVE_COMMENTS",
            "PROPOSAL_AGENT_HOST", "CLAUDECODE", "AI_AGENT", "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED",
            "CODEX_THREAD_ID")}
        runtime = Path(os.environ["QIFEI_RUNTIME_FILE"])
        if runtime.is_file():
            runtime.unlink()

    def tearDown(self) -> None:
        for key, value in self.saved_env.items():
            if value is not None:
                os.environ[key] = value
        Path(os.environ["QIFEI_RUNTIME_FILE"]).unlink(missing_ok=True)

    def test_nothing_declared_means_no_image_vision_or_native_comments(self) -> None:
        caps = self.doctor.detect_capabilities()
        self.assertEqual((caps["image_generation"], caps["visual_understanding"], caps["codex_native_comments"]),
                         (False, False, False))
        self.assertEqual(caps["agent_host"], "unknown")

    def test_agent_declaration_unblocks_the_visual_stages(self) -> None:
        caps = self.doctor.detect_capabilities({"image_provider": "magpie-image", "visual_understanding": True})
        self.assertEqual(caps["capability_sources"]["image_generation"], "agent")
        report = self.doctor.build_report({**caps, "node": True, "npm": True, "browser": True}, "full_deck")
        self.assertEqual(report["runtime_profile"], "api_full")
        self.assertNotIn("visual_direction", report["stage_blockers"])
        self.assertNotIn("visual_review", report["stage_blockers"])

    def test_saved_declaration_applies_later_and_declaration_beats_environment(self) -> None:
        self.doctor.save_declared({"image_provider": "codex_builtin", "codex_native_comments": True})
        caps = self.doctor.detect_capabilities()
        self.assertEqual((caps["image_provider"], caps["capability_sources"]["image_generation"]), ("codex_builtin", "saved"))
        self.assertTrue(caps["codex_native_comments"])
        os.environ["PROPOSAL_IMAGE_PROVIDER"] = "openai_api"
        self.assertEqual(self.doctor.detect_capabilities()["image_provider"], "openai_api")
        self.assertEqual(self.doctor.detect_capabilities({"image_provider": "magpie-image"})["image_provider"], "magpie-image")

    def test_host_is_detected_from_the_agent_environment(self) -> None:
        os.environ["CLAUDECODE"] = "1"
        self.assertEqual(self.doctor.detect_agent_host(), "claude_code")
        del os.environ["CLAUDECODE"]
        os.environ["CODEX_SANDBOX"] = "seatbelt"
        self.assertEqual(self.doctor.detect_agent_host(), "codex")
        del os.environ["CODEX_SANDBOX"]

    def test_cli_remember_and_forget(self) -> None:
        run = lambda *a: subprocess.run([sys.executable, str(DOCTOR), *a], capture_output=True, text=True, env=os.environ)
        out = run("--image-provider", "magpie-image", "--visual-understanding", "--remember").stdout
        self.assertIn("Image generation: magpie-image (agent declared)", out)
        self.assertIn("saved on this machine", run().stdout)
        run("--forget")
        self.assertIn("Image generation: none", run().stdout)

