from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_identity import build_id, canonical_build_material  # noqa: E402


class BuildIdentityTests(unittest.TestCase):
    def assert_cross_language(self, payload: dict, expected_material: str) -> None:
        python_material = canonical_build_material(
            payload["inputs"],
            payload["runtime"],
            payload.get("chapter_id"),
        )
        self.assertEqual(python_material, expected_material)
        expected_id = hashlib.sha256(expected_material.encode("utf-8")).hexdigest()[:16]
        self.assertEqual(
            build_id(payload["inputs"], payload["runtime"], payload.get("chapter_id")),
            expected_id,
        )
        result = subprocess.run(
            [
                "node",
                str(SCRIPTS / "build_identity.mjs"),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        javascript = json.loads(result.stdout)
        self.assertEqual(javascript["material"], expected_material)
        self.assertEqual(javascript["build_id"], expected_id)

    def test_full_build_uses_explicit_null_chapter(self) -> None:
        self.assert_cross_language(
            {
                "inputs": {"assets/hero.png": "aaa", "deck/deck-spec.json": "bbb"},
                "runtime": {"skill:scripts/render_deck.py": "ccc"},
                "chapter_id": None,
            },
            '{"chapter_id":null,"inputs":{"assets/hero.png":"aaa","deck/deck-spec.json":"bbb"},"runtime":{"skill:scripts/render_deck.py":"ccc"}}',
        )

    def test_chinese_paths_are_utf8_not_ascii_escaped(self) -> None:
        self.assert_cross_language(
            {
                "inputs": {"素材/产品主图.png": "甲", "内容/第一章.md": "乙"},
                "runtime": {"skill:脚本/render.py": "丙"},
                "chapter_id": "第一章",
            },
            '{"chapter_id":"第一章","inputs":{"内容/第一章.md":"乙","素材/产品主图.png":"甲"},"runtime":{"skill:脚本/render.py":"丙"}}',
        )

    def test_chapter_build_differs_from_full_build(self) -> None:
        inputs = {"deck/deck-spec.json": "aaa"}
        runtime = {"skill:scripts/render_deck.py": "bbb"}
        self.assertNotEqual(build_id(inputs, runtime, None), build_id(inputs, runtime, "C01"))

    def test_input_change_invalidates_old_build(self) -> None:
        runtime = {"skill:scripts/render_deck.py": "bbb"}
        original = build_id({"素材.png": "old"}, runtime, None)
        changed = build_id({"素材.png": "new"}, runtime, None)
        self.assertNotEqual(original, changed)


if __name__ == "__main__":
    unittest.main()
