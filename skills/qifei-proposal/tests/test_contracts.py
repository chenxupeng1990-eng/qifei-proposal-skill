from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from freeze_deck_spec import content_hash  # noqa: E402
from validate_deck_spec import png_has_alpha, title_has_terminal_period, valid_local_media, visual_length  # noqa: E402
from validate_design_loop import validate_presentation_route  # noqa: E402
from validate_project import validate_project  # noqa: E402


class ContractTests(unittest.TestCase):
    @staticmethod
    def approved(record_id: str) -> dict:
        return {"approved": True, "by": "Owner", "record_id": record_id}

    def write_redteam_project(self, project: Path, chapters: list[dict], active: str | None) -> dict:
        (project / "content" / "chapters").mkdir(parents=True)
        (project / "content" / "proposal-brief.md").write_text("Confirmed brief.", encoding="utf-8")
        (project / "AGENTS.md").write_text("Confirmed project authority.", encoding="utf-8")
        state = {
            "phase": "chapter_redteam",
            "proposal_owner": "Owner",
            "active_chapter_id": active,
            "approvals": {
                key: self.approved(key)
                for key in (
                    "materials_scope", "brief_grill", "proposal_brief", "requirements",
                    "strategy", "outline", "project_agents",
                )
            },
            "chapters": chapters,
            "reopen_log": [],
        }
        (project / "project-state.json").write_text(
            json.dumps(state, ensure_ascii=False),
            encoding="utf-8",
        )
        return state

    @staticmethod
    def presentation_route(
        *, expression_object: str, anchor_kind: str = "html"
    ) -> dict:
        return {
            "service_object": "现场评审者",
            "use_situation": "提案演讲",
            "presentation_task": "理解经营动作",
            "content_relation": "流程",
            "expression_object": expression_object,
            "best_carrier": "主载体",
            "dominant_type": "information_first",
            "anchor_kind": anchor_kind,
            "visual_argument": {
                "first_glance": "主对象",
                "reading_path": "主路径",
                "end_focus": "结论",
            },
            "visual_hammer": {
                "primary_object": "视觉锤",
                "supporting_elements": "标题和标签服务视觉锤",
                "orphan_element_check": "无孤儿元素",
            },
            "image2_decision": {
                "decision": "not_generate",
                "semantic_role": "none",
                "reason": "本页由HTML图表承担主载体。",
                "html_protected_content": "精确数据与图表标签。",
            },
            "image2_task": "无文字辅助视觉",
            "html_task": "精确标注",
            "visual_balance_plan": "主载体优先",
        }

    def test_process_rejects_none_visual_mode(self) -> None:
        page = {
            "visual_mode": "none",
            "visual_not_required_reason": "HTML 已能表达。",
            "presentation_route": self.presentation_route(
                expression_object="process", anchor_kind="html"
            ),
        }
        errors = validate_presentation_route(page, "S01")
        self.assertTrue(any("process pages require" in error for error in errors))

    def test_data_evidence_allows_html_anchor_without_image2(self) -> None:
        page = {
            "visual_mode": "none",
            "visual_not_required_reason": "HTML 图表是主视觉锚点。",
            "presentation_route": self.presentation_route(expression_object="data_evidence"),
        }
        self.assertEqual(validate_presentation_route(page, "S01"), [])

    def test_semantic_icon_allows_image2_when_it_has_a_real_role(self) -> None:
        route = self.presentation_route(expression_object="system", anchor_kind="hybrid")
        route["image2_decision"] = {
            "decision": "generate",
            "semantic_role": "semantic_icon",
            "reason": "用无文字图标标识经营对象，服务系统的阅读路径。",
            "semantic_nodes": ["内容", "商品", "人群", "增长信号"],
            "text_forbidden": True,
            "html_protected_content": "对象名称、指标与关系标注。",
        }
        page = {"visual_mode": "opaque-module", "presentation_route": route}
        self.assertEqual(validate_presentation_route(page, "S01"), [])

    def test_visual_length_weights_cjk_more_than_ascii(self) -> None:
        self.assertEqual(visual_length("中文AB"), 3.0)

    def test_main_title_rejects_terminal_period(self) -> None:
        self.assertTrue(title_has_terminal_period("让好钙，留下来。"))
        self.assertTrue(title_has_terminal_period("Let good calcium stay."))
        self.assertFalse(title_has_terminal_period("让好钙，留下来"))

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

    def test_transparent_png_requires_real_alpha_channel(self) -> None:
        def png_chunk(name: bytes, data: bytes) -> bytes:
            checksum = zlib.crc32(name + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", checksum)

        def minimal_png(color_type: int) -> bytes:
            ihdr = struct.pack(">IIBBBBB", 1, 1, 8, color_type, 0, 0, 0)
            return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(b"IEND", b"")

        with tempfile.TemporaryDirectory() as temp:
            rgba = Path(temp) / "rgba.png"
            rgb = Path(temp) / "rgb.png"
            rgba.write_bytes(minimal_png(6))
            rgb.write_bytes(minimal_png(2))
            self.assertTrue(png_has_alpha(rgba))
            self.assertFalse(png_has_alpha(rgb))

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

    def test_chapter_redteam_rejects_empty_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.write_redteam_project(project, [], None)
            errors = validate_project(project)
            self.assertTrue(any("At least one chapter" in error for error in errors))
            self.assertTrue(any("active_chapter_id" in error for error in errors))

    def test_chapter_redteam_requires_confirmed_target_with_source_and_slides(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.write_redteam_project(
                project,
                [{
                    "chapter_id": "C1",
                    "slides": [],
                    "manuscript_confirmed": False,
                    "confirmation_record_id": None,
                    "source_path": "content/chapters/missing.md",
                }],
                "C1",
            )
            errors = validate_project(project)
            self.assertTrue(any("slides must be non-empty" in error for error in errors))
            self.assertTrue(any("manuscript is not fully confirmed" in error for error in errors))
            self.assertTrue(any("missing confirmation_record_id" in error for error in errors))
            self.assertTrue(any("registered file does not exist" in error for error in errors))

    def test_chapter_redteam_allows_confirmed_target_without_blocking_other_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.write_redteam_project(
                project,
                [
                    {
                        "chapter_id": "C1",
                        "slides": ["S01"],
                        "manuscript_confirmed": True,
                        "confirmation_record_id": "confirm-C1",
                        "source_path": "content/chapters/C1.md",
                    },
                    {
                        "chapter_id": "C2",
                        "slides": [],
                        "manuscript_confirmed": False,
                        "confirmation_record_id": None,
                        "source_path": "content/chapters/missing.md",
                    },
                ],
                "C1",
            )
            (project / "content" / "chapters" / "C1.md").write_text(
                "# Confirmed C1\n",
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertEqual(errors, [])

    def test_design_loop_is_completed_during_review_and_required_by_qa(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            state = {
                "phase": "review",
                "proposal_owner": "Owner",
                "approvals": {},
                "chapters": [{"chapter_id": "C1", "design_loop_passed": False}],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            review_errors = validate_project(project)
            self.assertFalse(any("design loop" in error.lower() for error in review_errors))
            self.assertFalse(any("approved gate: design_loop" in error for error in review_errors))
            state["phase"] = "qa"
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            qa_errors = validate_project(project)
            self.assertTrue(any("design loop" in error.lower() for error in qa_errors))
            self.assertTrue(any("approved gate: design_loop" in error for error in qa_errors))

    def test_strategy_requires_completed_grill_and_proposal_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            state = {
                "phase": "strategy",
                "proposal_owner": "Owner",
                "approvals": {
                    "materials_scope": {"approved": True, "by": "Owner", "record_id": "materials"},
                    "requirements": {"approved": True, "by": "Owner", "record_id": "requirements"},
                },
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("brief_grill" in error for error in errors))
            self.assertTrue(any("proposal_brief" in error for error in errors))
            self.assertTrue(any("content/proposal-brief.md" in error for error in errors))

    def test_visual_direction_requires_uploaded_official_brand_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            state = {
                "phase": "visual_direction",
                "proposal_owner": "Owner",
                "content_freeze_id": "freeze-v1",
                "approvals": {},
                "brand_visual": {"source_ids": [], "source_files": []},
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("source_ids" in error for error in errors))
            self.assertTrue(any("source_files" in error for error in errors))
            self.assertTrue(any("brand_visual_sources" in error for error in errors))

    def test_design_calibration_requires_full_sample_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            calibration = project / "deck" / "design-calibration.html"
            calibration.parent.mkdir(parents=True)
            calibration.write_text('<section data-design-sample="cover"></section>', encoding="utf-8")
            state = {
                "phase": "design_calibration",
                "proposal_owner": "Owner",
                "approvals": {},
                "design_calibration": {"path": "deck/design-calibration.html"},
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("sample type: toc" in error for error in errors))
            self.assertTrue(any("sample type: chapter-data-led" in error for error in errors))
            self.assertTrue(any("sample type: content-visual-module" in error for error in errors))

    def test_generation_requires_brand_source_ids_in_design(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / "inputs" / "brand-official" / "guide.svg"
            source.parent.mkdir(parents=True)
            source.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
            audit = project / "evidence" / "brand-visual-audit.md"
            audit.parent.mkdir(parents=True)
            audit.write_text("Source BRAND-001 is approved.", encoding="utf-8")
            (project / "content").mkdir()
            (project / "content" / "proposal-brief.md").write_text("Confirmed proposal brief.", encoding="utf-8")
            (project / "AGENTS.md").write_text("Confirmed project authority.", encoding="utf-8")
            (project / "DESIGN.md").write_text("Confirmed design without source citation.", encoding="utf-8")
            state = {
                "phase": "generation",
                "proposal_owner": "Owner",
                "content_freeze_id": "freeze-v1",
                "design_version": "design-v1",
                "approvals": {
                    key: {"approved": True, "by": "Owner", "record_id": key}
                    for key in (
                        "brief_grill", "proposal_brief", "content_freeze", "brand_visual_sources",
                        "brand_visual_audit", "brand_visual_incorporation", "visual_sample", "design",
                        "design_calibration", "generation_ready",
                    )
                },
                "design_calibration": {
                    "path": "deck/design-calibration.html",
                    "approval_record_id": "design_calibration",
                },
                "brand_visual": {
                    "source_ids": ["BRAND-001"],
                    "source_files": ["inputs/brand-official/guide.svg"],
                    "audit_path": "evidence/brand-visual-audit.md",
                    "design_incorporation_record_id": "brand_visual_incorporation",
                },
                "chapters": [{
                    "chapter_id": "C1", "manuscript_confirmed": True, "redteam_passed": True,
                    "confirmation_record_id": "confirmed", "redteam_report": "reviews/redteam/C1.json",
                }],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("DESIGN.md does not cite brand visual source id: BRAND-001" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
