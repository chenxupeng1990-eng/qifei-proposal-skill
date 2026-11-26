from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional on minimal Windows Python before bootstrap
    Image = None  # type: ignore[assignment]


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from unittest.mock import patch

from build_presenter_html import analyze_motion_pacing, build_html, collect_slides, encode_image_data_uri  # noqa: E402
from validate_project import validate_project  # noqa: E402


class PresenterHtmlAndMotionTests(unittest.TestCase):
    def test_phase08_routes_to_presenter_motion_reference(self) -> None:
        ref_path = SKILL_ROOT / "references" / "presenter-html-and-motion.md"
        self.assertTrue(ref_path.is_file())
        ref_text = ref_path.read_text(encoding="utf-8")
        for key in (
            "双屏投屏演讲者模式",
            "基础配置",
            "增强配置",
            "≥ 20 页连续无动效",
            "色盘锁死设计系统",
            "visibility: hidden",
            "build_presenter_html.py",
        ):
            self.assertIn(key, ref_text)

        p08 = (SKILL_ROOT / "phase-packs" / "08-speaker-export.md").read_text(encoding="utf-8")
        self.assertIn("presenter-html-and-motion.md", p08)
        self.assertIn("build_presenter_html.py", p08)

    def test_project_state_schema_accepts_presenter_html_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            res = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_project.py"),
                    "--project",
                    str(project),
                    "--name",
                    "Presenter Fixture",
                    "--owner",
                    "Owner",
                    "--project-id",
                    "presenter-001",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            state_path = project / "project-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["presenter_html"] = {
                "enabled": True,
                "languages": ["zh", "en"],
                "notes_editable": True,
                "dual_screen": True,
                "motion_tier": "enhanced",
                "motion_plan_path": "exports/motion-plan.json",
                "motion_plan_approved": True,
                "max_static_run": 11,
                "output_path": "exports/Presenter_Offline.html",
            }
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertEqual(validate_project(project), [])

    def test_motion_pacing_guardrail_flags_20_consecutive_static_slides(self) -> None:
        ids = [f"P{i:02d}" for i in range(1, 31)]
        # Gap P02..P22 = 21 consecutive static slides -> FAIL_PACING_GAP
        plan_fail = {"slides": [{"slide_id": "P01", "tier": "basic"}, {"slide_id": "P23", "tier": "B"}, {"slide_id": "P30", "tier": "basic"}]}
        rep_fail = analyze_motion_pacing(ids, plan_fail)
        self.assertEqual(rep_fail["status"], "FAIL_PACING_GAP")
        self.assertEqual(rep_fail["max_static_run"], 21)

        # Insert A-tier at P12 -> max gap is 10 -> PASS
        plan_pass = {
            "slides": [
                {"slide_id": "P01", "tier": "basic"},
                {"slide_id": "P12", "tier": "A"},
                {"slide_id": "P23", "tier": "B"},
                {"slide_id": "P30", "tier": "basic"},
            ]
        }
        rep_pass = analyze_motion_pacing(ids, plan_pass)
        self.assertEqual(rep_pass["status"], "PASS")
        self.assertEqual(rep_pass["max_static_run"], 10)

    @unittest.skipIf(Image is None, "Pillow not installed; run scripts/bootstrap.py")
    def test_build_presenter_html_supports_single_and_bilingual_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = root / "P01.png"
            p2 = root / "P02.png"
            Image.new("RGB", (160, 90), (244, 243, 239)).save(p1)
            Image.new("RGB", (160, 90), (47, 58, 52)).save(p2)
            manifest = [
                {"slide_id": "P01", "ch_id": "CH01", "ch_zh": "导言", "ch_en": "Intro", "title_zh": "封面", "title_en": "Cover", "img_zh": str(p1), "img_en": str(p1), "note_zh": "开场讲稿", "note_en": "Opening script"},
                {"slide_id": "P02", "ch_id": "CH01", "ch_zh": "导言", "ch_en": "Intro", "title_zh": "结论", "title_en": "Conclusion", "img_zh": str(p2), "img_en": str(p2), "note_zh": "第二页讲稿", "note_en": "Second script"},
            ]
            # Single-language read-only notes
            zh_slides = collect_slides(manifest, ["zh"])
            zh_html = build_html(
                brand_name="TEST BRAND",
                subtitle="Demo Deck",
                chapters=[["CH01", "导言", "Intro", 1, 2]],
                slides=zh_slides,
                langs=["zh"],
                editable_notes=False,
            )
            self.assertIn("双屏演示", zh_html)
            self.assertNotIn('data-lang="en"', zh_html)
            self.assertNotIn('id="btn-edit"', zh_html)

            # Bilingual editable notes
            bi_slides = collect_slides(manifest, ["zh", "en"])
            bi_html = build_html(
                brand_name="TEST BRAND",
                subtitle="Bilingual Deck",
                chapters=[["CH01", "导言", "Intro", 1, 2]],
                slides=bi_slides,
                langs=["zh", "en"],
                editable_notes=True,
            )
            self.assertIn('data-lang="en"', bi_html)
            self.assertIn('id="btn-edit"', bi_html)
            self.assertIn("NEXT SLIDE", bi_html)
            self.assertIn("Microsoft YaHei", bi_html)
            self.assertIn("Segoe UI", bi_html)

    @unittest.skipIf(Image is None, "Pillow not installed; run scripts/bootstrap.py")
    def test_encode_image_falls_back_to_pillow_webp_without_cwebp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "slide.png"
            Image.new("RGB", (160, 90), (244, 243, 239)).save(p1)
            with patch("build_presenter_html.shutil.which", return_value=None):
                uri = encode_image_data_uri(p1)
            self.assertTrue(uri.startswith("data:image/webp;base64,"))


if __name__ == "__main__":
    unittest.main()
