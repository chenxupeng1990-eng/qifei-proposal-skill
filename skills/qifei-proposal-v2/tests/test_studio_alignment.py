"""v0.3.3: a misplaced heading must not silently hide confirm buttons; the Owner can take back a confirmation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QIFEI_MEMORY_HOME", tempfile.mkdtemp(prefix="qifei-memory-test-"))

import draft_studio  # noqa: E402
from test_draft_format import page  # noqa: E402

GOOD = "\n".join([
    "# 开场｜重新选择增长伙伴", "",
    page("P01", "长期经营而不是一次传播"),
    page("P02", "单一渠道能力不再构成竞争优势"),
    "# 打法｜把品牌经营成生活方式", "",
    page("P03", "内容就是货架"),
])

# P02 was inserted after the next chapter's heading: it is registered in C1 but drafted under 打法.
MISPLACED = "\n".join([
    "# 开场｜重新选择增长伙伴", "",
    page("P01", "长期经营而不是一次传播"),
    "# 打法｜把品牌经营成生活方式", "",
    page("P02", "单一渠道能力不再构成竞争优势"),
    page("P03", "内容就是货架"),
])


def make_project(root: Path, draft: str) -> Path:
    (root / "content" / "draft").mkdir(parents=True)
    (root / "content" / "draft" / "proposal-draft.md").write_text(draft, encoding="utf-8")
    state = {
        "phase": "manuscript", "proposal_owner": "Owner", "task_mode": "full_deck", "content_authority": "studio",
        "proposal_draft": {"authority": "studio", "status": "not_started", "format_version": "proposal-draft-v2",
                           "verified_snapshot_path": "content/draft/proposal-draft.md", "verified_slide_ids": []},
        "chapters": [
            {"chapter_id": "C1", "slides": ["P01", "P02"], "manuscript_confirmed": False, "confirmation_record_id": None},
            {"chapter_id": "C2", "slides": ["P03"], "manuscript_confirmed": False, "confirmation_record_id": None},
        ],
    }
    (root / "project-state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return root


def state(root: Path) -> dict:
    return json.loads((root / "project-state.json").read_text(encoding="utf-8"))


class ChapterAlignmentTests(unittest.TestCase):
    def test_aligned_draft_has_no_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), GOOD)
            model = draft_studio.parse_draft(GOOD)
            self.assertEqual(draft_studio.chapter_alignment_issues(model, state(root)), [])

    def test_misplaced_page_is_reported_and_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), MISPLACED)
            issues = draft_studio.chapter_alignment_issues(draft_studio.parse_draft(MISPLACED), state(root))
            self.assertTrue(any(i["page"] == "C1" and "P02" in i["message"] and "打法" in i["message"] for i in issues))
            run = subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "check", str(root)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stdout)
            self.assertIn("分到了不同章节", run.stdout)

    def test_studio_names_the_reason_instead_of_a_generic_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), MISPLACED)
            draft_path = root / "content" / "draft" / "proposal-draft.md"
            model = draft_studio.model_from_text(MISPLACED, root, draft_path, state(root))
            draft_studio.annotate_studio(model, state(root), draft_studio.ConfirmationStore(draft_path), 1)
            first = model["chapters"][0]["studio"]
            self.assertIsNone(first["chapter_id"])
            self.assertIn("P02", first["reason"])
            self.assertTrue(model["alignment_issues"])

    def test_title_heading_with_no_pages_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = "# 提案总标题\n\n一句说明。\n\n" + GOOD
            root = make_project(Path(tmp), draft)
            issues = draft_studio.chapter_alignment_issues(draft_studio.parse_draft(draft), state(root))
            self.assertTrue(any("总标题" in i["message"] for i in issues), issues)

    def test_render_says_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), GOOD)
            run = subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "render", str(root)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("READ-ONLY", run.stdout)
            self.assertIn("只读预览", (SKILL_ROOT / "assets" / "draft-studio" / "studio.js").read_text(encoding="utf-8"))


class RetractConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_project(Path(self.tmp.name), GOOD)
        self.draft = self.root / "content" / "draft" / "proposal-draft.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_retract_chapter(self) -> None:
        draft_studio.confirm_chapter(self.root, self.draft, "C1", "Owner")
        self.assertTrue(state(self.root)["chapters"][0]["manuscript_confirmed"])
        record = draft_studio.retract_confirmation(self.root, self.draft, "Owner", chapter_id="C1")
        chapter = state(self.root)["chapters"][0]
        self.assertFalse(chapter["manuscript_confirmed"])
        self.assertEqual(chapter["page_confirmations"], {})
        self.assertEqual(record["scope"], "retract")
        records = draft_studio.ConfirmationStore(self.draft).load()["records"]
        self.assertEqual([r.get("scope") for r in records][-1], "retract")
        model = draft_studio.model_from_text(GOOD, self.root, self.draft, state(self.root))
        self.assertEqual({s["status"] for s in model["chapters"][0]["slides"]}, {"pending"})

    def test_retract_one_page_reopens_the_chapter_only(self) -> None:
        draft_studio.confirm_chapter(self.root, self.draft, "C1", "Owner")
        draft_studio.retract_confirmation(self.root, self.draft, "Owner", slide_id="P02")
        chapter = state(self.root)["chapters"][0]
        self.assertFalse(chapter["manuscript_confirmed"])
        self.assertIn("P01", chapter["page_confirmations"])
        self.assertNotIn("P02", chapter["page_confirmations"])

    def test_nothing_to_retract(self) -> None:
        with self.assertRaises(draft_studio.EditError):
            draft_studio.retract_confirmation(self.root, self.draft, "Owner", chapter_id="C2")



class ReviewHookTests(unittest.TestCase):
    def test_inject_then_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "deck" / "pages" / "P01.html"
            page.parent.mkdir(parents=True)
            page.write_text('<html><head></head><body><section class="slide-canvas" data-slide-id="P01">'
                            '<h1>标题</h1><div data-screen-ignore><p>备注</p></div><p data-edit="off">页码</p>'
                            '</section></body></html>', encoding="utf-8")
            hooks = [sys.executable, str(SCRIPTS / "review_hooks.py")]
            self.assertEqual(subprocess.run([*hooks, "check", tmp, str(page)], capture_output=True).returncode, 1)
            subprocess.run([*hooks, "inject", tmp, str(page)], check=True, capture_output=True)
            html = page.read_text(encoding="utf-8")
            self.assertIn('data-edit-id="P01.t01"', html)
            self.assertEqual(html.count("data-edit-id"), 1)
            self.assertTrue((root / "deck" / "review-editor" / "loader.js").is_file())
            run = subprocess.run([*hooks, "check", tmp, str(page)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout)
            # A rewrite that drops the hooks is caught.
            page.write_text("<html><head></head><body><h1>新标题</h1></body></html>", encoding="utf-8")
            self.assertEqual(subprocess.run([*hooks, "check", tmp, str(page)], capture_output=True).returncode, 1)



class WireframeTests(unittest.TestCase):
    def test_coverage_and_cli(self) -> None:
        screen = "标题：长期经营而不是一次传播\n价格角色：品牌锚点｜日常主销\n- 功效：32%"
        draft = "# 开场｜重新选择增长伙伴\n\n" + page("P01", "长期经营而不是一次传播", {"PPT上屏内容": screen}) + page("P02", "渠道")
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), draft)
            wires = root / "content" / "draft" / "wireframes.json"
            wire = {"form": "数据对照", "why": "核心是数字。", "blocks": [
                {"type": "text", "role": "title", "x": 96, "y": 80, "w": 1400, "h": 72, "lines": ["长期经营而不是一次传播"]},
                {"type": "step", "x": 96, "y": 260, "w": 900, "h": 180, "num": "品牌锚点", "label": "日常主销", "tag": ""},
                {"type": "stat", "x": 96, "y": 700, "w": 240, "h": 150, "num": "32%", "label": "功效"},
                {"type": "image", "x": 1200, "y": 200, "w": 600, "h": 600, "note": "产品立在石材上"}]}
            wires.write_text(json.dumps({"pages": {"P01": wire}}, ensure_ascii=False), encoding="utf-8")
            model = draft_studio.model_from_text(draft, root, root / "content" / "draft" / "proposal-draft.md", state(root))
            p01 = model["chapters"][0]["slides"][0]
            self.assertEqual(p01["wireframe"]["coverage"], {"missing": [], "extra": []})
            issues = draft_studio.wireframe_issues(model)
            self.assertEqual([i["page"] for i in issues], ["P02"])  # P02 has no wireframe yet
            wire["blocks"].append({"type": "text", "role": "sub", "x": 0, "y": 0, "w": 10, "h": 10, "lines": ["讲解时先强调"]})
            wire["blocks"] = [b for b in wire["blocks"] if b["type"] != "stat"]
            wires.write_text(json.dumps({"pages": {"P01": wire}}, ensure_ascii=False), encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "wireframes", str(root)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn("32%", run.stdout)
            self.assertIn("讲解时先强调", run.stdout)


if __name__ == "__main__":
    unittest.main()
