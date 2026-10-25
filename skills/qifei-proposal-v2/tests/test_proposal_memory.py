from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
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
        (self.project / "memory").mkdir(parents=True)
        (self.project / "memory" / "decisions.md").write_text(PROJECT, encoding="utf-8")

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

    def test_phase_maps_to_stage(self) -> None:
        out = self.run_memory("load", "--project", str(self.project), "--phase", "design_calibration").stdout
        self.assertIn("PB-0002", out)
        self.assertNotIn("PB-0001", out)

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
        for path in (fresh / "owner.md", fresh / "playbook" / "playbook.md", project / "memory" / "decisions.md"):
            self.assertTrue(path.is_file(), path)
        (fresh / "owner.md").write_text(OWNER, encoding="utf-8")
        subprocess.run([sys.executable, str(SCRIPT), "init"], env=env, check=True, capture_output=True)
        self.assertEqual((fresh / "owner.md").read_text(encoding="utf-8"), OWNER)

    def test_templates_contain_no_live_entries(self) -> None:
        for path in (
            SKILL_ROOT / "assets" / "memory-templates" / "owner.md",
            SKILL_ROOT / "assets" / "memory-templates" / "playbook.md",
            SKILL_ROOT / "assets" / "project-template" / "memory" / "decisions.md",
        ):
            env = os.environ.copy()
            env["QIFEI_MEMORY_HOME"] = str(Path(self.tmp.name) / "empty")
            sys.path.insert(0, str(SKILL_ROOT / "scripts"))
            import proposal_memory  # noqa: PLC0415

            self.assertEqual(proposal_memory.parse_file(path, "owner"), [], path)

    def test_controller_loads_memory_every_phase(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("scripts/proposal_memory.py load", skill)
        self.assertIn("references/proposal-memory.md", skill)


if __name__ == "__main__":
    unittest.main()
