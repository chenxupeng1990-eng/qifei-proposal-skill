from __future__ import annotations

import json
import os
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
SCRIPT = SKILL_ROOT / "scripts" / "proposal_memory.py"

OWNER = """# Owner 偏好

## O-0001｜数据页用判断型标题
- 阶段：strategy, manuscript
- 状态：active
- 日期：2026-07-17
- 来源：乳品提案 Owner 原话

数据页标题写判断，不写主题。

## O-0002｜旧规则
- 阶段：all
- 状态：superseded:O-0003
- 日期：2026-06-01
- 来源：早期习惯

已经不再适用。

## O-0003｜参考旧模板时清掉旧口径
- 阶段：all
- 状态：active
- 日期：2026-08-01
- 来源：防晒提案复盘

旧结论、旧产品名、旧价盘必须清干净。
"""

PLAYBOOK = """# 方法论

## PB-0001｜美妆比稿第二章先讲消费者问题
- 阶段：strategy
- 状态：active
- 日期：2026-09-01
- 来源：家清、护肤两次比稿
- 适用：美妆

消费者问题 → 产品证据 → 选择理由。

## PB-0002｜视觉方向至少三套真实样张
- 阶段：visual
- 状态：active
- 日期：2026-09-02
- 来源：乳品提案视觉校准

方向说明不能替代样张。
"""

PROJECT = """# 项目记忆

## D-0001｜五年目标写净销售额
- 阶段：all
- 状态：active
- 日期：2026-10-01
- 来源：Owner 确认 rec-12

不得写成已实现业绩。
"""


class ProposalMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        (self.home / "playbook").mkdir(parents=True)
        (self.home / "owner.md").write_text(OWNER, encoding="utf-8")
        (self.home / "playbook" / "pitch.md").write_text(PLAYBOOK, encoding="utf-8")
        self.project = root / "project"
        self.project.mkdir()
        (self.home / "projects" / "project").mkdir(parents=True)
        (self.home / "projects" / "project" / "decisions.md").write_text(PROJECT, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_memory(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["QIFEI_MEMORY_HOME"] = str(self.home)
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False)

    def test_load_filters_by_phase_status_and_orders_layers(self) -> None:
        result = self.run_memory("load", "--project", str(self.project), "--phase", "strategy")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        for expected in ("D-0001", "O-0001", "O-0003", "PB-0001"):
            self.assertIn(expected, out)
        self.assertNotIn("O-0002", out)  # superseded
        self.assertNotIn("PB-0002", out)  # visual stage only
        self.assertLess(out.index("D-0001"), out.index("O-0003"))
        self.assertLess(out.index("O-0003"), out.index("O-0001"))  # newer first within a layer
        self.assertLess(out.index("O-0001"), out.index("PB-0001"))
        self.assertIn("不是事实来源", out)

    def test_phase_maps_to_stage_and_keeps_earlier_stages(self) -> None:
        out = self.run_memory("load", "--project", str(self.project), "--phase", "design_calibration").stdout
        self.assertIn("PB-0002", out)
        # A visual-stage session that reopens strategy content still needs strategy memory, marked as earlier.
        self.assertIn("PB-0001｜美妆比稿第二章先讲消费者问题**（前序阶段 strategy；", out)
        self.assertLess(out.index("PB-0002"), out.index("PB-0001"))
        self.assertNotIn("前序阶段", out.split("O-0003", 1)[1].split("\n", 1)[0])
        later = self.run_memory("load", "--project", str(self.project), "--phase", "strategy").stdout
        self.assertNotIn("PB-0002", later)  # later-stage memory is not pulled forward

    def test_load_writes_a_receipt_that_goes_stale_when_memory_changes(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        import proposal_memory  # noqa: PLC0415

        previous = os.environ.get("QIFEI_MEMORY_HOME")
        os.environ["QIFEI_MEMORY_HOME"] = str(self.home)
        try:
            self.assertIn("还没有读取", proposal_memory.receipt_problem(self.project, "manuscript"))
            self.run_memory("load", "--project", str(self.project), "--phase", "manuscript", "--tags", "美妆")
            self.assertIsNone(proposal_memory.receipt_problem(self.project, "manuscript"))
            self.assertIn("还没有读取", proposal_memory.receipt_problem(self.project, "design_calibration"))
            owner = self.home / "owner.md"
            owner.write_text(owner.read_text(encoding="utf-8").replace("数据页标题写判断", "数据页标题必须写判断"),
                             encoding="utf-8")
            self.assertIn("有更新", proposal_memory.receipt_problem(self.project, "manuscript"))
        finally:
            os.environ["QIFEI_MEMORY_HOME"] = previous or ""
            if previous is None:
                del os.environ["QIFEI_MEMORY_HOME"]

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["QIFEI_MEMORY_HOME"] = str(self.home)
        return subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env, check=False)

    def test_validate_hands_over_memory_and_blocks_until_it_is_read(self) -> None:
        (self.project / "project-state.json").write_text(json.dumps({"phase": "intake", "proposal_owner": "Owner"}),
                                                       encoding="utf-8")
        validate = str(SKILL_ROOT / "scripts" / "validate_project.py")
        first = self.run_script(validate, str(self.project))
        self.assertEqual(first.returncode, 1)
        self.assertIn("proposal memory: 本阶段（intake）的", first.stdout)
        self.assertIn("D-0001｜五年目标写净销售额", first.stdout)  # the memory itself is in the output
        second = self.run_script(validate, str(self.project))
        self.assertNotIn("proposal memory:", second.stdout)
        owner = self.home / "owner.md"
        owner.write_text(owner.read_text(encoding="utf-8").replace("旧价盘必须清干净", "旧价盘和旧数据必须清干净"),
                         encoding="utf-8")
        third = self.run_script(validate, str(self.project))
        self.assertIn("proposal memory: 提案记忆在上次读取后有更新", third.stdout)
        self.assertIn("旧价盘和旧数据必须清干净", third.stdout)

    def test_doctor_with_project_carries_the_memory(self) -> None:
        (self.project / "project-state.json").write_text(json.dumps({"phase": "manuscript", "proposal_owner": "Owner"}),
                                                       encoding="utf-8")
        doctor = str(SKILL_ROOT / "scripts" / "doctor.py")
        result = self.run_script(doctor, "--project", str(self.project), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        memory = json.loads(result.stdout)["proposal_memory"]
        self.assertEqual(memory["phase"], "manuscript")
        self.assertIn("O-0001｜数据页用判断型标题", memory["text"])
        self.assertIn("O-0001", self.run_script(doctor, "--project", str(self.project)).stdout)
        validate = self.run_script(str(SKILL_ROOT / "scripts" / "validate_project.py"), str(self.project))
        self.assertNotIn("proposal memory:", validate.stdout)

    def test_scope_tags_narrow_playbook(self) -> None:
        out = self.run_memory("load", "--project", str(self.project), "--phase", "strategy", "--tags", "快消").stdout
        self.assertNotIn("PB-0001", out)
        self.assertIn("O-0001", out)  # entries without scope always apply

    def test_budget_caps_output_and_reports_omissions(self) -> None:
        out = self.run_memory("load", "--project", str(self.project), "--phase", "strategy", "--max-entries", "2").stdout
        self.assertIn("另有 2 条相关记忆", out)

    def test_unknown_phase_is_rejected(self) -> None:
        self.assertEqual(self.run_memory("load", "--phase", "drafting").returncode, 2)

    def test_check_passes_for_valid_memory(self) -> None:
        result = self.run_memory("check", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("PASS: 6 entries", result.stdout)

    def test_check_reports_format_errors(self) -> None:
        (self.home / "owner.md").write_text(
            "## O-0001｜缺字段\n- 阶段：someday\n- 状态：superseded:O-0099\n- 日期：昨天\n\n"
            "## D-0005｜放错层\n- 阶段：all\n- 状态：active\n- 日期：2026-01-01\n- 来源：x\n\n正文\n",
            encoding="utf-8",
        )
        result = self.run_memory("check", "--project", str(self.project))
        self.assertEqual(result.returncode, 1)
        for message in ("unknown 阶段", "unknown id O-0099", "YYYY-MM-DD", "来源 is required", "body is empty", "ids start with O-"):
            self.assertIn(message, result.stdout)

    def test_init_creates_missing_files_without_overwriting(self) -> None:
        fresh = Path(self.tmp.name) / "fresh-home"
        env = os.environ.copy()
        env["QIFEI_MEMORY_HOME"] = str(fresh)
        project = Path(self.tmp.name) / "new-project"
        project.mkdir()
        result = subprocess.run([sys.executable, str(SCRIPT), "init", "--project", str(project)],
                                capture_output=True, text=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        pdir = fresh / "projects" / "new-project"
        for path in (fresh / "owner.md", fresh / "playbook" / "playbook.md", pdir / "decisions.md",
                     pdir / "candidates.md", pdir / "project.json"):
            self.assertTrue(path.is_file(), path)
        (fresh / "owner.md").write_text(OWNER, encoding="utf-8")
        subprocess.run([sys.executable, str(SCRIPT), "init"], env=env, check=True, capture_output=True)
        self.assertEqual((fresh / "owner.md").read_text(encoding="utf-8"), OWNER)

    def test_templates_contain_no_live_entries(self) -> None:
        for path in (
            SKILL_ROOT / "assets" / "memory-templates" / "owner.md",
            SKILL_ROOT / "assets" / "memory-templates" / "playbook.md",
            SKILL_ROOT / "assets" / "memory-templates" / "project.md",
            SKILL_ROOT / "assets" / "memory-templates" / "candidates.md",
        ):
            env = os.environ.copy()
            env["QIFEI_MEMORY_HOME"] = str(Path(self.tmp.name) / "empty")
            sys.path.insert(0, str(SKILL_ROOT / "scripts"))
            import proposal_memory  # noqa: PLC0415

            self.assertEqual(proposal_memory.parse_file(path, "owner"), [], path)

    def test_controller_loads_memory_every_phase(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        # Start of work: doctor --project prints this phase's memory; phase change: advance loads the next one.
        self.assertIn("doctor.py --project", skill)
        self.assertIn("proposal_memory.py advance", skill)
        self.assertIn("references/proposal-memory.md", skill)


CANDIDATES = """# 记忆候选

## MC-0001｜可见证明写证据，不写设计方向
- 建议层级：owner
- 阶段：manuscript
- 状态：candidate
- 日期：2026-10-25
- 来源：C-0001
- 适用：all

核心内容里的可见证明必须回答“凭什么”，引用证据编号；版式和载体写进视觉生成建议。

## MC-0002｜本项目不做品牌架构图
- 建议层级：project
- 阶段：visual
- 状态：candidate
- 日期：2026-10-25
- 来源：R2

只保留生活方式场景带。
"""


class MemoryCandidateTests(unittest.TestCase):
    """R2: studio decisions become candidates; only the Owner turns them into memory."""

    def setUp(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import draft_studio  # noqa: PLC0415
        from test_draft_format import page  # noqa: PLC0415

        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.home.mkdir()
        (self.home / "owner.md").write_text(OWNER, encoding="utf-8")
        self.project = root / "project"
        draft = self.project / "content" / "draft" / "proposal-draft.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# 开场｜示例\n\n" + page("P01", "长期经营") + page("P02", "渠道变化"), encoding="utf-8")
        store = draft_studio.DraftStore(self.project, draft, None)
        store.ensure_baseline()
        store.save({"kind": "field", "slide": "P02", "key": "talk", "md": "先讲渠道失效，再讲机会。"},
                   draft_studio.sha256_text(store.read()))
        comments = draft_studio.CommentStore(draft)
        decided = comments.create({"slide": "P01", "field": "P01:core", "quote": "核心内容的内容", "text": "这是证明还是方向？"}, 2)
        comments.reply(decided["id"], "改成证据台账的核准表述。", "Agent")
        comments.reply(decided["id"], "同意。", "Owner", resolve=True)
        comments.create({"slide": "P02", "field": "P02:screen", "quote": "PPT上屏内容的内容", "text": "还没定"}, 2)
        draft_studio.ConfirmationStore(draft).add({"record_id": "confirm-C1-r2-abc123", "chapter_id": "C1",
                                                   "slides": {"P01": "x"}, "by": "Owner", "revision": 2})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_memory(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["QIFEI_MEMORY_HOME"] = str(self.home)
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False)

    def write_candidates(self) -> Path:
        path = self.home / "projects" / "project" / "candidates.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CANDIDATES, encoding="utf-8")
        return path

    def test_signals_digest_decided_comments_owner_edits_and_confirmations(self) -> None:
        result = self.run_memory("signals", "--project", str(self.project))
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("### C-0001｜P01 · 核心内容（Owner 决定）", out)
        self.assertIn("- Agent：改成证据台账的核准表述。", out)
        self.assertNotIn("C-0002", out)  # still open: not a decision yet
        self.assertIn("### R2｜P02 · 讲解方向", out)
        self.assertIn("- 改前：讲解方向的内容。", out)
        self.assertIn("- 改后：先讲渠道失效，再讲机会。", out)
        self.assertIn("confirm-C1-r2-abc123", out)
        self.assertNotIn("R1", out)  # the baseline is not a decision

    def test_signals_already_cited_are_hidden_unless_all(self) -> None:
        self.write_candidates()
        out = self.run_memory("signals", "--project", str(self.project)).stdout
        self.assertNotIn("### C-0001", out)
        self.assertNotIn("### R2", out)
        self.assertIn("2 条信号已被候选或记忆引用", out)
        self.assertIn("### C-0001", self.run_memory("signals", "--project", str(self.project), "--all").stdout)

    def test_owner_accepts_an_edited_candidate_into_its_layer(self) -> None:
        candidates = self.write_candidates()
        result = self.run_memory("accept", "MC-0001", "--project", str(self.project), "--title", "可见证明只写证据")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("accepted as O-0004", result.stdout)
        owner = (self.home / "owner.md").read_text(encoding="utf-8")
        self.assertIn("## O-0004｜可见证明只写证据\n- 阶段：manuscript\n- 状态：active", owner)
        self.assertRegex(owner, r"- 来源：C-0001；Owner 采纳 \d{4}-\d{2}-\d{2}（MC-0001）")
        self.assertIn("- 状态：accepted:O-0004", candidates.read_text(encoding="utf-8"))
        self.assertIn("O-0004", self.run_memory("load", "--project", str(self.project), "--phase", "manuscript").stdout)

        self.assertEqual(self.run_memory("accept", "MC-0002", "--project", str(self.project)).returncode, 0)
        self.assertIn("## D-0001｜本项目不做品牌架构图", (self.home / "projects" / "project" / "decisions.md").read_text(encoding="utf-8"))
        check = self.run_memory("check", "--project", str(self.project))
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_reject_and_decisions_are_final(self) -> None:
        candidates = self.write_candidates()
        self.assertEqual(self.run_memory("reject", "MC-0002", "--project", str(self.project)).returncode, 0)
        self.assertIn("- 状态：rejected", candidates.read_text(encoding="utf-8"))
        again = self.run_memory("accept", "MC-0002", "--project", str(self.project))
        self.assertEqual(again.returncode, 1)
        self.assertIn("already rejected", again.stderr)
        self.assertFalse((self.home / "projects" / "project" / "decisions.md").exists())

    def test_check_reports_candidate_errors(self) -> None:
        path = self.write_candidates()
        path.write_text(CANDIDATES.replace("- 来源：R2", "- 来源：感觉").replace("建议层级：owner", "建议层级：team"),
                        encoding="utf-8")
        result = self.run_memory("check", "--project", str(self.project))
        self.assertEqual(result.returncode, 1)
        self.assertIn("MC-0002: 来源 must cite a signal id", result.stdout)
        self.assertIn("MC-0001: 建议层级 must be one of", result.stdout)

    def test_memory_box_shows_every_layer_and_takes_owner_decisions(self) -> None:
        self.write_candidates()
        self.run_memory("signals", "--project", str(self.project))  # any project command registers the project
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env["QIFEI_MEMORY_HOME"] = str(self.home)
        server = subprocess.Popen([sys.executable, str(SKILL_ROOT / "scripts" / "memory_box.py"), "--port", str(port)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(50):
                try:
                    html = urllib.request.urlopen(base + "/", timeout=1).read().decode("utf-8")
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("memory box did not start")
            token = json.loads(re.search(r"const TOKEN = (.*?);", html).group(1))

            def call(path: str, body: dict | None = None) -> tuple[int, dict]:
                req = urllib.request.Request(base + path, data=json.dumps(body).encode("utf-8") if body else None,
                                             headers={"Content-Type": "application/json", "X-Box-Token": token})
                try:
                    with urllib.request.urlopen(req, timeout=5) as res:
                        return res.status, json.loads(res.read().decode("utf-8"))
                except urllib.error.HTTPError as error:
                    with error:
                        return error.code, json.loads(error.read().decode("utf-8"))

            req = urllib.request.Request(base + "/api/memory")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(req, timeout=5)  # no token
            status, data = call("/api/memory")
            self.assertEqual([e["id"] for e in data["owner"]], ["O-0001", "O-0002", "O-0003"])
            (project,) = data["projects"]
            self.assertEqual(project["path"], str(self.project.resolve()))
            self.assertEqual([c["id"] for c in project["candidates"]], ["MC-0001", "MC-0002"])

            status, data = call("/api/candidate/accept", {"project": "project", "id": "MC-0001", "layer": "playbook",
                                                          "stages": ["manuscript", "review"], "body": "可见证明引用证据编号。"})
            self.assertEqual(status, 200, data)
            self.assertEqual(data["accepted"], "PB-0001")
            self.assertEqual(data["memory"]["playbook"][0]["stages"], ["manuscript", "review"])
            self.assertEqual(call("/api/candidate/accept", {"project": "project", "id": "MC-0002", "stages": ["someday"]})[0], 400)
            status, data = call("/api/candidate/reject", {"project": "project", "id": "MC-0002"})
            self.assertEqual([c["status"] for c in data["memory"]["projects"][0]["candidates"]], ["accepted:PB-0001", "rejected"])

            status, data = call("/api/entry/update", {"file": "owner.md", "id": "O-0001", "title": "数据页标题写判断",
                                                      "body": "新的正文。", "stages": ["manuscript"], "scope": [], "status": "retired"})
            self.assertEqual(status, 200, data)
            owner = (self.home / "owner.md").read_text(encoding="utf-8")
            self.assertIn("## O-0001｜数据页标题写判断\n- 阶段：manuscript\n- 状态：retired\n- 日期：2026-07-17", owner)
            self.assertIn("新的正文。\n\n## O-0002", owner)
            self.assertNotIn("O-0001", self.run_memory("load", "--project", str(self.project), "--phase", "manuscript").stdout)
            self.assertEqual(self.run_memory("check", "--project", str(self.project)).returncode, 0)
            self.assertEqual(call("/api/entry/update", {"file": "../outside.md", "id": "O-0001", "title": "x", "body": "x",
                                                        "stages": ["all"], "status": "active"})[0], 400)
        finally:
            server.terminate()
            server.wait(timeout=5)

if __name__ == "__main__":
    unittest.main()
