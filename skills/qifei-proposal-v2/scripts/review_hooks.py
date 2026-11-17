#!/usr/bin/env python3
"""Wire the browser calibration editor into formal page HTML, and check that it is still wired.

The agent writes page content only. After every page rewrite run `inject`; before review PNGs or
assembly run `check`. A page that lost its hooks fails loudly instead of losing the editor silently.

usage:
  python3 scripts/review_hooks.py inject <project> <page.html>...
  python3 scripts/review_hooks.py check  <project> <page.html>...
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
EDITOR_SRC = SKILL_ROOT.parent / "ppt-html-calibration-editor" / "assets" / "browser-editor" / "src"
EDITOR_DIR = "deck/review-editor"
TEXT_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "figcaption", "blockquote"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
HOOK = "data-review-hook"


class Scan(HTMLParser):
    """Find text elements that need an edit id, plus where the head/body tags sit."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=False)
        self.lines = text.split("\n")
        self.offsets = [0]
        for line in self.lines[:-1]:
            self.offsets.append(self.offsets[-1] + len(line) + 1)
        self.stack: list[tuple[str, bool, str | None]] = []  # tag, ignored, slide id
        self.targets: list[tuple[int, str, str, bool]] = []  # offset, start tag text, slide id, has id
        self.body: tuple[int, str] | None = None
        self.has_loader = self.has_css = False

    def pos(self) -> int:
        line, col = self.getpos()
        return self.offsets[line - 1] + col

    def handle_starttag(self, tag, attrs):
        names = dict(attrs)
        raw = self.get_starttag_text() or ""
        if tag == "script" and HOOK in names and "loader.js" in (names.get("src") or ""):
            self.has_loader = True
        if tag == "link" and HOOK in names:
            self.has_css = True
        if tag == "body":
            self.body = (self.pos(), raw)
        parent_ignored = self.stack[-1][1] if self.stack else False
        parent_slide = self.stack[-1][2] if self.stack else None
        ignored = parent_ignored or "data-screen-ignore" in names or names.get("data-edit") == "off"
        slide = names.get("data-slide-id") or names.get("data-page") or (
            names.get("id") if "slide" in (names.get("class") or "") else None) or parent_slide
        wants = tag in TEXT_TAGS or names.get("data-editable") in {"text", "image"}
        if wants and not ignored and not (self.stack and self.stack[-1][0] in TEXT_TAGS):
            self.targets.append((self.pos(), raw, slide or "page", "data-edit-id" in names))
        if tag not in VOID and not raw.endswith("/>"):
            self.stack.append((tag, ignored, slide))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def editor_href(project: Path, page: Path) -> str:
    return os.path.relpath(project / EDITOR_DIR, page.parent).replace(os.sep, "/")


def problems(project: Path, page: Path) -> list[str]:
    scan = Scan(page.read_text(encoding="utf-8"))
    scan.feed(page.read_text(encoding="utf-8"))
    found = []
    if not scan.has_css:
        found.append("没有加载编辑器样式 editor.css")
    if not scan.has_loader:
        found.append("没有加载编辑器 loader.js")
    if scan.body is None or "data-document-id" not in scan.body[1]:
        found.append("<body> 缺少 data-document-id")
    missing = [raw for _, raw, _, has in scan.targets if not has]
    if missing:
        found.append(f"{len(missing)} 处文字没有 data-edit-id（例如 {missing[0][:60]}）")
    if not (project / EDITOR_DIR / "loader.js").is_file():
        found.append(f"项目里没有编辑器文件 {EDITOR_DIR}/")
    if (project / "deck" / "components.css").is_file() and "data-components" not in page.read_text(encoding="utf-8"):
        found.append("没有加载文字层组件 deck/components.css")
    return found


def inject(project: Path, page: Path) -> int:
    target = project / EDITOR_DIR
    if not (target / "loader.js").is_file():
        shutil.copytree(EDITOR_SRC, target, dirs_exist_ok=True)
    text = page.read_text(encoding="utf-8")
    scan = Scan(text)
    scan.feed(text)
    counters: dict[str, int] = {}
    edits: list[tuple[int, str, str]] = []
    for offset, raw, slide, has in scan.targets:
        counters[slide] = counters.get(slide, 0) + 1
        if has:
            continue
        add = f' data-edit-id="{slide}.t{counters[slide]:02d}"'
        if "data-editable" not in raw:
            add = ' data-editable="text"' + add
        end = len(raw) - (2 if raw.endswith("/>") else 1)
        edits.append((offset, raw, raw[:end] + add + raw[end:]))
    if scan.body is not None and "data-document-id" not in scan.body[1]:
        raw = scan.body[1]
        edits.append((scan.body[0], raw, raw[:-1] + f' data-document-id="{project.name}">'))
    for offset, old, new in sorted(edits, reverse=True):
        assert text[offset:offset + len(old)] == old
        text = text[:offset] + new + text[offset + len(old):]
    href = editor_href(project, page)
    if not scan.has_css:
        tag = f'<link rel="stylesheet" href="{href}/editor.css" {HOOK}>\n'
        text = text.replace("</head>", tag + "</head>", 1) if "</head>" in text else tag + text
    components = project / "deck" / "components.css"
    if components.is_file() and "data-components" not in text:
        rel = os.path.relpath(components, page.parent).replace(os.sep, "/")
        tag = f'<link rel="stylesheet" href="{rel}" data-components>\n'
        text = text.replace("</head>", tag + "</head>", 1) if "</head>" in text else tag + text
    if not scan.has_loader:
        tag = f'<script type="module" src="{href}/loader.js" {HOOK}></script>\n'
        text = text.replace("</body>", tag + "</body>", 1) if "</body>" in text else text + tag
    page.write_text(text, encoding="utf-8")
    return len(edits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("inject", "check"))
    parser.add_argument("project")
    parser.add_argument("pages", nargs="+")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    failed = 0
    for name in args.pages:
        page = Path(name)
        page = (page if page.is_absolute() else project / page).resolve()
        if args.command == "inject":
            count = inject(project, page)
            print(f"{page.relative_to(project)}: wired ({count} change(s))")
        else:
            found = problems(project, page)
            failed += bool(found)
            for item in found:
                print(f"FAIL {page.relative_to(project)}: {item}")
    if args.command == "check":
        print(f"FAIL: {failed} page(s) missing review hooks; run `review_hooks.py inject`" if failed
              else f"PASS: review hooks present in {len(args.pages)} page(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
