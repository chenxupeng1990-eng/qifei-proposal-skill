from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V2CanvasContractTests(unittest.TestCase):
    def test_loader_accepts_v2_canvas_and_slide_id(self) -> None:
        text = (ROOT / "assets/browser-editor/src/loader.js").read_text(encoding="utf-8")
        self.assertIn(".slide, .slide-canvas", text)
        self.assertIn("slide.dataset.slideId", text)

    def test_multi_editor_accepts_v2_canvas_and_slide_id(self) -> None:
        text = (ROOT / "assets/browser-editor/src/multi-editor.js").read_text(encoding="utf-8")
        self.assertIn(".slide, .slide-canvas", text)
        self.assertIn("slide.dataset.slideId", text)


if __name__ == "__main__":
    unittest.main()
