#!/usr/bin/env python3
"""Final low-level check before final assembly, and again on the exported PPTX.

Content and visual quality were settled earlier (full-draft review, page production
checks, independent visual review, Owner page confirmation). This only catches
low-level slips: page count and order, on-screen text against the frozen draft,
layout measurements (orphans, overflow), and a recorded proofread for typos.

    python3 scripts/final_check.py <project> --proofread "全稿通读，无错别字"
    python3 scripts/final_check.py <project> --pptx exports/<deck>.pptx   # after export
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import screen_text  # noqa: E402
from validate_project import final_order_hash, load_json, validate_visual_review  # noqa: E402

REPORT = Path("reviews") / "qa" / "FINAL-CHECK.json"


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def deck_order(project: Path) -> list[str]:
    deck = load_json(project / "deck" / "deck-spec.json")
    return [str(s.get("slide_id") or "").strip() for s in deck.get("slides") or [] if isinstance(s, dict)]


def page_checks(project: Path, order: list[str]) -> tuple[dict, list[str]]:
    problems: list[str] = []
    manifest = load_json(project / "deck" / "assembly-ready" / "manifest.json")
    pages = {str(p.get("slide_id")): p for p in manifest.get("pages") or [] if isinstance(p, dict)}
    ready_order = [str(p.get("slide_id")) for p in manifest.get("pages") or [] if isinstance(p, dict)]
    if ready_order != order:
        problems.append(f"assembly-ready order {ready_order} does not match deck order {order}")
    state = load_json(project / "project-state.json")
    notes = state.get("speaker_notes") if isinstance(state.get("speaker_notes"), dict) else {}
    if notes.get("final_order_hash") not in (None, final_order_hash(order)):
        problems.append("speaker notes were written for another page order")
    draft = screen_text.draft_screen(project)
    allowed = screen_text.whitelist(project)
    text_results = {}
    for slide_id in order:
        page = pages.get(slide_id)
        if not page:
            problems.append(f"{slide_id}: not in the assembly-ready library")
            continue
        chunks = None
        review_path = page.get("review_manifest_path")
        if review_path and (project / review_path).is_file():
            review = load_json(project / review_path)
            chunks = next((p.get("text_chunks") for p in review.get("pages") or [] if p.get("slide_id") == slide_id), None)
        if chunks is None and page.get("source_type") == "html" and page.get("source_path"):
            found = screen_text.html_chunks(project / page["source_path"])
            chunks = found.get(slide_id) or found.get("") or []
        if chunks is None:
            text_results[slide_id] = {"skipped": "image-native page; check its text by eye"}
            continue
        if slide_id not in draft:
            problems.append(f"{slide_id}: not in the frozen draft")
            continue
        result = screen_text.compare(draft[slide_id], [str(c) for c in chunks], allowed)
        text_results[slide_id] = result
        problems += screen_text.failures({slide_id: result})
    if state.get("task_mode") != "inherited_module":
        problems += validate_visual_review(project, state)
    layout_path = project / "reviews" / "visual" / "LAYOUT-CHECK.json"
    layout = load_json(layout_path) if layout_path.is_file() else None
    if layout is None:
        problems.append("reviews/visual/LAYOUT-CHECK.json is missing; run check_page_layout.mjs on the final pages")
    else:
        for slide_id, items in (layout.get("pages") or {}).items():
            for item in items.get("problems") or []:
                problems.append(f"{slide_id}: {item}")
    return {"order": order, "text": text_results, "layout_report": str(layout_path.relative_to(project)) if layout else None}, problems


def write_report(project: Path, report: dict) -> None:
    path = project / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state_path = project / "project-state.json"
    state = load_json(state_path)
    state["final_check"] = {"report_path": REPORT.as_posix(), "status": report["status"],
                            "final_order_hash": report["final_order_hash"],
                            "pptx_status": (report.get("pptx") or {}).get("status")}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--proofread", help="what the proofread for typos found, e.g. 全稿通读，无错别字")
    parser.add_argument("--pptx", help="exported PPTX to check against the frozen draft (after export)")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    order = deck_order(project)

    if args.pptx:
        report = load_json(project / REPORT)
        if report.get("final_order_hash") != final_order_hash(order):
            raise SystemExit("Run the pre-assembly final check for the current page order first")
        results = screen_text.check_pptx(project, project / args.pptx, order)
        problems = screen_text.failures(results)
        report["pptx"] = {"path": args.pptx, "at": now(), "status": "failed" if problems else "passed", "problems": problems}
        write_report(project, report)
    else:
        if not (args.proofread or "").strip():
            raise SystemExit("--proofread is required: read every page for typos and record what you found")
        checks, problems = page_checks(project, order)
        report = {"at": now(), "status": "failed" if problems else "passed", "final_order_hash": final_order_hash(order),
                  "page_count": len(order), "proofread": args.proofread.strip(), "checks": checks, "problems": problems}
        write_report(project, report)
    for problem in problems:
        print(f"ERROR {problem}")
    print(f"{'FAIL' if problems else 'PASS'}: final low-level check ({len(order)} pages)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
