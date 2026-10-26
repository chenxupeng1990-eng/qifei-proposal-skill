#!/usr/bin/env python3
"""Check that on-screen text matches the frozen draft's "PPT上屏内容", line by line.

Missing lines and extra lines are both errors. Fixed design elements (wordmark text,
English eyebrow, page numbers) go in design-tokens.json `screen_text_whitelist`.
Used before a page enters the assembly-ready library and again after export.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import draft_studio  # noqa: E402

IGNORED = re.compile(r"[\s\*\-—–|｜•·:：，,。.;；、“”\"'‘’（）()【】\[\]→←↓↑□■①②③④⑤⑥⑦⑧⑨_+%/]+")
BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "section", "span", "br", "dt", "dd", "figcaption"}
SKIP_TAGS = {"script", "style", "title", "head", "template", "noscript"}


def norm(text: str) -> str:
    return IGNORED.sub("", text)


def draft_screen(project: Path) -> dict[str, dict]:
    draft_path, _ = draft_studio.load_project(project, None)
    model = draft_studio.parse_draft(draft_path.read_text(encoding="utf-8"))
    pages = {}
    for chapter in model["chapters"]:
        for slide in chapter["slides"]:
            screen = next((f["md"] for f in slide["fields"] if f["key"] == "screen"), "")
            lines = [line for line in screen.split("\n") if norm(line)]
            pages[slide["id"]] = {"slide_id": slide["id"], "title": slide["title"], "lines": lines}
    return pages


def whitelist(project: Path) -> set[str]:
    tokens = project / "deck" / "design-tokens.json"
    items = []
    if tokens.is_file():
        items = json.loads(tokens.read_text(encoding="utf-8")).get("screen_text_whitelist") or []
    return {norm(str(item)) for item in items if norm(str(item))}


class SlideText(HTMLParser):
    """Text chunks per `data-slide-id` ancestor (or one bucket when the file is a single page)."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, str | None, bool]] = []
        self.chunks: dict[str, list[str]] = {}
        self.current: list[str] = []

    def _slide(self) -> str:
        for _, slide, _ in reversed(self.stack):
            if slide:
                return slide
        return ""

    def _hidden(self) -> bool:
        return any(skip for _, _, skip in self.stack)

    def _flush(self) -> None:
        text = "".join(self.current).strip()
        if text:
            self.chunks.setdefault(self._slide(), []).append(text)
        self.current = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in BLOCK_TAGS:
            self._flush()
        hidden = tag in SKIP_TAGS or "data-screen-ignore" in attrs or attrs.get("aria-hidden") == "true"
        if tag in {"br", "img", "meta", "link", "input", "hr"}:
            return
        self.stack.append((tag, attrs.get("data-slide-id"), hidden))

    def handle_endtag(self, tag):
        if tag in BLOCK_TAGS:
            self._flush()
        while self.stack:
            open_tag, _, _ = self.stack.pop()
            if open_tag == tag:
                break

    def handle_data(self, data):
        if not self._hidden():
            self.current.append(data)

    def close(self):
        super().close()
        self._flush()


def html_chunks(path: Path) -> dict[str, list[str]]:
    parser = SlideText()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser.chunks


def pptx_chunks(path: Path) -> list[list[str]]:
    slides = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            (n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)),
        )
        for name in names:
            xml = archive.read(name).decode("utf-8")
            slides.append([re.sub(r"<[^>]+>", "", p) for p in re.findall(r"<a:p>.*?</a:p>", xml, re.S)])
    return slides


def compare(expected: dict, chunks: list[str], allowed: set[str]) -> dict[str, list[str]]:
    shown = norm("".join(chunks))
    missing = [line.strip() for line in expected["lines"] if norm(line) not in shown and norm(line) not in allowed]
    draft_all = norm(expected["title"] + "".join(expected["lines"]))
    extra = []
    for chunk in chunks:
        n = re.sub(r"^\d{1,2}(?=\D)", "", norm(chunk))  # list ordinals such as "04 · 反馈" are layout, not copy
        if n and n not in draft_all and n not in allowed and not n.isdigit() and n != norm(expected.get("slide_id", "")):
            extra.append(chunk.strip()[:80])
    return {"missing": missing, "extra": extra}


def check_html(project: Path, html: Path, slide_ids: list[str] | None = None) -> dict[str, dict]:
    pages = draft_screen(project)
    allowed = whitelist(project)
    chunks = html_chunks(html)
    results = {}
    targets = slide_ids or [s for s in chunks if s] or []
    for slide_id in targets:
        if slide_id not in pages:
            results[slide_id] = {"missing": [], "extra": [], "error": "slide not in draft"}
            continue
        page_chunks = chunks.get(slide_id) or (chunks.get("") if len(targets) == 1 else [])
        results[slide_id] = compare(pages[slide_id], page_chunks or [], allowed)
    return results


def check_pptx(project: Path, pptx: Path, slide_order: list[str]) -> dict[str, dict]:
    pages = draft_screen(project)
    allowed = whitelist(project)
    slides = pptx_chunks(pptx)
    results = {}
    if len(slides) != len(slide_order):
        results["_deck"] = {"missing": [], "extra": [], "error": f"PPTX has {len(slides)} slides, final order has {len(slide_order)}"}
    for slide_id, chunks in zip(slide_order, slides):
        if slide_id in pages:
            results[slide_id] = compare(pages[slide_id], chunks, allowed)
    return results


def failures(results: dict[str, dict]) -> list[str]:
    out = []
    for slide_id, result in results.items():
        if result.get("error"):
            out.append(f"{slide_id}: {result['error']}")
        for line in result.get("missing", []):
            out.append(f"{slide_id}: 缺少母稿上屏文字「{line}」")
        for line in result.get("extra", []):
            out.append(f"{slide_id}: 多出母稿没有的文字「{line}」")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--html", help="page or review HTML, project-relative or absolute")
    group.add_argument("--pptx")
    parser.add_argument("--slide-id", action="append", help="slides to check (HTML)")
    parser.add_argument("--order", help="comma-separated final slide order (PPTX); default deck-spec order")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    if args.html:
        path = Path(args.html) if Path(args.html).is_absolute() else project / args.html
        results = check_html(project, path, args.slide_id)
    else:
        path = Path(args.pptx) if Path(args.pptx).is_absolute() else project / args.pptx
        order = args.order.split(",") if args.order else [
            s["slide_id"] for s in json.loads((project / "deck" / "deck-spec.json").read_text(encoding="utf-8"))["slides"]
        ]
        results = check_pptx(project, path, order)
    problems = failures(results)
    for problem in problems:
        print(f"ERROR {problem}")
    print(f"{'FAIL' if problems else 'PASS'}: {len(results)} slide(s) checked against the frozen draft")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
