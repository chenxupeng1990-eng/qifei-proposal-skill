from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class ProgressiveDisclosureTests(unittest.TestCase):
    def test_thin_controller_routes_every_project_phase_to_one_pack(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        packs = re.findall(r"\(phase-packs/([^)]+\.md)\)", skill_text)
        self.assertEqual(len(packs), 8)
        self.assertEqual(len(set(packs)), 8)
        for pack in packs:
            self.assertTrue((SKILL_ROOT / "phase-packs" / pack).is_file(), pack)
        for phase in (
            "intake",
            "requirements",
            "strategy",
            "project_agents",
            "manuscript",
            "full_redteam",
            "content_frozen",
            "visual_direction",
            "design_calibration",
            "design_system",
            "generation",
            "review",
            "qa",
            "export",
        ):
            self.assertEqual(skill_text.count(f"`{phase}`"), 1, phase)

    def test_phase_packs_do_not_chain_into_future_phase_packs(self) -> None:
        for pack in (SKILL_ROOT / "phase-packs").glob("*.md"):
            text = pack.read_text(encoding="utf-8")
            self.assertNotIn("../phase-packs/", text, pack.name)

    def test_controller_is_materially_smaller_than_v1(self) -> None:
        controller_size = (SKILL_ROOT / "SKILL.md").stat().st_size
        permanent_size = (SKILL_ROOT / "agent.md").stat().st_size
        self.assertLess(controller_size + permanent_size, 8_000)

    def test_critical_v1_capabilities_remain_routed_in_v2(self) -> None:
        all_runtime_rules = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                SKILL_ROOT / "SKILL.md",
                SKILL_ROOT / "agent.md",
                *(sorted((SKILL_ROOT / "phase-packs").glob("*.md"))),
            )
        )
        for capability in (
            "Visualize:visualize",
            "公司介绍与选定案例放在提案前部",
            "$proposal-ppt-production",
            "$ppt-html-calibration-editor",
            "提示词必须去标识化",
            "基础交付",
            "增强交付",
            "不承诺",
            "data-to-strategy-evidence-engine.md",
            "数据事实 → 关系判断 → 品牌含义 → 策略选择 → 执行接口",
        ):
            self.assertIn(capability, all_runtime_rules, capability)

    def test_environment_degradation_is_centralized(self) -> None:
        text = (SKILL_ROOT / "references" / "environment-degradation.md").read_text(encoding="utf-8")
        self.assertIn("飞书不可用", text)
        self.assertIn("Image2 不可用", text)
        self.assertIn("Codex 浏览器评论不可用", text)

    def test_calibration_numbers_have_one_document_authority(self) -> None:
        calibration = (SKILL_ROOT / "phase-packs" / "06-design-calibration.md").read_text(encoding="utf-8")
        workflow = (SKILL_ROOT / "references" / "workflow.md").read_text(encoding="utf-8")
        design = (SKILL_ROOT / "references" / "design-calibration-contract.md").read_text(encoding="utf-8")
        marker = "24页及以下"
        self.assertNotIn(marker, calibration)
        self.assertNotIn(marker, workflow)
        self.assertIn(marker, design)

    def test_visual_reference_is_split_by_phase_responsibility(self) -> None:
        navigation = (SKILL_ROOT / "references" / "design-and-generation.md").read_text(encoding="utf-8")
        self.assertLess(len(navigation.splitlines()), 40)
        for reference in (
            "visual-direction.md",
            "design-calibration-contract.md",
            "design-system-contract.md",
            "page-production-loop.md",
        ):
            self.assertIn(reference, navigation)
            self.assertTrue((SKILL_ROOT / "references" / reference).is_file())

    def test_agents_template_uses_typed_placeholders(self) -> None:
        agents = (SKILL_ROOT / "assets" / "project-template" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("待填写", agents)
        self.assertNotIn("待确认", agents)
        self.assertNotRegex(agents, r"\{\{(?!INIT:|REQUIRED_AT_[A-Z_]+:|OPTIONAL:)")

    def test_cowart_is_not_a_workflow_dependency(self) -> None:
        for folder in ("phase-packs", "references"):
            for path in (SKILL_ROOT / folder).glob("*.md"):
                self.assertNotIn("Cowart", path.read_text(encoding="utf-8"), path.name)

    def test_temporary_pages_cannot_bypass_feishu_authority(self) -> None:
        text = (SKILL_ROOT / "references" / "feishu-proposal-draft-format.md").read_text(encoding="utf-8")
        self.assertIn("content/feishu/page-change-proposals.md", text)
        self.assertIn("不得进入 `chapters[].slides`", text)
        self.assertIn("回写飞书并完成整份回读", text)


if __name__ == "__main__":
    unittest.main()
