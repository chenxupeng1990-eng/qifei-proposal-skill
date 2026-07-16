#!/usr/bin/env python3
"""Render a frozen QIFEI deck spec into the single HTML visual master."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from validate_deck_spec import load_json, media_sources, validate_deck
from validate_project import validate_project


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_ROOT / "assets" / "html-runtime" / "deck-template.html"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_script_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors = validate_project(project) + validate_deck(project)
    if errors:
        print("Render blocked by deck validation:")
        for error in errors:
            print(f"- {error}")
        return 1

    deck_path = project / "deck" / "deck-spec.json"
    tokens_path = project / "deck" / "design-tokens.json"
    comments_path = project / "reviews" / "review-comments.json"
    contracts_path = project / "deck" / "slide-contracts.json"
    state_path = project / "project-state.json"
    deck = load_json(deck_path)
    tokens = load_json(tokens_path)
    comments = load_json(comments_path)
    state = load_json(state_path)

    tracked = [
        project / "AGENTS.md",
        project / "DESIGN.md",
        project / "content" / "proposal-brief.md",
        deck_path,
        tokens_path,
        contracts_path,
    ]
    brand_visual = state.get("brand_visual") if isinstance(state.get("brand_visual"), dict) else {}
    audit_path = str(brand_visual.get("audit_path") or "evidence/brand-visual-audit.md")
    tracked.append(project / Path(*audit_path.replace("\\", "/").split("/")))
    for source in brand_visual.get("source_files") or []:
        tracked.append(project / Path(*str(source).replace("\\", "/").split("/")))
    for slide in deck.get("slides") or []:
        for _, src in media_sources(slide):
            tracked.append(project / Path(*src.split("/")))
    hashes = {str(path.relative_to(project)).replace("\\", "/"): sha256(path) for path in tracked if path.is_file()}
    runtime_paths = [
        TEMPLATE_PATH,
        Path(__file__).resolve(),
        Path(__file__).with_name("validate_deck_spec.py"),
        Path(__file__).with_name("validate_project.py"),
        Path(__file__).with_name("export_deck.mjs"),
    ]
    runtime_hashes: dict[str, str] = {}
    for runtime_path in runtime_paths:
        if runtime_path.is_file():
            relative = str(runtime_path.relative_to(SKILL_ROOT)).replace("\\", "/")
            runtime_hashes[f"skill:{relative}"] = sha256(runtime_path)
    build_material = json.dumps({"inputs": hashes, "runtime": runtime_hashes}, sort_keys=True, separators=(",", ":"))
    build_id = hashlib.sha256(build_material.encode("utf-8")).hexdigest()[:16]

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = (
        template.replace("__DECK_JSON__", safe_script_json(deck))
        .replace("__DESIGN_JSON__", safe_script_json(tokens))
        .replace("__COMMENTS_JSON__", safe_script_json(comments))
        .replace("__BUILD_ID__", build_id)
    )
    out_path = project / "deck" / "proposal.html"
    atomic_text(out_path, html)
    output_hash = sha256(out_path)

    manifest = {
        "schema_version": "1.0",
        "build_id": build_id,
        "rendered_at": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "content_freeze_id": deck.get("content_freeze_id"),
        "design_version": deck.get("design_version"),
        "inputs": hashes,
        "runtime": runtime_hashes,
        "output": "deck/proposal.html",
        "output_sha256": output_hash,
    }
    atomic_text(project / "deck" / "build-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Rendered HTML master: {out_path}")
    print(f"Build id: {build_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
