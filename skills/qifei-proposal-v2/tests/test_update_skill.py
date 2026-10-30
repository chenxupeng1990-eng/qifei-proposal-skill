"""The Skill tells the user about a newer release in plain words, at most once a day, and stays silent offline."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import update_skill  # noqa: E402

RELEASE = {"version": "9.9.9", "summary": ["页面可以逐页确认", "评论可以删除"], "zipball_url": None, "html_url": None}


class UpdateCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"QIFEI_HOME": self.tmp.name, "QIFEI_UPDATE_CHECK": ""}
        self.saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.calls = 0

    def tearDown(self) -> None:
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def fetch(self):
        self.calls += 1
        return RELEASE

    def test_newer_release_is_announced_once_a_day(self) -> None:
        first = update_skill.check("2026-10-30", self.fetch)
        self.assertTrue(first["newer"] and first["notify"])
        self.assertIn("9.9.9", first["message"])
        self.assertIn("更新提案 skill", first["message"])
        again = update_skill.check("2026-10-30", self.fetch)
        self.assertFalse(again["notify"])
        self.assertEqual(self.calls, 1)  # looked online once that day
        self.assertTrue(update_skill.check("2026-10-31", self.fetch)["notify"])

    def test_offline_or_switched_off_stays_silent(self) -> None:
        self.assertIsNone(update_skill.check("2026-10-30", lambda: None)["message"])
        update_skill.set_check_enabled(False)
        result = update_skill.check("2026-10-30", self.fetch)
        self.assertEqual((result["enabled"], result["message"], self.calls), (False, None, 0))
        self.assertEqual(json.loads(update_skill.settings_path().read_text())["update_check"], False)

    def test_release_summary_uses_the_release_text(self) -> None:
        body = "提案记忆可以全局关闭。\n\n*English line*\n\n## 改动\n- `off` / `on` 开关\n- 关闭后不读不写\n- 第三条\n- 第四条\n"
        self.assertEqual(update_skill.release_summary(body), ["提案记忆可以全局关闭"])
        self.assertEqual(update_skill.release_summary("## 改动\n- 只有列表\n"), [])


if __name__ == "__main__":
    unittest.main()
