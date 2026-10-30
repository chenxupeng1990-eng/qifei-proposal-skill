#!/usr/bin/env python3
"""Design review comments: the Owner draws a box on a rendered page and comments on it.

Each thread records the slide, the review PNG it was drawn on (path and SHA256), the box
in 1920×1080 page coordinates, the text block under the box, and a crop of the area. A
thread whose page has been re-rendered since is marked stale, so the agent knows the box
may have moved. Agents list and reply; only the Owner resolves, from the studio page.

The studio serves the review page at /design. Agents use:

    python3 scripts/design_review.py list <project> [--all] [--json]
    python3 scripts/design_review.py reply <project> D-0001 "改了什么、在哪个文件"
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

STORE = Path("deck") / "review" / "design-comments.json"
CROPS = Path("deck") / "review" / "design-comments"
CALIBRATION = Path("deck") / "review" / "calibration"  # capture_calibration_pngs.mjs writes here
PAGE_W, PAGE_H = 1920, 1080
MAX_TEXT = 4000
MAX_CROP_BYTES = 4 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ReviewError(ValueError):
    pass


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_pages(project: Path) -> list[dict[str, Any]]:
    """Latest captured PNG per slide across every review manifest under deck/review, in deck order when known.

    A review manifest is any JSON there with `pages` entries carrying `slide_id` and `png_path`
    (capture_review_pngs.mjs writes `<chapter>/review-manifest.json`; per-page manifests work too).
    """
    latest: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted((project / "deck" / "review").rglob("*.json")):
        if manifest_path.name == STORE.name:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict) or not isinstance(manifest.get("pages"), list):
            continue
        captured = manifest.get("created_at") or dt.datetime.fromtimestamp(manifest_path.stat().st_mtime).astimezone().isoformat()
        for page in manifest["pages"]:
            if not isinstance(page, dict):
                continue
            png = project / str(page.get("png_path") or "")
            if not page.get("slide_id") or not png.is_file():
                continue
            entry = {
                "slide_id": page["slide_id"],
                "png_path": page["png_path"],
                "png_sha256": sha256_file(png),
                "manifest": manifest_path.relative_to(project).as_posix(),
                "captured_at": captured,
                "text_boxes": page.get("text_boxes") or [],
            }
            if entry["captured_at"] >= latest.get(page["slide_id"], {}).get("captured_at", ""):
                latest[page["slide_id"]] = entry
    order: list[str] = []
    deck = project / "deck" / "deck-spec.json"
    if deck.is_file():
        try:
            order = [str(s.get("slide_id")) for s in json.loads(deck.read_text(encoding="utf-8")).get("slides") or []]
        except json.JSONDecodeError:
            order = []
    rank = {slide_id: n for n, slide_id in enumerate(order)}
    return sorted(latest.values(), key=lambda p: (rank.get(p["slide_id"], len(rank)), p["slide_id"]))


def anchor_for(rect: dict[str, float], boxes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The text block that overlaps the drawn box most (by share of the block covered)."""
    best, best_score = None, 0.0
    for box in boxes:
        ix = max(0.0, min(rect["x"] + rect["w"], box["x"] + box["w"]) - max(rect["x"], box["x"]))
        iy = max(0.0, min(rect["y"] + rect["h"], box["y"] + box["h"]) - max(rect["y"], box["y"]))
        area = max(1.0, box["w"] * box["h"])
        score = ix * iy / area
        if score > best_score:
            best, best_score = box, score
    if not best:
        return None
    return {"text": str(best.get("text") or "")[:120], "selector": str(best.get("selector") or "")[:200],
            "box": {k: round(float(best[k]), 1) for k in ("x", "y", "w", "h")}}


class DesignCommentStore:
    def __init__(self, project: Path) -> None:
        self.project = project
        self.path = project / STORE
        self.lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"threads": []}
        return json.loads(self.path.read_text(encoding="utf-8") or '{"threads": []}')

    def digest(self) -> str | None:
        return hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.is_file() else None

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".design-comments-", suffix=".json", dir=self.path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, self.path)

    @staticmethod
    def _text(value: Any, name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ReviewError(f"{name} cannot be empty")
        if len(text) > MAX_TEXT:
            raise ReviewError(f"{name} is longer than {MAX_TEXT} characters")
        return text

    def _find(self, data: dict[str, Any], thread_id: str) -> dict[str, Any]:
        for thread in data["threads"]:
            if thread["id"] == thread_id:
                return thread
        raise ReviewError(f"unknown design comment {thread_id}")

    def threads(self) -> list[dict[str, Any]]:
        """Threads with `stale` set when the slide's current review PNG differs from the one commented on.
        Deleted threads stay in the file as a record and are left out here."""
        current = {p["slide_id"]: p["png_sha256"] for p in review_pages(self.project)}
        out = []
        for thread in self.load()["threads"]:
            if thread["status"] == "deleted":
                continue
            out.append({**thread, "stale": current.get(thread["slide"]) != thread["png_sha256"]})
        return out

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        slide = str(payload.get("slide") or "")
        page = next((p for p in review_pages(self.project) if p["slide_id"] == slide), None)
        if not page:
            raise ReviewError(f"{slide or '(no slide)'} has no captured review page")
        if payload.get("png_sha256") and payload["png_sha256"] != page["png_sha256"]:
            raise ReviewError("the page was re-rendered while you were drawing; reload and draw the box again")
        try:
            raw = payload.get("rect") or {}
            rect = {k: float(raw[k]) for k in ("x", "y", "w", "h")}
        except (KeyError, TypeError, ValueError) as error:
            raise ReviewError("rect needs x, y, w and h in page pixels") from error
        rect["x"], rect["y"] = max(0.0, rect["x"]), max(0.0, rect["y"])
        rect["w"], rect["h"] = min(rect["w"], PAGE_W - rect["x"]), min(rect["h"], PAGE_H - rect["y"])
        if rect["w"] < 4 or rect["h"] < 4:
            raise ReviewError("the box is too small")
        rect = {k: round(v, 1) for k, v in rect.items()}
        text = self._text(payload.get("text"), "comment")
        author = self._text(payload.get("author") or "Owner", "author")[:40]
        with self.lock:
            data = self.load()
            number = max((int(t["id"].split("-")[1]) for t in data["threads"]), default=0) + 1
            thread_id = f"D-{number:04d}"
            crop = self._save_crop(thread_id, payload.get("crop"))
            thread = {
                "id": thread_id,
                "slide": slide,
                "png_path": page["png_path"],
                "png_sha256": page["png_sha256"],
                "manifest": page["manifest"],
                "rect": rect,
                "anchor": anchor_for(rect, page["text_boxes"]),
                "crop_path": crop,
                "status": "open",
                "created_at": now(),
                "messages": [{"author": author, "at": now(), "text": text}],
            }
            data["threads"].append(thread)
            self._write(data)
            return thread

    def _save_crop(self, thread_id: str, data_url: Any) -> str | None:
        if not data_url:
            return None
        head, _, body = str(data_url).partition(",")
        if head != "data:image/png;base64":
            raise ReviewError("crop must be a PNG data URL")
        raw = base64.b64decode(body, validate=True)
        if not raw.startswith(PNG_MAGIC) or len(raw) > MAX_CROP_BYTES:
            raise ReviewError("crop is not a PNG or is too large")
        path = self.project / CROPS / f"{thread_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path.relative_to(self.project).as_posix()

    def reply(self, thread_id: str, text: str, author: str) -> dict[str, Any]:
        with self.lock:
            data = self.load()
            thread = self._find(data, thread_id)
            name = self._text(author or "Agent", "author")[:40]
            thread["messages"].append({"author": name, "at": now(), "text": self._text(text, "reply")})
            self._write(data)
            return thread

    def set_status(self, thread_id: str, status: str, author: str) -> dict[str, Any]:
        """Resolve, reopen or delete. Only the studio page calls this: it is the Owner's call. A
        deleted thread is hidden everywhere but kept in the file."""
        if status not in {"open", "resolved", "deleted"}:
            raise ReviewError("status must be open, resolved or deleted")
        with self.lock:
            data = self.load()
            thread = self._find(data, thread_id)
            thread.update({"status": status, "status_by": (author or "Owner")[:40], "status_at": now()})
            self._write(data)
            return thread


def open_threads(project: Path, slide_id: str | None = None) -> list[dict[str, Any]]:
    return [t for t in DesignCommentStore(project).threads()
            if t["status"] == "open" and (slide_id is None or t["slide"] == slide_id)]


def open_calibration_threads(project: Path) -> list[dict[str, Any]]:
    """Open comments on design calibration samples; the calibration cannot be approved over them."""
    prefix = CALIBRATION.as_posix() + "/"
    return [t for t in open_threads(project) if str(t.get("manifest") or "").startswith(prefix)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="list design comments (open ones by default)")
    listing.add_argument("project")
    listing.add_argument("--all", action="store_true", help="include resolved threads")
    listing.add_argument("--slide")
    listing.add_argument("--json", action="store_true")
    reply = sub.add_parser("reply", help="reply as an agent; the Owner resolves in the studio")
    reply.add_argument("project")
    reply.add_argument("thread")
    reply.add_argument("text")
    reply.add_argument("--author", default="Agent")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    store = DesignCommentStore(project)
    if args.command == "reply":
        thread = store.reply(args.thread, args.text, args.author)
        print(f"Replied to {thread['id']} ({thread['slide']}); the Owner decides whether to resolve it.")
        return 0
    threads = [t for t in store.threads()
               if (args.all or t["status"] == "open") and (not args.slide or t["slide"] == args.slide)]
    if args.json:
        print(json.dumps(threads, ensure_ascii=False, indent=2))
        return 0
    for t in threads:
        r = t["rect"]
        anchor = f"｜“{t['anchor']['text']}”" if t.get("anchor") else ""
        flag = " [页面已重新渲染，框位置可能已变]" if t["stale"] else ""
        print(f"{t['id']} [{t['status']}] {t['slide']} 框 x{r['x']:.0f} y{r['y']:.0f} {r['w']:.0f}×{r['h']:.0f}{anchor}{flag}")
        if t.get("crop_path"):
            print(f"    截图：{t['crop_path']}")
        for message in t["messages"]:
            print(f"    {message['author']} {message['at'][:16].replace('T', ' ')}：{message['text']}")
    if not threads:
        print("No open design comments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
