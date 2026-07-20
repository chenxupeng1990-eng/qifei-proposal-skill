#!/usr/bin/env python3
"""Dependency-free hash contract for frozen proposal slides."""

from __future__ import annotations

import hashlib
import json


HASH_FIELDS = (
    "chapter",
    "role",
    "layout",
    "kicker",
    "title",
    "subtitle",
    "blocks",
    "visual",
    "evidence_ids",
    "speaker_doc_anchor",
)


def content_hash(slide: dict) -> str:
    payload = {key: slide.get(key) for key in HASH_FIELDS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
