"""Gates added after the full-flow test: Owner-only approvals and waivers, memory signals before a
phase change, DESIGN.md content, on-screen text against the draft, caution phrases on screen,
the independent visual review, and design review comments."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["QIFEI_MEMORY_HOME"] = tempfile.mkdtemp(prefix="qifei-memory-test-")  # never touch real memory

import design_review  # noqa: E402
import draft_studio  # noqa: E402
import proposal_memory  # noqa: E402
import screen_text  # noqa: E402
import validate_project as vp  # noqa: E402
from memory_fixtures import mark_signals_run  # noqa: E402
from test_draft_studio import FEISHU_DRAFT  # noqa: E402
from test_draft_studio_live import StudioServerCase  # noqa: E402


def png(width: int = 32, height: int = 18, shade: int = 200) -> bytes:
    raw = b"".join(b"\x00" + bytes([shade, shade, shade]) * width for _ in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class OwnerWaiverTests(unittest.TestCase):
    def state(self, by: str) -> dict:
        return {"proposal_owner": "林某（Proposal Owner）",
                "approvals": {"x": {"approved": True, "by": by, "at": "2026-10-26", "record_id": "APR-1"}},
                "validation_waivers": [{"error": "E1", "reason": "Owner accepted", "record_id": "APR-1"}]}

    def test_owner_record_waives_the_named_error(self) -> None:
        self.assertEqual(vp.apply_waivers(self.state("林某"), ["E1", "E2"]), ["E2"])

    def test_agent_cannot_waive_its_own_errors(self) -> None:
        errors = vp.apply_waivers(self.state("Codex 主代理"), ["E1"])
        self.assertIn("E1", errors)
        self.assertTrue(any("agents cannot waive" in e for e in errors))


class SignalsGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        write_json(self.project / "project-state.json", {"project_id": f"gate-{id(self)}", "phase": "full_redteam"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def signals_errors(self) -> list[str]:
        return [e for e in vp.validate_project(self.project) if "没有汇总记忆信号" in e]

    def test_leaving_a_phase_without_signals_is_blocked(self) -> None:
        self.assertTrue(self.signals_errors())
        mark_signals_run(self.project)
        self.assertEqual(self.signals_errors(), [])

    def test_advance_distils_the_old_phase_and_loads_the_new_one(self) -> None:
        nxt = vp.PHASES[vp.PHASES.index("full_redteam") + 1]
        out = proposal_memory.render_advance(self.project, nxt)
        self.assertIn(f"full_redteam → {nxt}", out)
        self.assertEqual(proposal_memory.read_signals_receipt(self.project)["phase"], "full_redteam")
        write_json(self.project / "project-state.json", {"project_id": f"gate-{id(self)}", "phase": nxt})
        self.assertEqual(self.signals_errors(), [])
        with self.assertRaises(ValueError):
            proposal_memory.render_advance(self.project, "nowhere")

    def test_switching_memory_off_drops_both_memory_gates(self) -> None:
        home = Path(os.environ["QIFEI_MEMORY_HOME"])
        (home / "owner.md").write_text("# Owner 偏好\n\n## O-0001｜开场先亮判断\n- 阶段：all\n- 状态：active\n"
                                       "- 日期：2026-10-26\n- 来源：测试\n\n正文。\n", encoding="utf-8")
        memory_errors = lambda: [e for e in vp.validate_project(self.project) if e.startswith(vp.MEMORY_ERROR)]
        try:
            self.assertTrue(memory_errors())
            proposal_memory.set_memory_enabled(False)
            self.assertFalse(proposal_memory.memory_enabled())
            self.assertEqual(memory_errors(), [])
            os.environ["QIFEI_MEMORY"] = "on"  # the environment overrides the saved setting
            self.assertTrue(proposal_memory.memory_enabled())
        finally:
            os.environ.pop("QIFEI_MEMORY", None)
            proposal_memory.set_memory_enabled(True)
            (home / "owner.md").unlink()

    def test_owner_note_becomes_a_signal(self) -> None:
        note_id = proposal_memory.add_note(self.project, "竞品对标只用同档国际线", "S07")
        self.assertEqual(note_id, "N-0001")
        self.assertTrue(any(s["ref"] == "N-0001" for s in proposal_memory.studio_signals(self.project)))


class DesignContentTests(unittest.TestCase):
    def test_headings_alone_do_not_pass(self) -> None:
        errors = vp.design_content_errors("# DESIGN\n## 网格\n## 字号\n## 文字区\n## QA\n")
        self.assertEqual(len(errors), 8)

    def test_filled_design_passes(self) -> None:
        text = (SKILL_ROOT.parents[1] / "demo" / "visual-sample" / "DESIGN.md").read_text(encoding="utf-8")
        self.assertEqual(vp.design_content_errors(text), [])


class ScreenTextTests(unittest.TestCase):
    expected = {"slide_id": "S03", "title": "香气是复购理由", "lines": ["Instagram 搜索热度 +38%", "来源：Google Trends 2025"]}

    def test_matching_page_passes_and_ordinals_page_ids_and_whitelist_are_ignored(self) -> None:
        chunks = ["S03", "香气是复购理由", "01 Instagram 搜索热度 +38%", "来源：Google Trends 2025", "示例品牌"]
        result = screen_text.compare(self.expected, chunks, {screen_text.norm("示例品牌")})
        self.assertEqual(result, {"missing": [], "extra": []})

    def test_missing_and_extra_lines_are_both_errors(self) -> None:
        result = screen_text.compare(self.expected, ["香气是复购理由", "Instagram 搜索热度 +38%", "数据仅供参考"], set())
        self.assertEqual(result["missing"], ["来源：Google Trends 2025"])
        self.assertEqual(result["extra"], ["数据仅供参考"])


class CautionLintTests(unittest.TestCase):
    def caution(self, text: str) -> list[str]:
        return [i["message"] for i in draft_studio.check_format(text) if "内部审慎用语" in i["message"]]

    def test_caution_phrase_on_screen_is_flagged(self) -> None:
        self.assertEqual(self.caution(FEISHU_DRAFT), [])
        draft = FEISHU_DRAFT.replace("| 标题 | 示例品牌中国市场长期合作提案 |", "| 标题 | 示例品牌中国市场长期合作提案，不代表最终报价 |", 1)
        self.assertNotEqual(draft, FEISHU_DRAFT)
        self.assertEqual(len(self.caution(draft)), 1)
        self.assertIn("不代表", self.caution(draft)[0])

    def test_caution_outside_the_screen_field_is_fine(self) -> None:
        draft = FEISHU_DRAFT.replace("### 讲解方向\n", "### 讲解方向\n搜索热度不等于销量，讲的时候说明口径。\n", 1)
        self.assertNotEqual(draft, FEISHU_DRAFT)
        self.assertEqual(self.caution(draft), [])


class IntroFingerprintTests(unittest.TestCase):
    def test_editing_a_chapter_intro_reopens_its_pages(self) -> None:
        updated, _ = draft_studio.apply_edit(FEISHU_DRAFT, {"kind": "intro", "chapter": "ch01", "md": "**本章回答：** 新的问题。"})
        self.assertEqual(draft_studio.changed_slides(FEISHU_DRAFT, updated), ["P01", "P02"])


class ConfirmationDigestVersionTests(unittest.TestCase):
    def test_confirmations_recorded_before_intros_were_covered_still_match(self) -> None:
        old = draft_studio.page_digests(FEISHU_DRAFT, 1)
        self.assertNotEqual(old, draft_studio.page_digests(FEISHU_DRAFT))
        updated, _ = draft_studio.apply_edit(FEISHU_DRAFT, {"kind": "field", "slide": "P01", "key": "talk", "md": "改过的讲解方向。"})
        self.assertNotEqual(old["P01"], draft_studio.page_digests(updated, 1)["P01"])
        self.assertEqual(old["P02"], draft_studio.page_digests(updated, 1)["P02"])


class VisualReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        page = self.project / "deck" / "assembly-ready" / "pages" / "S01.png"
        page.parent.mkdir(parents=True)
        page.write_bytes(png())
        self.hash = hashlib.sha256(page.read_bytes()).hexdigest()
        write_json(self.project / "deck" / "assembly-ready" / "manifest.json",
                   {"pages": [{"slide_id": "S01", "ready_png_sha256": self.hash}]})
        write_json(self.project / "reviews" / "visual" / "LAYOUT-CHECK.json", {"pages": {"S01": {"problems": []}}})
        self.report = {"independent_agent": True, "review_agent_id": "agent-7", "status": "passed",
                       "layout_check_report": "reviews/visual/LAYOUT-CHECK.json",
                       "pages": [{"slide_id": "S01", "png_sha256": self.hash,
                                  "checks": {k: "ok" for k in vp.VISUAL_REVIEW_ITEMS}}]}
        self.state = {"visual_review": {"report_path": "reviews/visual/REVIEW.json", "independent_agent": True,
                                        "review_agent_id": "agent-7"}}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def errors(self) -> list[str]:
        write_json(self.project / "reviews" / "visual" / "REVIEW.json", self.report)
        return vp.validate_visual_review(self.project, self.state)

    def test_complete_independent_review_passes(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_self_review_changed_page_missing_items_and_open_layout_problems_fail(self) -> None:
        self.report["independent_agent"] = False
        self.report["pages"][0]["png_sha256"] = "0" * 64
        del self.report["pages"][0]["checks"]["orphans"]
        write_json(self.project / "reviews" / "visual" / "LAYOUT-CHECK.json", {"pages": {"S01": {"problems": ["孤字尾行"]}}})
        joined = "\n".join(self.errors())
        for needle in ("independent review agent", "changed after the review", "orphans", "1 problem"):
            self.assertIn(needle, joined)


class DesignReviewStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.png = self.project / "deck" / "review" / "full" / "S01.png"
        self.png.parent.mkdir(parents=True)
        self.png.write_bytes(png())
        write_json(self.project / "deck" / "review" / "full" / "review-manifest.json", {
            "created_at": "2026-10-26T10:00:00Z",
            "pages": [{"slide_id": "S01", "png_path": "deck/review/full/S01.png",
                       "text_boxes": [{"text": "香气是复购理由", "selector": "h1.title", "x": 160, "y": 200, "w": 800, "h": 120},
                                      {"text": "来源：Google Trends", "selector": "p.source", "x": 160, "y": 980, "w": 400, "h": 30}]}],
        })
        self.store = design_review.DesignCommentStore(self.project)
        self.crop = "data:image/png;base64," + base64.b64encode(png(8, 8)).decode()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_comment_records_box_anchor_crop_and_page_hash(self) -> None:
        thread = self.store.create({"slide": "S01", "rect": {"x": 150, "y": 190, "w": 500, "h": 100},
                                    "text": "标题和正文左缘没对齐", "crop": self.crop})
        self.assertEqual(thread["id"], "D-0001")
        self.assertEqual(thread["anchor"]["text"], "香气是复购理由")
        self.assertEqual(thread["png_sha256"], hashlib.sha256(self.png.read_bytes()).hexdigest())
        self.assertTrue((self.project / thread["crop_path"]).read_bytes().startswith(b"\x89PNG"))
        self.assertFalse(self.store.threads()[0]["stale"])

    def test_rerendered_page_marks_the_comment_stale(self) -> None:
        self.store.create({"slide": "S01", "rect": {"x": 0, "y": 0, "w": 100, "h": 100}, "text": "x"})
        self.png.write_bytes(png(shade=90))
        self.assertTrue(self.store.threads()[0]["stale"])

    def test_bad_input_is_rejected(self) -> None:
        for payload in ({"slide": "S99", "rect": {"x": 0, "y": 0, "w": 50, "h": 50}, "text": "x"},
                        {"slide": "S01", "rect": {"x": 0, "y": 0, "w": 2, "h": 2}, "text": "x"},
                        {"slide": "S01", "rect": {"x": 0, "y": 0, "w": 50, "h": 50}, "text": "  "},
                        {"slide": "S01", "rect": {"x": 0, "y": 0, "w": 50, "h": 50}, "text": "x", "crop": "data:text/html;base64,PGI+"},
                        {"slide": "S01", "rect": {"x": 0, "y": 0, "w": 50, "h": 50}, "text": "x", "png_sha256": "old"}):
            with self.assertRaises(design_review.ReviewError):
                self.store.create(payload)

    def test_open_comments_block_the_page_until_resolved(self) -> None:
        thread = self.store.create({"slide": "S01", "rect": {"x": 0, "y": 0, "w": 100, "h": 100}, "text": "数字压在纹理上"})
        self.store.reply(thread["id"], "已移到干净区域", "Agent")
        self.assertEqual([t["id"] for t in design_review.open_threads(self.project, "S01")], ["D-0001"])
        self.store.set_status(thread["id"], "resolved", "Owner")
        self.assertEqual(design_review.open_threads(self.project, "S01"), [])


class DesignReviewServerTests(StudioServerCase):
    def setUp(self) -> None:
        super().setUp()
        page = self.project / "deck" / "review" / "full" / "S01.png"
        page.parent.mkdir(parents=True)
        page.write_bytes(png())
        write_json(self.project / "deck" / "review" / "full" / "review-manifest.json",
                   {"pages": [{"slide_id": "S01", "png_path": "deck/review/full/S01.png"}]})
        (self.project / "secret.png").write_bytes(png())

    def test_design_api_lists_pages_and_takes_comments(self) -> None:
        self.assertEqual(self.request("/api/design", token=None)[0], 403)
        status, data = self.request("/api/design")
        self.assertEqual((status, [p["slide_id"] for p in data["pages"]]), (200, ["S01"]))
        status, data = self.request("/api/design/comments", {"slide": "S01", "rect": {"x": 10, "y": 10, "w": 300, "h": 200}, "text": "字太小"})
        self.assertEqual((status, data["thread"]["id"]), (200, "D-0001"))
        self.assertEqual(self.request("/api/design/comments", {"slide": "S01", "text": "x"}, token=None)[0], 403)

    def test_only_review_pngs_are_served(self) -> None:
        import urllib.error
        import urllib.request
        ok = urllib.request.urlopen(f"{self.base}/files/deck/review/full/S01.png?token={self.token}", timeout=5)
        self.assertEqual(ok.headers["Content-Type"], "image/png")
        ok.close()
        for path in ("secret.png", "deck/review/../../secret.png", "deck/review/full/review-manifest.json"):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(f"{self.base}/files/{path}?token={self.token}", timeout=5)
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()


if __name__ == "__main__":
    unittest.main()
