#!/usr/bin/env python3
"""Validate the JSON-Schema subset used by the proposal project state."""

from __future__ import annotations

import re
from typing import Any


TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def resolve_ref(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"Only local schema refs are supported: {ref}")
    value: Any = root
    for part in ref[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(value, dict):
        raise ValueError(f"Schema ref does not resolve to an object: {ref}")
    return value


def type_matches(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPE_MAP[expected])


def validate_json_schema(instance: Any, schema: dict, *, root: dict | None = None, path: str = "$") -> list[str]:
    root = root or schema
    if "$ref" in schema:
        return validate_json_schema(instance, resolve_ref(root, schema["$ref"]), root=root, path=path)

    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else list(expected)
        if not any(type_matches(instance, item) for item in expected_types):
            errors.append(f"{path}: expected type {' or '.join(expected_types)}")
            return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} is not in the allowed enum")

    if isinstance(instance, str):
        if len(instance) < int(schema.get("minLength", 0)):
            errors.append(f"{path}: string is shorter than minLength")
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, instance):
            errors.append(f"{path}: string does not match pattern {pattern!r}")

    if isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: array has fewer than minItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate_json_schema(item, item_schema, root=root, path=f"{path}[{index}]"))

    if isinstance(instance, dict):
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for required in schema.get("required") or []:
            if required not in instance:
                errors.append(f"{path}: missing required property {required!r}")
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate_json_schema(value, properties[key], root=root, path=f"{path}.{key}"))
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(validate_json_schema(value, additional, root=root, path=f"{path}.{key}"))
    return errors
