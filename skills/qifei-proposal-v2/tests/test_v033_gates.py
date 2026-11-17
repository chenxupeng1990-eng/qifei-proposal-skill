"""v0.3.3 gates from a full-run review: calibration samples, Logo, type scale, generation records, doctor."""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QIFEI_MEMORY_HOME", tempfile.mkdtemp(prefix="qifei-memory-test-"))

from test_draft_format import page  # noqa: E402
from validate_design_loop import generation_record_errors  # noqa: E402
from validate_project import (  # noqa: E402
    calibration_sample_errors, logo_overlay_errors, production_check_column_errors, type_scale_and_logo_errors,
)

SCREEN = "标题：消费者愿意为结果买单\n- 功效：32%\n- 效果不明显：34%\n来源：示例调研机构"


def png(path: Path, alpha: bool) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    color = 6 if alpha else 2
    width = 4 if alpha else 3
    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, color, 0, 0, 0)
    raw = (b"\x00" + b"\x10" * width * 2) * 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class CalibrationSampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        draft = "# 市场\n\n" + page("P03", "消费者愿意为结果买单", {"PPT上屏内容": SCREEN})
        (self.root / "content" / "draft").mkdir(parents=True)
        (self.root / "content" / "draft" / "proposal-draft.md").write_text(draft, encoding="utf-8")
        (self.root / "project-state.json").write_text("{}", encoding="utf-8")
        self.cal = self.root / "deck" / "design-calibration.html"
        self.cal.parent.mkdir(parents=True)
        png(self.root / "assets" / "base.png", alpha=False)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def errors(self, html: str) -> list[str]:
        return calibration_sample_errors(self.root, self.cal, html)

    def test_clean_sample_passes(self) -> None:
        html = ('<section data-design-sample="data" data-sample-page="P03"><h1>消费者愿意为结果买单</h1>'
                '<p>功效</p><p>32%</p><p data-screen-ignore>评审说明</p></section>')
        self.assertEqual(self.errors(html), [])

    def test_sample_must_name_its_page(self) -> None:
        self.assertTrue(any("data-sample-page" in e for e in self.errors('<section data-design-sample="data"></section>')))

    def test_off_screen_copy_is_caught(self) -> None:
        html = '<section data-design-sample="data" data-sample-page="P03"><p>讲解时先强调消费者心理</p></section>'
        self.assertTrue(any("not in P03" in e for e in self.errors(html)))

    def test_two_samples_sharing_one_base(self) -> None:
        html = ('<section data-design-sample="cover" data-sample-page="P03"><img src="../assets/base.png"></section>'
                '<section data-design-sample="data" data-sample-page="P03" style="background:url(../assets/base.png)"></section>')
        self.assertTrue(any("same base image" in e for e in self.errors(html)))

    def test_shared_alpha_png_is_fine(self) -> None:
        png(self.root / "assets" / "product.png", alpha=True)
        html = ('<section data-design-sample="cover" data-sample-page="P03"><img src="../assets/product.png"></section>'
                '<section data-design-sample="data" data-sample-page="P03"><img src="../assets/product.png"></section>')
        self.assertEqual(self.errors(html), [])


class ProductionCheckColumnTests(unittest.TestCase):
    def test_columns_and_rows(self) -> None:
        table = ("| 样张 | 核心内容 | 表达载体 | 排版理由 |\n|---|---|---|---|\n"
                 "| cover | 品牌在中国的角色 | 人物 Hero | 人物占右，标题在留白 |\n| data | 选与不选的心理 | 情绪场景＋数据 | |\n")
        errors = production_check_column_errors(table, ("cover", "data", "toc"))
        self.assertTrue(any("data leaves 排版理由" in e for e in errors), errors)
        self.assertTrue(any("no row for sample toc" in e for e in errors), errors)
        self.assertFalse(any("cover" in e for e in errors), errors)

    def test_missing_table(self) -> None:
        self.assertTrue(production_check_column_errors("逐张检查过了。", ("cover",)))


class LogoAndTypeScaleTests(unittest.TestCase):
    def test_logo_needs_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            png(root / "inputs" / "brand-official" / "logo-white.png", alpha=False)
            png(root / "inputs" / "brand-official" / "logo.png", alpha=True)
            self.assertTrue(logo_overlay_errors(root, {"logo_overlay": "inputs/brand-official/logo-white.png"}))
            self.assertEqual(logo_overlay_errors(root, {"logo_overlay": "inputs/brand-official/logo.png"}), [])
            self.assertTrue(logo_overlay_errors(root, {}))
            self.assertEqual(logo_overlay_errors(root, {"logo_overlay_reason": "代理品牌，页面不放 Logo"}), [])

    def test_type_scale_and_logo_slot(self) -> None:
        brand = {"logo_overlay": "inputs/brand-official/logo.svg"}
        self.assertTrue(type_scale_and_logo_errors({}, brand))
        tokens = {
            "type_scale": {k: {"px": v} for k, v in {"title": 56, "subtitle": 32, "body": 26, "source": 16}.items()},
            "logo": {"file": "inputs/brand-official/logo.svg", "slot": {"x": 1680, "y": 48, "w": 180}},
        }
        self.assertEqual(type_scale_and_logo_errors(tokens, brand), [])


class GenerationRecordTests(unittest.TestCase):
    def test_products_need_official_reference_and_edits_are_capped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inputs" / "brand-official").mkdir(parents=True)
            (root / "inputs" / "brand-official" / "night-cream.png").write_bytes(b"x")
            (root / "assets").mkdir()
            (root / "assets" / "master.png").write_bytes(b"x")
            ok = {"references": ["inputs/brand-official/night-cream.png"], "products": ["夜间霜"], "edit_rounds": 1}
            self.assertEqual(generation_record_errors(root, ok, "P07"), [])
            no_ref = {"references": ["assets/master.png"], "products": ["夜间霜"], "edit_rounds": 0}
            self.assertTrue(any("official product" in e for e in generation_record_errors(root, no_ref, "P07")))
            foggy = {"references": [], "products": [], "edit_rounds": 4}
            self.assertTrue(any("regenerate" in e for e in generation_record_errors(root, foggy, "P03")))
            self.assertTrue(generation_record_errors(root, {}, "P01"))


class DoctorProjectMemoryTests(unittest.TestCase):
    def test_declared_abilities_stay_with_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "project-state.json").write_text('{"phase": "intake"}', encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if not k.startswith("PROPOSAL_")}
            env["QIFEI_RUNTIME_FILE"] = str(root / "runtime.json")
            doctor = [sys.executable, str(SCRIPTS / "doctor.py"), "--project", str(root)]
            subprocess.run([*doctor, "--image-provider", "codex_builtin", "--visual-understanding"],
                           env=env, check=True, capture_output=True)
            later = subprocess.run(doctor, env=env, check=True, capture_output=True, text=True).stdout
            self.assertIn("codex_builtin (declared earlier for this project)", later)
            self.assertNotIn("GAP image_generation", later)
            self.assertFalse((root / "runtime.json").exists())
            state = json.loads((root / "project-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["runtime"]["declared"]["image_provider"], "codex_builtin")



class RouteAndComponentTests(unittest.TestCase):
    def test_html_only_needs_owner_approval_per_page(self) -> None:
        from validate_design_loop import validate_presentation_route
        page = {"render_route": "html_only", "visual_mode": "none"}
        errors = validate_presentation_route(page, "P14", {})
        self.assertTrue(any("html_only needs route_exception" in e for e in errors))
        page["route_exception"] = {"record_id": "owner-P14-html", "reason": "九个 SKU 的数据表"}
        approvals = {"p14": {"approved": True, "record_id": "owner-P14-html"}}
        self.assertFalse(any("html_only" in e for e in validate_presentation_route(page, "P14", approvals)))
        page["visual_mode"] = "background"
        self.assertTrue(any("visual_mode must be none" in e for e in validate_presentation_route(page, "P14", approvals)))

    def test_components_follow_the_tokens(self) -> None:
        from build_components import build
        css = build({"type_scale": {"title": {"px": 56}, "body": {"px": 26, "line_height": 1.5}},
                     "logo": {"slot": {"x": 1680, "y": 48, "w": 180}}})
        self.assertIn("--q-title-size: 56px;", css)
        self.assertIn(".q-body {", css)
        self.assertIn(".q-logo { position: absolute; left: 1680px; top: 48px; width: 180px;", css)
        with self.assertRaises(ValueError):
            build({})


if __name__ == "__main__":
    unittest.main()
