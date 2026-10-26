"""M4 acceptance: a full deck goes from manuscript to content freeze with the studio as authority, no Feishu."""
from __future__ import annotations

import os
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import draft_studio  # noqa: E402
from test_draft_format import page  # noqa: E402
from validate_feishu_draft import validate_feishu_draft_evidence  # noqa: E402
from validate_project import validate_project as _validate_project  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_fixtures import mark_signals_run  # noqa: E402


def validate_project(project):
    """Gate checks in these tests assume memory signals were distilled for the current phase."""
    mark_signals_run(project)
    return _validate_project(project)


DRAFT = "\n".join([
    "<title>示例长期合作提案</title>",
    "",
    "# 开场｜重新选择增长伙伴",
    "",
    "**本章回答：** 为什么需要长期伙伴。",
    "",
    "**逻辑路径：** 合作意图 → 单渠道失效 → 需要增长出口。",
    "",
    "**情绪方向：** 从郑重开始，制造选择压力。",
    "",
    page("P01", "长期经营而不是一次传播"),
    page("P02", "单一渠道能力不再构成竞争优势"),
    "# 打法｜把品牌经营成生活方式",
    "",
    page("P03", "内容就是货架"),
])

APPROVED = {"approved": True, "by": "Owner", "at": "2026-10-25T10:00:00+08:00"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
os.environ["QIFEI_MEMORY_HOME"] = tempfile.mkdtemp(prefix="qifei-memory-test-")  # never read or write real memory


class StudioAuthorityAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        p = self.project
        (p / "content" / "draft").mkdir(parents=True)
        (p / "content" / "chapters").mkdir(parents=True)
        (p / "content" / "draft" / "proposal-draft.md").write_text(DRAFT, encoding="utf-8")
        (p / "content" / "proposal-brief.md").write_text("Confirmed brief.", encoding="utf-8")
        (p / "AGENTS.md").write_text("Confirmed project authority.", encoding="utf-8")
        for chapter in ("C1", "C2"):
            (p / "content" / "chapters" / f"{chapter}.md").write_text(f"# {chapter}\n", encoding="utf-8")
        state = {
            "phase": "full_redteam",
            "proposal_owner": "Owner",
            "task_mode": "full_deck",
            "content_authority": "studio",
            "approvals": {
                key: {**APPROVED, "record_id": key}
                for key in ("materials_scope", "brief_grill", "proposal_brief", "requirements", "strategy", "outline", "project_agents")
            },
            "proposal_draft": {
                "authority": "studio", "status": "not_started", "format_version": "proposal-draft-v2",
                "verified_snapshot_path": "content/draft/proposal-draft.md", "verified_slide_ids": [],
            },
            "chapters": [
                {"chapter_id": "C1", "slides": ["P01", "P02"], "manuscript_confirmed": False,
                 "confirmation_record_id": None, "source_path": "content/chapters/C1.md"},
                {"chapter_id": "C2", "slides": ["P03"], "manuscript_confirmed": False,
                 "confirmation_record_id": None, "source_path": "content/chapters/C2.md"},
            ],
            "reopen_log": [],
        }
        (p / "project-state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        self.port = free_port()
        self.server = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "draft_studio.py"), "serve", str(p), "--port", str(self.port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.base = f"http://127.0.0.1:{self.port}"
        for _ in range(50):
            try:
                html = urllib.request.urlopen(self.base + "/", timeout=1).read().decode("utf-8")
                break
            except OSError:
                time.sleep(0.1)
        else:
            self.fail("studio did not start")
        self.token = json.loads(re.search(r'id="live">(.*?)</script>', html).group(1))["token"]

    def tearDown(self) -> None:
        self.server.terminate()
        self.server.wait(timeout=5)
        self.server.stdout.close()
        self.server.stderr.close()
        self.tmp.cleanup()

    def post(self, path: str, body: dict) -> tuple[int, dict]:
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-Studio-Token": self.token})
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read().decode("utf-8"))

    def state(self) -> dict:
        return json.loads((self.project / "project-state.json").read_text(encoding="utf-8"))

    def test_manuscript_to_content_freeze_without_feishu(self) -> None:
        # 1. Nothing confirmed or registered yet: the gate refuses.
        errors = validate_project(self.project)
        self.assertTrue(any("C1: manuscript is not fully confirmed" in e for e in errors))
        self.assertTrue(any("authority feishu or studio with status verified" in e for e in errors))

        # 2. Owner confirms C1; the draft is registered automatically.
        status, data = self.post("/api/confirm", {"chapter_id": "C1", "author": "Owner"})
        self.assertEqual(status, 200, data)
        self.assertEqual(self.state()["proposal_draft"]["status"], "verified")
        errors = validate_project(self.project)
        self.assertEqual([e for e in errors if "C2" not in e], [], errors)
        self.assertTrue(any("C2: manuscript is not fully confirmed" in e for e in errors))

        # 3. Owner confirms C2: the full-draft review gate opens with no Feishu at all.
        status, data = self.post("/api/confirm", {"chapter_id": "C2", "author": "Owner"})
        self.assertEqual(status, 200, data)
        self.assertEqual(validate_project(self.project), [])
        self.assertEqual(validate_feishu_draft_evidence(self.project, self.state()), [])
        self.assertTrue(data["model"]["registration"]["all_confirmed"])

        # 4. Editing a confirmed page reopens its chapter and invalidates the registration.
        model = json.loads(urllib.request.urlopen(urllib.request.Request(
            self.base + "/api/model", headers={"X-Studio-Token": self.token})).read())
        status, saved = self.post("/api/save", {
            "target": {"kind": "field", "slide": "P02", "key": "talk", "md": "换一种讲法。"},
            "base_sha": model["meta"]["sha256"],
        })
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["entry"]["reopened"], ["C1"])
        state = self.state()
        self.assertFalse(state["chapters"][0]["manuscript_confirmed"])
        self.assertTrue(state["chapters"][1]["manuscript_confirmed"])
        self.assertEqual(state["proposal_draft"]["status"], "editing")
        errors = validate_project(self.project)
        self.assertTrue(any("C1: manuscript is not fully confirmed" in e for e in errors))
        p02 = next(s for c in saved["model"]["chapters"] for s in c["slides"] if s["id"] == "P02")
        self.assertEqual(p02["status"], "modified")

        # 5. Owner re-confirms C1 and the gate opens again.
        status, data = self.post("/api/confirm", {"chapter_id": "C1", "author": "Owner"})
        self.assertEqual(status, 200, data)
        self.assertEqual(validate_project(self.project), [])

        # 6. Content freeze after an independent full-draft review.
        report = self.project / "reviews" / "redteam" / "FULL.json"
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({"status": "passed", "independent_agent": True, "review_agent_id": "independent-rt-1"}), encoding="utf-8")
        state = self.state()
        state.update({
            "phase": "content_frozen",
            "content_freeze_id": "freeze-v1",
            "full_redteam": {"report_path": "reviews/redteam/FULL.json", "review_agent_id": "independent-rt-1", "independent_agent": True},
        })
        state["approvals"].update({k: {**APPROVED, "record_id": k} for k in ("full_redteam", "content_freeze")})
        draft_studio.write_state(self.project, state)
        self.assertEqual(validate_project(self.project), [])

    def test_gate_catches_a_chapter_marked_confirmed_after_a_silent_edit(self) -> None:
        for chapter in ("C1", "C2"):
            self.assertEqual(self.post("/api/confirm", {"chapter_id": chapter, "author": "Owner"})[0], 200)
        self.server.terminate()
        self.server.wait(timeout=5)
        draft = self.project / "content" / "draft" / "proposal-draft.md"
        draft.write_text(draft.read_text(encoding="utf-8").replace("内容就是货架的", "内容就是货架！的", 1)
                         .replace("核心内容的内容。", "核心内容被悄悄改了。", 1), encoding="utf-8")
        # Re-registering is allowed for anyone, but the edit reopens C1 and fingerprints still disagree
        # if someone flips the flag back by hand instead of having the Owner confirm.
        result = subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "register", str(self.project)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = self.state()
        self.assertFalse(state["chapters"][0]["manuscript_confirmed"])
        state["chapters"][0]["manuscript_confirmed"] = True
        draft_studio.write_state(self.project, state)
        errors = validate_project(self.project)
        self.assertTrue(any("C1: changed after confirmation (P01)" in e for e in errors), errors)

    def test_confirm_refuses_pages_that_fail_the_format_check(self) -> None:
        draft = self.project / "content" / "draft" / "proposal-draft.md"
        draft.write_text(DRAFT.replace("### 讲解方向", "### 演讲任务", 1), encoding="utf-8")
        time.sleep(0.8)
        status, data = self.post("/api/confirm", {"chapter_id": "C1", "author": "Owner"})
        self.assertEqual(status, 400)
        self.assertIn("格式问题", data["error"])
        status, data = self.post("/api/confirm", {"chapter_id": "C2", "author": "Owner"})
        self.assertEqual(status, 200)
        self.assertIn("registration_pending", data)


class InitDefaultsTests(unittest.TestCase):
    def test_full_deck_defaults_to_the_studio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            result = subprocess.run([sys.executable, str(SCRIPTS / "init_project.py"), "--project", str(project),
                                     "--name", "示例项目", "--owner", "Owner", "--task-mode", "full_deck"],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project / "project-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["content_authority"], "studio")
            self.assertEqual(state["proposal_draft"]["authority"], "studio")
            self.assertEqual(state["proposal_draft"]["format_version"], "proposal-draft-v2")
            self.assertEqual(state["proposal_draft"]["verified_snapshot_path"], "content/draft/proposal-draft.md")
            self.assertTrue((project / "content" / "draft" / "proposal-draft.md").is_file())
            self.assertEqual(validate_project(project), [])

    def test_feishu_stays_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            subprocess.run([sys.executable, str(SCRIPTS / "init_project.py"), "--project", str(project), "--name", "x",
                            "--owner", "Owner", "--task-mode", "full_deck", "--content-authority", "feishu"],
                           capture_output=True, text=True, check=True)
            state = json.loads((project / "project-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["proposal_draft"]["authority"], "feishu")
            self.assertEqual(state["proposal_draft"]["verified_snapshot_path"], "content/feishu/proposal-draft.md")


if __name__ == "__main__":
    unittest.main()
