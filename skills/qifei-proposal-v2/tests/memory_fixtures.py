"""Fixture helper: record that memory signals were distilled for the project's current phase."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import proposal_memory  # noqa: E402


def mark_signals_run(project: Path) -> None:
    phase = proposal_memory.project_phase(project)
    path = proposal_memory.project_dir(project) / proposal_memory.SIGNALS_RECEIPT
    path.write_text(json.dumps({"phase": phase, "fresh": 0, "at": "2026-10-26T10:00:00+08:00"}), encoding="utf-8")
