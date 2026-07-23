from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
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
        write_json(project / "deck" / "deck-spec.json", deck)

    def prepare_pre_freeze_state(self, project: Path) -> None:
        initial = read_json(project / "project-state.json")
        demo = read_json(DEMO / "project-state.json")
        demo.update({
            "project_id": "中文-e2e",
            "project_name": "中文路径端到端测试",
            "proposal_owner": "测试负责人",
            "phase": "full_redteam",
            "content_freeze_id": None,
            "active_chapter_id": "C1",
            "assembly": initial["assembly"],
            "reopen_log": [],
        })
        demo["approvals"]["full_redteam"] = approved("full-redteam-1")
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
            "redteam_passed": True,
            "redteam_report": "reviews/redteam/C1.json",
        }]
        write_json(project / "project-state.json", demo)
        (project / "content" / "chapters" / "C1.md").write_text(
            "# 已确认章节\n\n两页端到端测试。\n",
            encoding="utf-8",
        )
        write_json(project / "reviews" / "redteam" / "C1.json", {"status": "passed"})

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
                "presentation_route": {
                    "service_object": "端到端自动化验收",
                    "use_situation": "机器导出验证",
                    "presentation_task": "确认页面可渲染并保持顺序",
                    "content_relation": "事实",
                    "expression_object": "statement",
                    "best_carrier": "HTML页面",
                    "dominant_type": "information_first",
                    "anchor_kind": "html",
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
                        "decision": "not_generate",
                        "semantic_role": "none",
                        "reason": "本测试只验证HTML导出链路",
                        "html_protected_content": "冻结文字与页面顺序",
                    },
                    "image2_task": "不生成",
                    "html_task": "承载冻结文字与页面顺序",
                    "visual_balance_plan": "主标题优先",
                },
                "visual_mode": "none",
                "visual_not_required_reason": "HTML承担本测试的可见主载体",
                "visual": {},
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
        state["approvals"]["content_qa"] = approved("content-qa-1")
        state["approvals"]["visual_qa"] = approved("visual-qa-1")
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
