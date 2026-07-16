#!/usr/bin/env python3
"""Validate frozen slide contracts, evidence links, copy budgets, and media paths."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from freeze_deck_spec import content_hash


SLIDE_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]{1,31}$")
LEAK_PATTERN = re.compile(
    r"待确认|TBD|TODO|仅供内部|内部备注|请补充|PLACEHOLDER|<local-path>|agent\s*note",
    re.IGNORECASE,
)
HTML_PATTERN = re.compile(r"<\s*/?\s*[a-z][^>]*>", re.IGNORECASE)
REMOTE_PATTERN = re.compile(r"^(?:https?:|file:|data:)", re.IGNORECASE)
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def visual_length(value: object) -> float:
    width = 0.0
    for char in str(value or ""):
        if char.isspace():
            width += 0.25
            continue
        width += 1.0 if unicodedata.east_asian_width(char) in {"W", "F"} else 0.5
    return round(width, 2)


def walk_strings(value: object, path: str = ""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_strings(item, f"{path}.{key}" if path else str(key))


def block_body_strings(blocks: object) -> list[str]:
    strings: list[str] = []
    for path, text in walk_strings(blocks, "blocks"):
        if path.endswith(".src") or path.endswith(".alt") or path.endswith(".type"):
            continue
        strings.append(text)
    return strings


def item_count(block: object) -> int:
    if not isinstance(block, dict):
        return 0
    items = block.get("items")
    return len(items) if isinstance(items, list) else 0


def media_sources(slide: dict[str, Any]) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    visual = slide.get("visual")
    if isinstance(visual, dict) and isinstance(visual.get("src"), str) and visual["src"].strip():
        sources.append(("visual.src", visual["src"].strip()))
    for index, block in enumerate(slide.get("blocks") or []):
        if isinstance(block, dict) and block.get("type") == "image" and isinstance(block.get("src"), str):
            sources.append((f"blocks[{index}].src", block["src"].strip()))
    return sources


def valid_local_media(project: Path, src: str) -> str | None:
    if not src:
        return "media source is empty"
    if REMOTE_PATTERN.search(src) or WINDOWS_ABSOLUTE.search(src) or src.startswith(("/", "\\")):
        return "media must use a project-local relative path"
    if "\\" in src:
        return "media path must use forward slashes"
    normalized = PurePosixPath(src)
    if ".." in normalized.parts or "." in normalized.parts:
        return "media path cannot contain traversal or dot segments"
    if not normalized.parts or normalized.parts[0] != "assets":
        return "media must live under project assets/"
    target = (project / Path(*normalized.parts)).resolve()
    assets_root = (project / "assets").resolve()
    try:
        target.relative_to(assets_root)
    except ValueError:
        return "media path escaped project assets/"
    if not target.is_file():
        return f"media file does not exist: {src}"
    return None


def evidence_ids(project: Path) -> set[str]:
    ledger_path = project / "evidence" / "evidence-ledger.json"
    ledger = load_json(ledger_path)
    rows = ledger.get("evidence") if isinstance(ledger.get("evidence"), list) else []
    return {str(row.get("evidence_id")) for row in rows if isinstance(row, dict) and row.get("evidence_id")}


def validate_deck(project: Path) -> list[str]:
    errors: list[str] = []
    try:
        deck = load_json(project / "deck" / "deck-spec.json")
        contracts_doc = load_json(project / "deck" / "slide-contracts.json")
        known_evidence = evidence_ids(project)
    except ValueError as exc:
        return [str(exc)]

    for key in ("deck_id", "project_name", "content_freeze_id", "design_version"):
        if not deck.get(key):
            errors.append(f"deck.{key} is required")

    contracts = contracts_doc.get("layouts") if isinstance(contracts_doc.get("layouts"), dict) else {}
    slides = deck.get("slides") if isinstance(deck.get("slides"), list) else []
    if not slides:
        errors.append("deck.slides must contain at least one slide")
        return errors

    seen: set[str] = set()
    for index, slide in enumerate(slides, start=1):
        scope = f"slide {index}"
        if not isinstance(slide, dict):
            errors.append(f"{scope}: expected object")
            continue
        slide_id = str(slide.get("slide_id") or "").strip()
        scope = slide_id or scope
        if not SLIDE_ID_PATTERN.fullmatch(slide_id):
            errors.append(f"{scope}: invalid slide_id; use uppercase stable IDs such as P01 or A03")
        if slide_id in seen:
            errors.append(f"{scope}: duplicate slide_id")
        seen.add(slide_id)

        for key in ("chapter", "role", "layout", "title", "speaker_doc_anchor"):
            if not slide.get(key):
                errors.append(f"{scope}: missing required field {key}")
        if slide.get("status") != "content_frozen":
            errors.append(f"{scope}: status must be content_frozen before generation")
        approved_hash = slide.get("approved_content_hash")
        if not approved_hash:
            errors.append(f"{scope}: missing approved_content_hash")
        elif approved_hash != content_hash(slide):
            errors.append(f"{scope}: content changed after approval; reopen and freeze again")

        layout = str(slide.get("layout") or "")
        contract = contracts.get(layout)
        if not isinstance(contract, dict):
            errors.append(f"{scope}: unknown layout contract {layout!r}")
            contract = {}

        title_width = visual_length(slide.get("title"))
        subtitle_width = visual_length(slide.get("subtitle"))
        body_width = sum(visual_length(text) for text in block_body_strings(slide.get("blocks") or []))
        for field, actual, budget_key in (
            ("title", title_width, "title_max"),
            ("subtitle", subtitle_width, "subtitle_max"),
            ("blocks", body_width, "body_max"),
        ):
            budget = contract.get(budget_key)
            if isinstance(budget, (int, float)) and actual > budget:
                errors.append(f"{scope}: {field} visual width {actual} exceeds {layout}.{budget_key}={budget}; shorten or split")

        max_items = contract.get("max_items")
        if isinstance(max_items, int):
            for block_index, block in enumerate(slide.get("blocks") or []):
                count = item_count(block)
                if count > max_items:
                    errors.append(f"{scope}: blocks[{block_index}] has {count} items, max {max_items} for {layout}")

        sources = media_sources(slide)
        media_slots = contract.get("media_slots")
        if isinstance(media_slots, int) and len(sources) > media_slots:
            errors.append(f"{scope}: {len(sources)} media item(s) exceed {layout}.media_slots={media_slots}")
        for field, src in sources:
            problem = valid_local_media(project, src)
            if problem:
                errors.append(f"{scope}.{field}: {problem}")

        slide_evidence = slide.get("evidence_ids")
        if not isinstance(slide_evidence, list):
            errors.append(f"{scope}: evidence_ids must be an array")
        else:
            for evidence_id in slide_evidence:
                if str(evidence_id) not in known_evidence:
                    errors.append(f"{scope}: unknown evidence_id {evidence_id!r}")

        public_copy = {
            "kicker": slide.get("kicker"),
            "title": slide.get("title"),
            "subtitle": slide.get("subtitle"),
            "blocks": slide.get("blocks"),
            "source_note": slide.get("source_note"),
        }
        for field, text in walk_strings(public_copy):
            if LEAK_PATTERN.search(text):
                errors.append(f"{scope}.{field}: internal or unresolved wording is not allowed")
            if HTML_PATTERN.search(text):
                errors.append(f"{scope}.{field}: raw HTML is not allowed in authored copy")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors = validate_deck(project)
    if errors:
        print("Deck contract validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Deck contract valid: {project / 'deck' / 'deck-spec.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
