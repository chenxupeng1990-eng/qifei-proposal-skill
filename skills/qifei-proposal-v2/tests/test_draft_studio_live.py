from __future__ import annotations

import json
import re
import shutil
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
from test_draft_studio import CHAPTER_FILE, FEISHU_DRAFT, write_project  # noqa: E402


def field(model: dict, slide_id: str, key: str) -> dict:
    slide = draft_studio.find_slide(model, slide_id)
    return next(f for f in slide["fields"] if f["key"] == key)


class ApplyEditTests(unittest.TestCase):
    def test_field_edit_touches_only_that_field(self) -> None:
        updated, slide = draft_studio.apply_edit(
            FEISHU_DRAFT, {"kind": "field", "slide": "P01", "key": "talk", "md": "先讲合作意图，再讲选择标准。"}
        )
        self.assertEqual(slide, "P01")
        before, after = FEISHU_DRAFT.split("\n"), updated.split("\n")
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(len(before), len(after))
        self.assertEqual(len(changed), 1)
        self.assertEqual(field(draft_studio.parse_draft(updated), "P01", "talk")["md"], "先讲合作意图，再讲选择标准。")

    def test_multiline_edit_keeps_neighbouring_headings_intact(self) -> None:
        updated, _ = draft_studio.apply_edit(
            FEISHU_DRAFT, {"kind": "field", "slide": "P01", "key": "logic", "md": "第一行\n\n第二行 → 第三行"}
        )
        model = draft_studio.parse_draft(updated)
        self.assertEqual(field(model, "P01", "logic")["md"], "第一行\n\n第二行 → 第三行")
        self.assertEqual(field(model, "P01", "screen")["md"], field(draft_studio.parse_draft(FEISHU_DRAFT), "P01", "screen")["md"])

    def test_title_edit_keeps_heading_prefix(self) -> None:
        updated, _ = draft_studio.apply_edit(FEISHU_DRAFT, {"kind": "title", "slide": "P02", "md": "新的结论式标题"})
        self.assertIn("## P02｜新的结论式标题\n", updated)

    def test_chapter_file_page_is_edited_as_source(self) -> None:
        model = draft_studio.parse_draft(CHAPTER_FILE)
        slide = draft_studio.find_slide(model, "P09")
        self.assertIn("body_md", slide)
        self.assertNotIn("span", slide["fields"][0])
        with self.assertRaises(draft_studio.EditError):
            draft_studio.apply_edit(CHAPTER_FILE, {"kind": "field", "slide": "P09", "key": "core", "md": "x"})
        updated, _ = draft_studio.apply_edit(CHAPTER_FILE, {"kind": "body", "slide": "P09", "md": "- 核心内容：改写后的判断。"})
        self.assertIn("- 核心内容：改写后的判断。", updated)
        self.assertIn("### [P08] 品牌锚点是香气生活方式", updated)

    def test_intro_edit(self) -> None:
        updated, slide = draft_studio.apply_edit(FEISHU_DRAFT, {"kind": "intro", "chapter": "ch01", "md": "**本章回答：** 新的问题。"})
        self.assertIsNone(slide)
        self.assertEqual(draft_studio.parse_draft(updated)["chapters"][0]["intro_md"], "**本章回答：** 新的问题。")

    def test_unknown_targets_are_rejected(self) -> None:
        with self.assertRaises(draft_studio.EditError):
            draft_studio.apply_edit(FEISHU_DRAFT, {"kind": "field", "slide": "P99", "key": "talk", "md": "x"})
        with self.assertRaises(draft_studio.EditError):
            draft_studio.apply_edit(FEISHU_DRAFT, {"kind": "title", "slide": "P01", "md": "   "})


class DraftStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = write_project(Path(self.tmp.name), FEISHU_DRAFT, {
            "proposal_draft": {"authority": "local", "revision_id": 7, "verified_slide_ids": []},
            "chapters": [{"chapter_id": "CH00", "slides": ["P01", "P02"], "manuscript_confirmed": True}],
        })
        path, state = draft_studio.load_project(self.project, None)
        self.store = draft_studio.DraftStore(self.project, path, state)
        self.store.ensure_baseline()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_writes_draft_revision_hash_and_snapshot(self) -> None:
        base = self.store.model()["meta"]["sha256"]
        entry = self.store.save({"kind": "field", "slide": "P01", "key": "talk", "md": "新讲法"}, base)
        self.assertEqual(entry["revision"], 8)
        text = self.store.read()
        self.assertIn("新讲法", text)
        self.assertEqual(entry["sha256"], draft_studio.sha256_text(text))
        self.assertEqual((self.store.revisions_dir / "rev-000008.md").read_text(encoding="utf-8"), text)
        self.assertEqual([e["revision"] for e in self.store.entries()], [7, 8])

    def test_confirmed_page_becomes_modified_after_edit(self) -> None:
        base = self.store.model()["meta"]["sha256"]
        self.store.save({"kind": "title", "slide": "P01", "md": "改过的封面标题"}, base)
        statuses = {s["id"]: s["status"] for c in self.store.model()["chapters"] for s in c["slides"]}
        self.assertEqual(statuses["P01"], "modified")
        self.assertEqual(statuses["P02"], "confirmed")

    def test_stale_base_is_a_conflict(self) -> None:
        base = self.store.model()["meta"]["sha256"]
        self.store.save({"kind": "field", "slide": "P01", "key": "talk", "md": "第一次"}, base)
        with self.assertRaises(draft_studio.EditConflict):
            self.store.save({"kind": "field", "slide": "P01", "key": "talk", "md": "第二次"}, base)

    def test_outside_change_is_recorded_once_with_touched_pages(self) -> None:
        self.store.draft_path.write_text(FEISHU_DRAFT.replace("内容即货架。", "内容就是货架。"), encoding="utf-8")
        entry = self.store.sync_external()
        self.assertEqual((entry["actor"], entry["revision"], entry["slides"]), ("external", 8, ["P03"]))
        self.assertIsNone(self.store.sync_external())

    def test_edit_cannot_add_or_remove_pages(self) -> None:
        base = self.store.model()["meta"]["sha256"]
        before = self.store.read()
        with self.assertRaises(draft_studio.EditError):
            self.store.save({"kind": "field", "slide": "P01", "key": "talk", "md": "讲法\n\n## P99｜偷偷加的一页"}, base)
        self.assertEqual(self.store.read(), before)
        self.assertEqual(len(self.store.entries()), 1)

    def test_unchanged_save_records_nothing(self) -> None:
        model = self.store.model()
        original = field(model, "P01", "talk")
        entry = self.store.save(
            {"kind": "field", "slide": "P01", "key": "talk", "md": original.get("raw", original["md"])},
            model["meta"]["sha256"],
        )
        self.assertTrue(entry.get("unchanged"))
        self.assertEqual(len(self.store.entries()), 1)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class StudioServerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = write_project(Path(self.tmp.name), FEISHU_DRAFT, None)
        self.port = free_port()
        self.process = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "draft_studio.py"), "serve", str(self.project), "--port", str(self.port)],
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
        self.draft = self.project / "content" / "draft" / "proposal-draft.md"

    def tearDown(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()
        self.tmp.cleanup()

    def request(self, path: str, body: dict | None = None, token: str | None = "default", host: str | None = None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Studio-Token"] = self.token if token == "default" else token
        if host:
            headers["Host"] = host
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read().decode("utf-8"))



class StudioServerTests(StudioServerCase):
    def test_api_requires_token_and_local_host(self) -> None:
        self.assertEqual(self.request("/api/model", token=None)[0], 403)
        self.assertEqual(self.request("/api/model", token="wrong")[0], 403)
        self.assertEqual(self.request("/api/model", host="attacker.example")[0], 403)
        self.assertEqual(self.request("/api/save", {"target": {}, "base_sha": ""}, token=None)[0], 403)

    def test_save_round_trip_and_conflict(self) -> None:
        status, model = self.request("/api/model")
        self.assertEqual(status, 200)
        target = {"kind": "field", "slide": "P03", "key": "core", "md": "内容就是货架。"}
        status, saved = self.request("/api/save", {"target": target, "base_sha": model["meta"]["sha256"]})
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["entry"]["slides"], ["P03"])
        self.assertIn("内容就是货架。", self.draft.read_text(encoding="utf-8"))
        status, conflict = self.request("/api/save", {"target": target, "base_sha": model["meta"]["sha256"]})
        self.assertEqual(status, 409)
        self.assertEqual(conflict["model"]["meta"]["sha256"], saved["entry"]["sha256"])
        self.assertEqual(self.request("/api/save", {"target": {"kind": "nope"}, "base_sha": saved["entry"]["sha256"]})[0], 400)

    def test_events_push_outside_changes(self) -> None:
        req = urllib.request.Request(f"{self.base}/api/events?token={self.token}")
        stream = urllib.request.urlopen(req, timeout=10)
        self.assertEqual(stream.readline().strip(), b": connected")
        self.draft.write_text(FEISHU_DRAFT.replace("渠道已经全域化。", "渠道已经全面全域化。"), encoding="utf-8")
        payload = None
        deadline = time.time() + 8
        while time.time() < deadline:
            line = stream.readline().decode("utf-8").strip()
            if line.startswith("data:"):
                payload = json.loads(line[5:])
                break
        stream.close()
        self.assertIsNotNone(payload)
        self.assertEqual((payload["actor"], payload["slides"]), ("external", ["P02"]))


class CommentStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = draft_studio.CommentStore(Path(self.tmp.name) / "proposal-draft.md")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_thread_lifecycle(self) -> None:
        thread = self.store.create({"slide": "P01", "field": "P01:core", "quote": "长期经营", "prefix": "要承担的是", "suffix": "，而不是", "text": "再具体一点", "author": "总悟"}, 3)
        self.assertEqual((thread["id"], thread["status"], thread["draft_revision"]), ("C-0001", "open", 3))
        self.store.reply("C-0001", "已补充三年目标", "Agent")
        self.store.set_status("C-0001", "resolved", "总悟")
        saved = self.store.load()["threads"][0]
        self.assertEqual([m["author"] for m in saved["messages"]], ["总悟", "Agent"])
        self.assertEqual((saved["status"], saved["status_by"]), ("resolved", "总悟"))
        self.assertEqual(self.store.create({"slide": "P02", "field": "P02:core", "quote": "x", "text": "y"}, 3)["id"], "C-0002")

    def test_invalid_input_is_rejected(self) -> None:
        with self.assertRaises(draft_studio.EditError):
            self.store.create({"slide": "P01", "field": "P01:core", "quote": "", "text": "y"}, 1)
        with self.assertRaises(draft_studio.EditError):
            self.store.reply("C-9999", "x", "Agent")
        with self.assertRaises(draft_studio.EditError):
            self.store.set_status("C-0001", "deleted", "x")

    def test_full_export_keeps_decisions_brief_does_not(self) -> None:
        self.store.create({"slide": "P01", "field": "P01:core", "quote": "长期经营", "text": "这是证明还是方向？"}, 1)
        self.store.reply("C-0001", "已改成证据", "Agent")
        self.store.set_status("C-0001", "resolved", "总悟")
        model = draft_studio.parse_draft(FEISHU_DRAFT)
        threads = self.store.load()["threads"]
        full = draft_studio.export_markdown(model, "full", threads)
        record = full.split("#### 评审记录", 1)[1].split("###", 1)[0]
        self.assertIn("C-0001｜已决定", record)
        self.assertIn("Agent", record)
        self.assertIn("决定：总悟", record)
        self.assertNotIn("评审记录", draft_studio.export_markdown(model, "brief", threads))

    def test_field_labels_for_cli(self) -> None:
        self.assertEqual(draft_studio.field_label("P09:core"), "核心内容")
        self.assertEqual(draft_studio.field_label("title:P09"), "标题")
        self.assertEqual(draft_studio.field_label("intro:ch01"), "章节说明")


class CommentApiTests(StudioServerCase):
    def test_comment_api_and_live_event(self) -> None:
        stream = urllib.request.urlopen(urllib.request.Request(f"{self.base}/api/events?token={self.token}"), timeout=10)
        self.assertEqual(stream.readline().strip(), b": connected")
        status, created = self.request("/api/comments", {"slide": "P03", "field": "P03:core", "quote": "内容即货架", "text": "改成更口语"})
        self.assertEqual(status, 200, created)
        self.assertEqual(created["thread"]["draft_revision"], 0)
        subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "reply", str(self.project), "C-0001", "已改"], check=True, capture_output=True)
        events = []
        deadline = time.time() + 8
        while time.time() < deadline and len(events) < 2:
            line = stream.readline().decode("utf-8").strip()
            if line.startswith("event:"):
                events.append(line)
        stream.close()
        self.assertEqual(events, ["event: comments", "event: comments"])
        status, data = self.request("/api/comments")
        self.assertEqual([m["text"] for m in data["threads"][0]["messages"]], ["改成更口语", "已改"])
        self.assertEqual(self.request("/api/comments/status", {"id": "C-0001", "status": "resolved"})[0], 200)
        self.assertEqual(self.request("/api/comments/reply", {"id": "C-0404", "text": "x"})[0], 400)
        self.assertEqual(self.request("/api/comments", {"quote": "x", "text": "y"}, token=None)[0], 403)
        listed = subprocess.run([sys.executable, str(SCRIPTS / "draft_studio.py"), "comments", str(self.project)], capture_output=True, text=True, check=True)
        self.assertIn("No open comment threads.", listed.stdout)


@unittest.skipUnless(
    shutil.which("node") and (SKILL_ROOT / "node_modules" / "playwright-core").is_dir(),
    "node runtime dependencies are not installed",
)
class StudioBrowserTests(StudioServerCase):
    def test_edit_in_page_and_receive_outside_change(self) -> None:
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("draft-studio-live.e2e.mjs")), self.base + "/", str(self.draft), "P01", "talk", "P02"],
            cwd=SKILL_ROOT, capture_output=True, text=True, check=False, timeout=60,
        )
        if result.returncode == 3:
            self.skipTest("no Chromium-based browser available")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["saved_in_file"] and report["saved_in_page"] and report["outside_change_rendered"])
        self.assertEqual(report["script_errors"], [])

    def test_select_text_comment_reply_and_resolve(self) -> None:
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("draft-studio-comments.e2e.mjs")), self.base + "/", str(self.project), "P01", "core", "长期经营"],
            cwd=SKILL_ROOT, capture_output=True, text=True, check=False, timeout=60,
        )
        if result.returncode == 3:
            self.skipTest("no Chromium-based browser available")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["highlight_text"], "长期经营")
        self.assertTrue(report["card_aligned"])
        self.assertTrue(report["agent_reply_shown"])
        self.assertEqual(report["status_in_file"], "resolved")
        self.assertTrue(report["decision_kept_visible"])
        self.assertEqual(report["decision_badge"].strip(), "1")
        self.assertEqual(report["messages_in_file"], ["Owner", "Agent"])
        self.assertEqual(report["script_errors"], [])


if __name__ == "__main__":
    unittest.main()
