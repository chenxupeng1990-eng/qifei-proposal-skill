from __future__ import annotations

import json
import hashlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from freeze_deck_spec import content_hash  # noqa: E402
from validate_deck_spec import png_has_alpha, title_has_terminal_period, valid_local_media, validate_deck, visual_length  # noqa: E402
from validate_design_loop import validate_presentation_route  # noqa: E402
from validate_project import validate_project  # noqa: E402


class ContractTests(unittest.TestCase):
    @staticmethod
    def approved(record_id: str) -> dict:
        return {
            "approved": True,
            "by": "Owner",
            "at": "2026-08-05T10:00:00+08:00",
            "record_id": record_id,
        }

    def write_full_redteam_project(self, project: Path, chapters: list[dict]) -> dict:
        (project / "content" / "chapters").mkdir(parents=True, exist_ok=True)
        (project / "content" / "proposal-brief.md").write_text("Confirmed brief.", encoding="utf-8")
        (project / "AGENTS.md").write_text("Confirmed project authority.", encoding="utf-8")
        state = {
            "phase": "full_redteam",
            "proposal_owner": "Owner",
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

    def attach_verified_feishu_draft(self, project: Path, state: dict, slide_ids: list[str]) -> None:
        snapshot = project / "content" / "feishu" / "proposal-draft.md"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        pages = []
        for slide_id in slide_ids:
            pages.append(
                f"""## {slide_id}｜结论式标题

### 核心内容
核心判断。

### 逻辑展开
事实 → 判断 → 动作。

### PPT上屏内容
精确上屏内容。

### 讲解方向
本页讲解方向。

### 策略与过桥
承接前页并进入下一页。

### 视觉生成建议
视觉锤与主载体。

### 证据与来源
证据编号。
"""
            )
        text = (
            "# 第一章｜推进策略\n\n"
            "**本章回答：** 本章必须解决的问题。\n\n"
            "**逻辑路径：** 上一章输出 → 本章结论 → 下一章输入。\n\n"
            "**情绪方向：** 建立共识并释放期待。\n\n"
            + "\n".join(pages)
        )
        snapshot.write_text(text, encoding="utf-8")
        state["proposal_draft"] = {
            "authority": "feishu",
            "status": "verified",
            "format_version": "feishu-proposal-draft-v1",
            "feishu_doc_url": "https://example.feishu.cn/docx/doc-token",
            "document_id": "doc-token",
            "revision_id": 12,
            "last_verified_at": "2026-07-27T12:00:00+08:00",
            "verified_snapshot_path": "content/feishu/proposal-draft.md",
            "verified_snapshot_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "verified_slide_ids": slide_ids,
        }
        (project / "project-state.json").write_text(
            json.dumps(state, ensure_ascii=False),
            encoding="utf-8",
        )

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
        self.assertTrue(any("visual_mode none is not allowed" in error for error in errors))

    def test_data_evidence_rejects_html_only_page_without_image2(self) -> None:
        page = {
            "visual_mode": "none",
            "visual_not_required_reason": "HTML 图表是主视觉锚点。",
            "presentation_route": self.presentation_route(expression_object="data_evidence"),
        }
        errors = validate_presentation_route(page, "S01")
        self.assertTrue(any("every formal page requires an Image2 asset" in error for error in errors))

    def test_semantic_icon_allows_image2_when_it_has_a_real_role(self) -> None:
        route = self.presentation_route(expression_object="system", anchor_kind="hybrid")
        route["image2_decision"] = {
            "decision": "generate",
            "semantic_role": "semantic_icon",
            "reason": "用无文字图标标识经营对象，服务系统的阅读路径。",
            "visual_family_id": "yili-retention-v1",
            "semantic_nodes": ["内容", "商品", "人群", "增长信号"],
            "text_forbidden": True,
            "html_protected_content": "对象名称、指标与关系标注。",
        }
        page = {"visual_mode": "opaque-module", "presentation_route": route}
        self.assertEqual(validate_presentation_route(page, "S01"), [])

    def test_image2_asset_requires_visual_family_id(self) -> None:
        route = self.presentation_route(expression_object="statement", anchor_kind="hybrid")
        route["image2_decision"] = {
            "decision": "generate",
            "semantic_role": "hero",
            "reason": "用主视觉强化本页观点。",
            "html_protected_content": "标题与精确数字。",
        }
        errors = validate_presentation_route(
            {"visual_mode": "opaque-module", "presentation_route": route},
            "S01",
        )
        self.assertTrue(any("visual_family_id is required" in error for error in errors))

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

    def test_deck_generation_requires_presentation_route_on_every_slide(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "deck").mkdir()
            (project / "evidence").mkdir()
            (project / "evidence" / "evidence-ledger.json").write_text(
                json.dumps({"evidence": []}),
                encoding="utf-8",
            )
            slide = {
                "slide_id": "P01",
                "chapter": "C1",
                "role": "statement",
                "layout": "statement",
                "title": "明确增长命题",
                "speaker_doc_anchor": "speaker:P01",
                "status": "content_frozen",
                "blocks": [],
                "visual": {},
                "evidence_ids": [],
            }
            slide["approved_content_hash"] = content_hash(slide)
            (project / "deck" / "deck-spec.json").write_text(
                json.dumps({
                    "deck_id": "deck-1",
                    "project_name": "Test",
                    "content_freeze_id": "freeze-1",
                    "design_version": "design-1",
                    "slides": [slide],
                }),
                encoding="utf-8",
            )
            (project / "deck" / "slide-contracts.json").write_text(
                json.dumps({"layouts": {"statement": {}}}),
                encoding="utf-8",
            )
            (project / "deck" / "design-tokens.json").write_text(
                json.dumps({"transparent_png": {"slots": []}}),
                encoding="utf-8",
            )
            errors = validate_deck(project)
            self.assertTrue(any("P01: presentation_route is required" in error for error in errors))

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

    def test_full_redteam_rejects_empty_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.write_full_redteam_project(project, [])
            errors = validate_project(project)
            self.assertTrue(any("At least one chapter" in error for error in errors))

    def test_full_redteam_requires_every_chapter_confirmed_with_source_and_slides(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.write_full_redteam_project(
                project,
                [{
                    "chapter_id": "C1",
                    "slides": [],
                    "manuscript_confirmed": False,
                    "confirmation_record_id": None,
                    "source_path": "content/chapters/missing.md",
                }],
            )
            errors = validate_project(project)
            self.assertTrue(any("slides must be non-empty" in error for error in errors))
            self.assertTrue(any("manuscript is not fully confirmed" in error for error in errors))
            self.assertTrue(any("missing confirmation_record_id" in error for error in errors))
            self.assertTrue(any("registered file does not exist" in error for error in errors))

    def test_full_redteam_rejects_local_markdown_without_verified_feishu_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            chapter_path = project / "content" / "chapters" / "C1.md"
            chapter_path.parent.mkdir(parents=True)
            chapter_path.write_text("# Confirmed C1\n", encoding="utf-8")
            self.write_full_redteam_project(
                project,
                [{
                    "chapter_id": "C1",
                    "slides": ["C1-S01"],
                    "manuscript_confirmed": True,
                    "confirmation_record_id": "confirm-C1",
                    "source_path": "content/chapters/C1.md",
                }],
            )
            errors = validate_project(project)
            self.assertTrue(any("verified Feishu proposal draft" in error for error in errors))

    def test_full_redteam_rejects_verified_feishu_draft_with_missing_page_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            chapter_path = project / "content" / "chapters" / "C1.md"
            chapter_path.parent.mkdir(parents=True)
            chapter_path.write_text("# Confirmed C1\n", encoding="utf-8")
            state = self.write_full_redteam_project(
                project,
                [{
                    "chapter_id": "C1",
                    "slides": ["C1-S01"],
                    "manuscript_confirmed": True,
                    "confirmation_record_id": "confirm-C1",
                    "source_path": "content/chapters/C1.md",
                }],
            )
            self.attach_verified_feishu_draft(project, state, ["C1-S01"])
            snapshot = project / "content" / "feishu" / "proposal-draft.md"
            text = snapshot.read_text(encoding="utf-8").replace("### 视觉生成建议", "### 视觉说明")
            snapshot.write_text(text, encoding="utf-8")
            state = json.loads((project / "project-state.json").read_text(encoding="utf-8"))
            state["proposal_draft"]["verified_snapshot_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            (project / "project-state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("missing section: 视觉生成建议" in error for error in errors))

    def test_full_redteam_requires_all_chapters_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            self.write_full_redteam_project(
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
            )
            (project / "content" / "chapters" / "C1.md").write_text(
                "# Confirmed C1\n",
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertTrue(any("C2: manuscript is not fully confirmed" in error for error in errors))
            self.assertTrue(any("C2: slides must be non-empty" in error for error in errors))

    def test_full_redteam_allows_all_confirmed_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            chapters = []
            for chapter_id in ("C1", "C2"):
                source_path = project / "content" / "chapters" / f"{chapter_id}.md"
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_text(f"# Confirmed {chapter_id}\n", encoding="utf-8")
                chapters.append({
                    "chapter_id": chapter_id,
                    "slides": [f"{chapter_id}-S01"],
                    "manuscript_confirmed": True,
                    "confirmation_record_id": f"confirm-{chapter_id}",
                    "source_path": f"content/chapters/{chapter_id}.md",
                })
            self.write_full_redteam_project(project, chapters)
            state = json.loads((project / "project-state.json").read_text(encoding="utf-8"))
            self.attach_verified_feishu_draft(
                project,
                state,
                [slide for chapter in chapters for slide in chapter["slides"]],
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
                    "materials_scope": self.approved("materials"),
                    "requirements": self.approved("requirements"),
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
                "design_calibration": {
                    "path": "deck/design-calibration.html",
                    "profile": "extended",
                    "planned_slide_count": 70,
                },
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("sample type: toc" in error for error in errors))
            self.assertTrue(any("sample type: chapter-data-led" in error for error in errors))
            self.assertTrue(any("sample type: content-visual-module" in error for error in errors))
            self.assertTrue(any("alpha_sample_path" in error for error in errors))

    def test_compact_design_calibration_accepts_six_risk_covering_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            calibration = project / "deck" / "design-calibration.html"
            calibration.parent.mkdir(parents=True)
            sample_types = (
                "cover",
                "toc",
                "chapter-image-led",
                "content-medium",
                "content-high",
                "closing",
            )
            calibration.write_text(
                "\n".join(
                    f'<section data-design-sample="{sample_type}"></section>'
                    for sample_type in sample_types
                ),
                encoding="utf-8",
            )
            state = {
                "phase": "design_calibration",
                "proposal_owner": "Owner",
                "approvals": {},
                "design_calibration": {
                    "path": "deck/design-calibration.html",
                    "profile": "compact",
                    "planned_slide_count": 20,
                },
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertFalse(any("Design calibration is missing required sample type" in error for error in errors), errors)
            self.assertFalse(any("design_calibration.profile" in error for error in errors), errors)
            self.assertFalse(any("required_sample_types" in error for error in errors), errors)

    def test_content_freeze_rejects_main_agent_full_draft_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            report = project / "reviews" / "redteam" / "FULL.json"
            report.parent.mkdir(parents=True)
            report.write_text(
                json.dumps({
                    "status": "passed",
                    "review_agent_id": "local-main-agent-full-rt",
                    "independent_agent": False,
                }),
                encoding="utf-8",
            )
            state = {
                "phase": "content_frozen",
                "proposal_owner": "Owner",
                "content_freeze_id": "freeze-v1",
                "approvals": {
                    "full_redteam": self.approved("full-redteam"),
                    "content_freeze": self.approved("freeze-v1"),
                },
                "full_redteam": {
                    "report_path": "reviews/redteam/FULL.json",
                    "review_agent_id": "local-main-agent-full-rt",
                    "independent_agent": False,
                },
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("independent review agent" in error for error in errors))

    def test_visual_direction_requires_explicit_brand_scope_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            state = {
                "phase": "visual_direction",
                "proposal_owner": "Owner",
                "approvals": {},
                "brand_visual": {
                    "source_ids": ["BRAND-001"],
                    "source_files": ["inputs/brand-official/guide.svg"],
                },
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("brand_visual.scope_decision" in error for error in errors))

    def test_visual_direction_rejects_direction_notes_without_image2_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            state = {
                "phase": "design_calibration",
                "proposal_owner": "Owner",
                "content_freeze_id": "freeze-v1",
                "approvals": {
                    "visual_direction": self.approved("visual-direction-1"),
                },
                "visual_direction": {
                    "selected_direction_id": "DIR-A",
                    "approval_record_id": "visual-direction-1",
                    "directions": [
                        {
                            "direction_id": "DIR-A",
                            "name": "方向说明A",
                            "visual_thesis": "深蓝与金色表现产品科技。",
                        },
                        {
                            "direction_id": "DIR-B",
                            "name": "方向说明B",
                            "visual_thesis": "暖色生活方式表现家庭关系。",
                        },
                    ],
                },
                "brand_visual": {},
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertTrue(any("must register at least one real Image2 draft" in error for error in errors))

    def test_visual_direction_accepts_two_registered_image2_direction_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            directions = []
            for direction_id in ("DIR-A", "DIR-B"):
                asset = project / "assets" / "image2" / f"{direction_id}.png"
                prompt = project / "assets" / "image2" / f"{direction_id}-prompt.md"
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(b"registered image2 draft")
                prompt.write_text("Image2 prompt record.", encoding="utf-8")
                directions.append({
                    "direction_id": direction_id,
                    "name": f"视觉方向{direction_id}",
                    "visual_thesis": f"{direction_id}的独立视觉命题。",
                    "visual_family_id": f"family-{direction_id.lower()}",
                    "representative_slide_ids": ["COVER"],
                    "image2_assets": [{
                        "generator": "image2",
                        "asset_path": f"assets/image2/{direction_id}.png",
                        "prompt_record": f"assets/image2/{direction_id}-prompt.md",
                    }],
                })
            state = {
                "phase": "design_calibration",
                "proposal_owner": "Owner",
                "content_freeze_id": "freeze-v1",
                "approvals": {
                    "visual_direction": self.approved("visual-direction-1"),
                },
                "visual_direction": {
                    "selected_direction_id": "DIR-A",
                    "approval_record_id": "visual-direction-1",
                    "directions": directions,
                },
                "brand_visual": {},
                "chapters": [],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(
                json.dumps(state, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = validate_project(project)
            self.assertFalse(any("visual_direction." in error for error in errors), errors)

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
                    key: self.approved(key)
                    for key in (
                        "brief_grill", "proposal_brief", "content_freeze", "brand_visual_sources",
                        "brand_visual_audit", "brand_visual_incorporation", "visual_direction", "design",
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
                    "chapter_id": "C1", "manuscript_confirmed": True,
                    "confirmation_record_id": "confirmed",
                }],
                "reopen_log": [],
            }
            (project / "project-state.json").write_text(json.dumps(state), encoding="utf-8")
            errors = validate_project(project)
            self.assertTrue(any("DESIGN.md does not cite brand visual source id: BRAND-001" in error for error in errors))

    def test_review_runtime_requires_responsive_preview_and_narrow_viewport_qa(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        template = (skill_root / "assets" / "html-runtime" / "deck-template.html").read_text(encoding="utf-8")
        capture = (skill_root / "scripts" / "capture_review_pngs.mjs").read_text(encoding="utf-8")
        self.assertIn("function updatePreviewScale()", template)
        self.assertIn("Math.min(1, availableWidth / 1920)", template)
        self.assertIn("?export=1&review=1", capture)
        self.assertIn("width:594,height:863", capture)
        self.assertIn("responsive-preview-overflow", capture)


if __name__ == "__main__":
    unittest.main()
