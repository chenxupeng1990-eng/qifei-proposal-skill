#!/usr/bin/env python3
"""Report the runtime profile, adapters, deliverables, and current boundaries."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


TASK_MODES = ("full_deck", "inherited_module", "standalone_module")


def env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def lark_auth_is_ready(status: dict) -> bool:
    identities = status.get("identities") if isinstance(status.get("identities"), dict) else {}
    selected = str(status.get("identity") or "").strip()
    candidates = [identities.get(selected)] if selected else list(identities.values())
    for identity in candidates:
        if not isinstance(identity, dict) or identity.get("available") is not True:
            continue
        if str(identity.get("status") or "").strip() in {"ready", "needs_refresh"}:
            return True
    return False


def detect_lark_authorization(lark_cli: bool) -> bool:
    if "PROPOSAL_FEISHU_AUTHORIZED" in os.environ:
        return env_true("PROPOSAL_FEISHU_AUTHORIZED")
    if not lark_cli:
        return False
    try:
        result = subprocess.run(
            ["lark-cli", "auth", "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0:
            return False
        return lark_auth_is_ready(json.loads(result.stdout))
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False


def detect_capabilities() -> dict:
    browser_candidates = (
        os.environ.get("CHROME_PATH"),
        os.environ.get("EDGE_PATH"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    )
    browser = any(Path(item).is_file() for item in browser_candidates if item)
    lark_cli = shutil.which("lark-cli") is not None
    return {
        "agent_host": os.environ.get("PROPOSAL_AGENT_HOST", "unknown"),
        "filesystem": True,
        "shell": True,
        "python": sys.version_info >= (3, 9),
        "node": shutil.which("node") is not None,
        "npm": shutil.which("npm") is not None,
        "browser": browser,
        "image_generation": bool(os.environ.get("PROPOSAL_IMAGE_PROVIDER")),
        "image_provider": os.environ.get("PROPOSAL_IMAGE_PROVIDER") or None,
        "visual_understanding": env_true("PROPOSAL_VISUAL_UNDERSTANDING"),
        "codex_native_comments": env_true("PROPOSAL_CODEX_NATIVE_COMMENTS"),
        "feishu_cli": lark_cli,
        "feishu_authorized": detect_lark_authorization(lark_cli),
    }


def load_capabilities(path: str | None) -> dict:
    if not path:
        return detect_capabilities()
    value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("capabilities input must be a JSON object")
    return value


def build_report(capabilities: dict, task_mode: str) -> dict:
    image_ready = bool(capabilities.get("image_generation"))
    local_runtime = all(bool(capabilities.get(key)) for key in ("node", "npm", "browser"))
    codex_host = str(capabilities.get("agent_host") or "").startswith("codex")

    if image_ready and local_runtime:
        runtime_profile = "codex_full" if codex_host else "api_full"
    elif local_runtime:
        runtime_profile = "local_production"
    else:
        runtime_profile = "content_only"

    if capabilities.get("codex_native_comments"):
        review_adapter = "codex_native_comments"
    elif local_runtime and capabilities.get("filesystem"):
        review_adapter = "local_review_bundle"
    else:
        review_adapter = "external_review_record"

    feishu_ready = bool(capabilities.get("feishu_cli") and capabilities.get("feishu_authorized"))
    if task_mode == "full_deck":
        content_authority = "feishu" if feishu_ready else "feishu_pending"
    elif task_mode == "inherited_module":
        content_authority = "inherit_parent"
    else:
        content_authority = "local"

    blockers: list[str] = []
    stage_blockers: dict[str, list[str]] = {}
    if not capabilities.get("filesystem"):
        blockers.append("filesystem access is required to create governed project artifacts")
    if task_mode == "full_deck" and not feishu_ready:
        stage_blockers.setdefault("manuscript_confirmation", []).append(
            "full_deck requires Feishu CLI authorization and reread proof"
        )
    if not image_ready:
        stage_blockers.setdefault("visual_direction", []).append(
            "a registered image generation adapter is required for formal visual approval"
        )
    if not capabilities.get("visual_understanding"):
        stage_blockers.setdefault("visual_qa", []).append(
            "visual understanding or a registered human visual reviewer is required for visual QA"
        )
    if not local_runtime:
        stage_blockers.setdefault("review_and_export", []).append(
            "Node, npm, and a launchable browser or an equivalent external renderer are required"
        )

    boundaries: list[str] = []
    if not image_ready:
        boundaries.append("formal visual direction and formal page generation cannot be approved")
    if not capabilities.get("visual_understanding"):
        boundaries.append("visual QA requires an external human or visual-understanding adapter")
    if not local_runtime:
        boundaries.append("local HTML review, PNG capture, and PPTX export are unavailable")
    if not feishu_ready:
        boundaries.append("Feishu writeback, reread revision, and collaboration proof are unavailable")
    if review_adapter != "codex_native_comments":
        boundaries.append("Codex native browser comments are replaced by a hash-bound review record")

    return {
        "schema_version": "1.0",
        "task_mode": task_mode,
        "runtime_profile": runtime_profile,
        "capabilities": capabilities,
        "adapters": {
            "image_generation": capabilities.get("image_provider") or ("configured_api" if image_ready else "none"),
            "review": review_adapter,
            "content_authority": content_authority,
            "independent_review": "separate_agent_or_human",
        },
        "deliverables": {
            "strategy_and_manuscript": bool(capabilities.get("filesystem")),
            "formal_visuals": image_ready and bool(capabilities.get("visual_understanding")),
            "local_review_bundle": review_adapter == "local_review_bundle",
            "pptx_export": local_runtime,
            "feishu_verification": feishu_ready,
        },
        "boundaries": boundaries,
        "blockers": blockers,
        "stage_blockers": stage_blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-mode", choices=TASK_MODES, default="full_deck")
    parser.add_argument("--capabilities", help="Optional JSON capability override")
    parser.add_argument("--write", help="Write the report to this path")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    try:
        report = build_report(load_capabilities(args.capabilities), args.task_mode)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Runtime doctor failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.write:
        output = Path(args.write).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    if args.json:
        print(rendered)
    else:
        print(f"Runtime profile: {report['runtime_profile']}")
        print(f"Task mode: {report['task_mode']}")
        for item in report["boundaries"]:
            print(f"BOUNDARY {item}")
        for item in report["blockers"]:
            print(f"BLOCKER {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
