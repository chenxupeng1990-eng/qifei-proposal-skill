#!/usr/bin/env python3
"""Cross-language canonical build identity for proposal renders."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping


def canonical_build_material(
    inputs: Mapping[str, str],
    runtime: Mapping[str, str],
    chapter_id: str | None,
) -> str:
    """Return the exact UTF-8 material shared with build_identity.mjs."""
    return json.dumps(
        {
            "chapter_id": chapter_id or None,
            "inputs": dict(inputs),
            "runtime": dict(runtime),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_id(
    inputs: Mapping[str, str],
    runtime: Mapping[str, str],
    chapter_id: str | None,
) -> str:
    material = canonical_build_material(inputs, runtime, chapter_id)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
