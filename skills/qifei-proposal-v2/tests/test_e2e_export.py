from __future__ import annotations

import json
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
DEMO = REPO_ROOT / "demo" / "visual-sample"
sys.path.insert(0, str(SCRIPTS))

from build_identity import build_id  # noqa: E402


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def approved(record_id: str) -> dict:
    return {"approved": True, "by": "测试负责人", "at": "2026-07-23T00:00:00+08:00", "record_id": record_id}


class EndToEndExportTests(unittest.TestCase):
    maxDiff = None

    def run_command(self, command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=cwd or SKILL_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    @staticmethod
    def presentation_route() -> dict:
        return {
            "service_object": "端到端自动化验收",
            "use_situation": "机器导出验证",
            "presentation_task": "确认页面可渲染并保持顺序",
            "content_relation": "事实",
            "expression_object": "statement",
            "best_carrier": "HTML页面",
            "dominant_type": "information_first",
            "anchor_kind": "hybrid",
            "visual_argument": {
                "first_glance": "页面主标题",
                "reading_path": "标题到正文",
                "end_focus": "冻结内容",
            },
            "visual_hammer": {
                "primary_object": "页面主标题",
                "supporting_elements": "正文服务主标题",
                "orphan_element_check": "无孤儿元素",
            },
            "image2_decision": {
                "decision": "generate",
                "semantic_role": "semantic_icon",
                "reason": "使用同一视觉家族的无文字语义资产验证混合导出链路",
                "visual_family_id": "e2e-visual-family",
                "semantic_nodes": ["冻结内容"],
                "text_forbidden": True,
                "html_protected_content": "冻结文字与页面顺序",
            },
            "image2_task": "提供无文字语义视觉资产",
            "html_task": "承载冻结文字与页面顺序",
            "visual_balance_plan": "主标题优先",
        }

    @staticmethod
    def write_alpha_png(path: Path) -> None:
        def chunk(name: bytes, data: bytes) -> bytes:
            checksum = zlib.crc32(name + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", checksum)

        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        raw = b"\x00\x00\x00\x00\x00"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )

    def copy_fixture_sources(self, project: Path) -> None:
        for name in ("AGENTS.md", "DESIGN.md"):
            shutil.copy2(DEMO / name, project / name)
        for directory in ("assets", "content", "evidence", "inputs"):
            shutil.copytree(DEMO / directory, project / directory, dirs_exist_ok=True)
        for name in ("design-calibration.html", "design-tokens.json", "slide-contracts.json"):
            shutil.copy2(DEMO / "deck" / name, project / "deck" / name)
        deck = read_json(DEMO / "deck" / "deck-spec.json")
        deck["project_name"] = "中文路径端到端测试"
        deck["slides"] = deck["slides"][:2]
        deck["content_freeze_id"] = None
        for slide in deck["slides"]:
            slide["presentation_route"] = self.presentation_route()
            slide["visual_mode"] = "opaque-module"
            slide["visual"] = {"src": "assets/approved/e2e-visual.png"}
        write_json(project / "deck" / "deck-spec.json", deck)
        e2e_visual = "assets/approved/e2e-visual.png"
        self.write_alpha_png(project / e2e_visual)
        prompt_record = "assets/image2/e2e-visual-prompt.md"
        (project / prompt_record).parent.mkdir(parents=True, exist_ok=True)
        (project / prompt_record).write_text("无文字语义视觉测试资产。", encoding="utf-8")
        write_json(project / "assets" / "asset-manifest.json", {
            "schema_version": "1.0",
            "assets": [{
                "asset_id": "e2e-visual",
                "path": e2e_visual,
                "status": "approved",
                "visual_family_id": "e2e-visual-family",
                "semantic_role": "semantic_icon",
                "prompt_record": prompt_record,
            }],
        })
        tokens_path = project / "deck" / "design-tokens.json"
        tokens = read_json(tokens_path)
        tokens["visual_family_id"] = "e2e-visual-family"
        write_json(tokens_path, tokens)
        alpha_relative = "assets/approved/alpha/calibration.png"
        self.write_alpha_png(project / alpha_relative)
        calibration_path = project / "deck" / "design-calibration.html"
        calibration_text = calibration_path.read_text(encoding="utf-8")
        calibration_path.write_text(
            calibration_text.replace(
                '<div class="alpha-slot" aria-label="透明 PNG 模块槽位预览"></div>',
                f'<img class="alpha-slot" src="../{alpha_relative}" alt="透明 PNG 模块槽位预览">',
            ),
            encoding="utf-8",
        )

    def prepare_pre_freeze_state(self, project: Path) -> None:
        initial = read_json(project / "project-state.json")
        demo = read_json(DEMO / "project-state.json")
        demo.update({
            "project_id": "中文-e2e",
            "project_name": "中文路径端到端测试",
            "proposal_owner": "测试负责人",
            "phase": "full_redteam",
            "content_freeze_id": None,
            "assembly": initial["assembly"],
            "reopen_log": [],
        })
        demo["approvals"]["full_redteam"] = approved("full-redteam-1")
        demo["full_redteam"] = {
            "report_path": "reviews/redteam/FULL.json",
            "review_agent_id": "independent-review-agent-e2e",
            "independent_agent": True,
        }
        demo["brand_visual"].update({
            "scope_decision": "official_brand",
            "project_brand_name": "Demo Brand",
        })
        direction_records = []
        for direction_id in ("DIR-A", "DIR-B"):
            direction_asset = project / "assets" / "image2" / f"{direction_id}.png"
            direction_prompt = project / "assets" / "image2" / f"{direction_id}-prompt.md"
            direction_asset.parent.mkdir(parents=True, exist_ok=True)
            direction_asset.write_bytes(b"registered e2e image2 direction draft")
            direction_prompt.write_text("Image2 direction prompt.", encoding="utf-8")
            direction_records.append({
                "direction_id": direction_id,
                "name": f"端到端方向{direction_id}",
                "visual_thesis": f"{direction_id}独立视觉命题",
                "visual_family_id": f"e2e-{direction_id.lower()}",
                "representative_slide_ids": ["D01"],
                "image2_assets": [{
                    "generator": "image2",
                    "asset_path": f"assets/image2/{direction_id}.png",
                    "prompt_record": f"assets/image2/{direction_id}-prompt.md",
                }],
            })
        demo["visual_direction"] = {
            "directions": direction_records,
            "selected_direction_id": "DIR-A",
            "approval_record_id": demo["approvals"]["visual_direction"]["record_id"],
        }
        demo["design_calibration"]["alpha_sample_path"] = "assets/approved/alpha/calibration.png"
        demo["design_calibration"]["profile"] = "extended"
        demo["design_calibration"]["planned_slide_count"] = 70
        demo["approvals"]["content_freeze"] = {
            "approved": False, "by": None, "at": None, "record_id": None,
        }
        demo["approvals"]["content_qa"] = {
            "approved": False, "by": None, "at": None, "record_id": None,
        }
        demo["approvals"]["visual_qa"] = {
            "approved": False, "by": None, "at": None, "record_id": None,
        }
        demo["approvals"]["final_assembly"] = {
            "approved": False, "by": None, "at": None, "record_id": None,
        }
        demo["chapters"] = [{
            "chapter_id": "C1",
            "slides": ["D01", "D02"],
            "source_path": "content/chapters/C1.md",
            "manuscript_confirmed": True,
            "confirmation_record_id": "confirm-C1",
        }]
        snapshot = (
            "# 第一章｜端到端验证\n\n"
            "**本章回答：** 验证导出链路。\n\n"
            "**逻辑路径：** 输入 → 渲染 → 导出。\n\n"
            "**情绪方向：** 确认链路稳定。\n\n"
            "## D01｜第一页\n\n"
            "### 核心内容\n验证第一页。\n\n"
            "### 逻辑展开\n输入到输出。\n\n"
            "### PPT上屏内容\n第一页。\n\n"
            "### 讲解方向\n说明第一页。\n\n"
            "### 策略与过桥\n进入第二页。\n\n"
            "### 视觉生成建议\n使用HTML与视觉资产。\n\n"
            "### 证据与来源\n端到端夹具。\n\n"
            "## D02｜第二页\n\n"
            "### 核心内容\n验证第二页。\n\n"
            "### 逻辑展开\n承接第一页。\n\n"
            "### PPT上屏内容\n第二页。\n\n"
            "### 讲解方向\n说明第二页。\n\n"
            "### 策略与过桥\n完成验证。\n\n"
            "### 视觉生成建议\n使用HTML与视觉资产。\n\n"
            "### 证据与来源\n端到端夹具。\n"
        )
        snapshot_path = project / "content" / "feishu" / "proposal-draft.md"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(snapshot, encoding="utf-8")
        demo["proposal_draft"] = {
            "authority": "feishu",
            "status": "verified",
            "format_version": "feishu-proposal-draft-v1",
            "feishu_doc_url": "https://example.feishu.cn/docx/e2e",
            "document_id": "e2e-doc",
            "revision_id": 1,
            "last_verified_at": "2026-07-23T00:00:00+08:00",
            "verified_snapshot_path": "content/feishu/proposal-draft.md",
            "verified_snapshot_sha256": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
            "verified_slide_ids": ["D01", "D02"],
            "fallback_reason": None,
        }
        write_json(project / "project-state.json", demo)
        (project / "content" / "chapters" / "C1.md").write_text(
            "# 已确认章节\n\n两页端到端测试。\n",
            encoding="utf-8",
        )
        write_json(project / "reviews" / "redteam" / "FULL.json", {
            "status": "passed",
            "review_agent_id": "independent-review-agent-e2e",
            "independent_agent": True,
        })

    def design_loop_report(self, project: Path) -> None:
        state = read_json(project / "project-state.json")
        checks = {
            name: True
            for name in (
                "manuscript_fidelity", "brand_consistency", "design_contract", "no_overflow",
                "image_html_cohesion", "visual_argument_realized", "visual_hammer_realized",
                "remote_readability", "visual_balance", "browser_comments_resolved",
            )
        }
        pages = []
        for slide_id, template_id in (("D01", "hero"), ("D02", "cards")):
            pages.append({
                "slide_id": slide_id,
                "iterations": 1,
                "template_id": template_id,
                "core_expression": "验证冻结内容、浏览器渲染与批准页面一致",
                "presentation_route": self.presentation_route(),
                "visual_mode": "opaque-module",
                "visual": {
                    "asset_id": "e2e-visual",
                    "asset_path": "assets/approved/e2e-visual.png",
                    "prompt_record": "assets/image2/e2e-visual-prompt.md",
                },
                "html_output": "deck/chapters/C1.html",
                "validation": checks,
                "result": "pass",
                "next_action": "pass",
            })
        report = {
            "schema_version": "1.0",
            "chapter_id": "C1",
            "design_version": state["design_version"],
            "loop_steps": ["template", "image2", "html", "validate"],
            "chapter_html": "deck/chapters/C1.html",
            "status": "passed",
            "pages": pages,
            "approved_by": "测试负责人",
            "approval_record_id": "design-loop-C1",
        }
        write_json(project / "reviews" / "design-loop" / "C1.json", report)
        state["phase"] = "export"
        state["approvals"]["design_loop"] = approved("design-loop-all")
        state["approvals"]["final_page_order"] = approved("final-order-1")
        state["approvals"]["speaker_notes"] = approved("speaker-notes-1")
        state["approvals"]["content_qa"] = approved("content-qa-1")
        state["approvals"]["visual_qa"] = approved("visual-qa-1")
        notes_path = project / "content" / "speaker-notes.md"
        notes_path.write_text("# 最终讲稿\n\nD01\n\nD02\n", encoding="utf-8")
        state["speaker_notes"] = {
            "status": "verified",
            "final_slide_count": 2,
            "final_order_hash": hashlib.sha256(b"D01\nD02").hexdigest(),
            "feishu_doc_url": "https://example.feishu.cn/docx/e2e-notes",
            "local_backup_path": "content/speaker-notes.md",
        }
        state["chapters"][0].update({
            "design_loop_passed": True,
            "design_loop_report": "reviews/design-loop/C1.json",
            "design_loop_record_id": "design-loop-C1",
        })
        write_json(project / "project-state.json", state)

    def test_two_page_chinese_path_export_chain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="提案端到端-") as temp:
            project = Path(temp) / "中文项目与素材"
            self.run_command([
                sys.executable, str(SCRIPTS / "init_project.py"),
                "--project", str(project),
                "--name", "中文路径端到端测试",
                "--owner", "测试负责人",
            ])
            self.copy_fixture_sources(project)
            self.prepare_pre_freeze_state(project)
            self.run_command([
                sys.executable, str(SCRIPTS / "freeze_deck_spec.py"), str(project),
                "--approved-by", "测试负责人", "--approval-id", "freeze-中文-1",
            ])

            state = read_json(project / "project-state.json")
            state["phase"] = "generation"
            write_json(project / "project-state.json", state)
            self.run_command([sys.executable, str(SCRIPTS / "render_deck.py"), str(project), "--chapter-id", "C1"])
            self.run_command([sys.executable, str(SCRIPTS / "render_deck.py"), str(project)])
            self.run_command(["node", str(SCRIPTS / "capture_review_pngs.mjs"), str(project)])
            state = read_json(project / "project-state.json")
            state["phase"] = "review"
            write_json(project / "project-state.json", state)

            review_relative = "deck/review/full/review-manifest.json"
            for index, slide_id in enumerate(("D01", "D02"), start=1):
                self.run_command([
                    sys.executable, str(SCRIPTS / "manage_assembly_ready.py"), str(project),
                    "approve", "--review-manifest", review_relative, "--slide-id", slide_id,
                    "--approved-by", "测试负责人", "--approval-id", f"page-{index}",
                ])
            self.run_command([
                sys.executable, str(SCRIPTS / "manage_assembly_ready.py"), str(project),
                "finalize", "--approved-by", "测试负责人", "--approval-id", "final-1",
            ])
            self.design_loop_report(project)
            self.run_command(["node", str(SCRIPTS / "export_deck.mjs"), str(project)])

            pngs = sorted((project / "exports" / "png").glob("*.png"))
            self.assertEqual([path.stem for path in pngs], ["D01", "D02"])
            with zipfile.ZipFile(project / "exports" / "proposal-preview.pptx") as archive:
                slides = sorted(
                    name
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                )
            self.assertEqual(len(slides), 2)
            pdf_count = self.run_command([
                "node", "--input-type=module", "-e",
                (
                    "import {readFileSync} from 'node:fs';"
                    "import {PDFDocument} from 'pdf-lib';"
                    "const p=await PDFDocument.load(readFileSync(process.argv[1]));"
                    "console.log(p.getPageCount());"
                ),
                str(project / "exports" / "proposal.pdf"),
            ]).stdout.strip()
            self.assertEqual(pdf_count, "2")

            deck = read_json(project / "deck" / "deck-spec.json")
            state = read_json(project / "project-state.json")
            manifest = read_json(project / "deck" / "build-manifest.json")
            assembly = read_json(project / "deck" / "assembly-ready" / "manifest.json")
            self.assertEqual([slide["slide_id"] for slide in deck["slides"]], ["D01", "D02"])
            self.assertEqual([page["slide_id"] for page in assembly["pages"]], ["D01", "D02"])
            self.assertEqual(state["content_freeze_id"], "freeze-中文-1")
            self.assertEqual(deck["content_freeze_id"], "freeze-中文-1")
            self.assertEqual(manifest["content_freeze_id"], "freeze-中文-1")
            self.assertEqual(manifest["design_version"], "design-v1")
            self.assertEqual(
                manifest["build_id"],
                build_id(manifest["inputs"], manifest["runtime"], None),
            )


if __name__ == "__main__":
    unittest.main()
