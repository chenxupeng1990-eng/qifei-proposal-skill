#!/usr/bin/env python3
"""Report the runtime profile, adapters, deliverables, and current boundaries."""

from __future__ import annotations

import argparse
import datetime as dt
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


def runtime_file() -> Path:
    """Per-machine record of the abilities agents declared (kept beside the memory home)."""
    return Path(os.environ.get("QIFEI_RUNTIME_FILE") or Path.home() / ".qifei-proposal" / "runtime.json")


def load_saved() -> dict:
    try:
        value = json.loads(runtime_file().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_declared(declared: dict) -> Path:
    saved = load_saved()
    saved.update({key: value for key, value in declared.items() if value and key != "agent_host"})
    path = runtime_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def detect_agent_host() -> str:
    """Which agent runs this script. A Python script cannot see the agent's tools, but it can see its host."""
    if os.environ.get("PROPOSAL_AGENT_HOST"):
        return os.environ["PROPOSAL_AGENT_HOST"]
    if os.environ.get("CLAUDECODE") or os.environ.get("AI_AGENT", "").startswith("claude-code"):
        return "claude_code"
    if any(os.environ.get(name) for name in ("CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_THREAD_ID")):
        return "codex"
    return "unknown"


def first_declared(declared: dict, saved: dict, key: str, env_value) -> tuple:
    """(value, source): what the agent declared now, then the environment, then what was saved on this machine."""
    for source, value in (("agent", declared.get(key)), ("env", env_value), ("saved", saved.get(key))):
        if value:
            return value, source
    return None, None


def detect_capabilities(declared: dict | None = None) -> dict:
    """The agent's own abilities (image generation, reading images, native browser comments) are invisible to
    this script, so the agent declares them; the environment and earlier saved declarations also count."""
    declared = declared or {}
    saved = load_saved()
    provider, provider_source = first_declared(declared, saved, "image_provider", os.environ.get("PROPOSAL_IMAGE_PROVIDER"))
    visual, visual_source = first_declared(declared, saved, "visual_understanding", env_true("PROPOSAL_VISUAL_UNDERSTANDING"))
    comments, comments_source = first_declared(declared, saved, "codex_native_comments", env_true("PROPOSAL_CODEX_NATIVE_COMMENTS"))
    edit, edit_source = first_declared(declared, saved, "image_edit", env_true("PROPOSAL_IMAGE_EDIT"))
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
        "agent_host": declared.get("agent_host") or detect_agent_host(),
        "filesystem": True,
        "shell": True,
        "python": sys.version_info >= (3, 9),
        "node": shutil.which("node") is not None,
        "npm": shutil.which("npm") is not None,
        "browser": browser,
        "image_generation": bool(provider),
        "image_provider": str(provider) if provider else None,
        "visual_understanding": bool(visual),
        "codex_native_comments": bool(comments),
        "image_edit": bool(edit),
        "capability_sources": {"image_generation": provider_source, "visual_understanding": visual_source,
                               "codex_native_comments": comments_source, "image_edit": edit_source},
        "feishu_cli": lark_cli,
        "feishu_authorized": detect_lark_authorization(lark_cli),
    }


def load_capabilities(path: str | None, declared: dict | None = None) -> dict:
    if not path:
        return detect_capabilities(declared)
    value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("capabilities input must be a JSON object")
    return value


# Capabilities that can usually be filled. When one is missing the agent asks the user before downgrading;
# Feishu and native comments have built-in equivalents (the studio, hash-bound review records) and are not asked.
GAP_HELP = {
    "image_generation": {
        "blocks": ["visual_direction", "design_calibration", "generation"],
        "question": "这次没有检测到图像生成能力。视觉方向、设计校准和正式页面都需要真实生图。你能补上吗？",
        "options": [
            "我（当前 Agent）其实能生图：重跑 doctor 并加 --image-provider <名称>",
            "配置一个 OpenAI 兼容的图像 API：设置 PROPOSAL_IMAGE_PROVIDER=openai_api 和对应的 API Key 环境变量",
            "换一个能生图的 Agent（如 Codex）来做视觉阶段",
            "暂不补齐：先做到内容冻结，视觉阶段前再处理（记录为 Owner 接受的降级）",
        ],
    },
    "visual_understanding": {
        "blocks": ["visual_review"],
        "question": "这次没有检测到看图能力。独立视觉审查需要有人或有 Agent 逐页看图。你能补上吗？",
        "options": [
            "我（当前 Agent）其实能看图：重跑 doctor 并加 --visual-understanding",
            "视觉审查交给另一个能看图的 Agent",
            "指定一位人工视觉审查者",
            "暂不补齐：视觉审查阶段前再处理（记录为 Owner 接受的降级）",
        ],
    },
    "image_edit": {
        "blocks": ["generation"],
        "question": "这是视觉表现型任务（如品牌手册），整页连文字一起生图。图上文字出错时，要框出出错区域局部重生成。这次没有检测到局部编辑（带蒙版重绘）能力，你能补上吗？",
        "options": [
            "我（当前 Agent）的生图工具能局部编辑：重跑 doctor 并加 --image-edit",
            "配置一个支持蒙版编辑的图像 API，设置 PROPOSAL_IMAGE_EDIT=1",
            "暂不补齐：文字出错时整页重生成（记录为 Owner 接受的降级）",
        ],
    },
    "local_runtime": {
        "blocks": ["review", "speaker_notes", "qa", "export"],
        "question": "这台电脑缺少 Node.js、npm 或可启动的浏览器，页面评审截图和 PNG/PDF/PPTX 导出做不了。你能补上吗？",
        "options": [
            "在仓库根目录运行 python3 scripts/bootstrap.py --suite v2（会安装依赖并自检）",
            "安装 Chrome / Edge，或用 CHROME_PATH 指向已安装的浏览器",
            "暂不补齐：只交付内容和提示词包（记录为 Owner 接受的降级）",
        ],
    },
}


def capability_gaps(capabilities: dict, task_nature: str = "persuasive") -> list[dict]:
    missing = {
        "image_generation": not capabilities.get("image_generation"),
        "visual_understanding": not capabilities.get("visual_understanding"),
        # Only a visual_showcase task draws text into the image and fixes it region by region.
        "image_edit": task_nature == "visual_showcase" and not capabilities.get("image_edit"),
        "local_runtime": not all(bool(capabilities.get(key)) for key in ("node", "npm", "browser")),
    }
    return [{"id": gap, **GAP_HELP[gap]} for gap, is_missing in missing.items() if is_missing]


def build_report(capabilities: dict, task_mode: str, task_nature: str = "persuasive") -> dict:
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
        # The local draft studio needs only Python; Feishu remains an optional collaboration adapter.
        content_authority = "studio"
    elif task_mode == "inherited_module":
        content_authority = "inherit_parent"
    else:
        content_authority = "local"

    blockers: list[str] = []
    stage_blockers: dict[str, list[str]] = {}
    if not capabilities.get("filesystem"):
        blockers.append("filesystem access is required to create governed project artifacts")
    if not image_ready:
        stage_blockers.setdefault("visual_direction", []).append(
            "no image generation declared: if this agent can generate images, rerun doctor with "
            "--image-provider <name> (add --remember to keep it for this machine)"
        )
    if not capabilities.get("visual_understanding"):
        stage_blockers.setdefault("visual_review", []).append(
            "no visual understanding declared: if this agent can read images, rerun doctor with --visual-understanding; "
            "otherwise register a human visual reviewer"
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
        boundaries.append("Feishu collaboration is unavailable; the local draft studio is the content authority")
    if review_adapter != "codex_native_comments":
        boundaries.append("Codex native browser comments are replaced by a hash-bound review record"
                          " (declare --native-comments if this agent has them)")

    return {
        "schema_version": "1.0",
        "task_mode": task_mode,
        "task_nature": task_nature,
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
        "gaps": capability_gaps(capabilities, task_nature),
    }


def update_notice() -> dict | None:
    """A newer release, for the agent to pass on once a day. Never blocks or fails the doctor."""
    try:
        import update_skill  # noqa: PLC0415

        return update_skill.check()
    except Exception:
        return None


def record_runtime(project: Path, report: dict) -> dict:
    """Write the gaps found into project-state.json, so validation can check each was put to the Owner."""
    state_path = project / "project-state.json"
    if not state_path.is_file():
        return {}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["runtime"] = {
        "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "agent_host": report["capabilities"].get("agent_host"),
        "runtime_profile": report["runtime_profile"],
        "gaps": [gap["id"] for gap in report["gaps"]],
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state.get("runtime_decisions") or {}


def accept_gap(project: Path, gap: str, by: str, note: str) -> None:
    """Record that the Owner chose not to fill a capability gap now (a deliberate, recorded downgrade)."""
    if gap not in GAP_HELP:
        raise ValueError(f"unknown gap {gap!r}; one of {', '.join(GAP_HELP)}")
    if not by.strip():
        raise ValueError("--by is required: the Owner who decided")
    state_path = project / "project-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("runtime_decisions", {})[gap] = {
        "decision": "accepted_downgrade", "by": by.strip(), "note": note.strip(),
        "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-mode", choices=TASK_MODES, default="full_deck")
    parser.add_argument("--capabilities", help="Optional JSON capability override")
    parser.add_argument("--write", help="Write the report to this path")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    parser.add_argument("--project", help="Proposal project directory; also prints the proposal memory for its phase")
    parser.add_argument("--agent-host", help="the agent running this, e.g. codex or claude_code (detected when omitted)")
    parser.add_argument("--image-provider", help="this agent's image generation, e.g. codex_builtin, magpie-image, openai_api")
    parser.add_argument("--visual-understanding", action="store_true", help="this agent can read and judge images")
    parser.add_argument("--native-comments", action="store_true", help="this agent has Codex native browser comments")
    parser.add_argument("--image-edit", action="store_true", help="this agent's image tool can regenerate a masked region")
    parser.add_argument("--task-nature", choices=("persuasive", "visual_showcase"),
                        help="read from project-state.json with --project; persuasive when omitted")
    parser.add_argument("--remember", action="store_true", help="save the declared abilities for this machine")
    parser.add_argument("--forget", action="store_true", help="clear the abilities saved for this machine")
    parser.add_argument("--accept-gap", choices=sorted(GAP_HELP),
                        help="record that the Owner chose not to fill this gap now (needs --project and --by)")
    parser.add_argument("--by", default="", help="the Owner who decided (with --accept-gap)")
    parser.add_argument("--note", default="", help="why, and when to revisit (with --accept-gap)")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve() if args.project else None
    if args.accept_gap:
        if project is None:
            print("--accept-gap needs --project", file=sys.stderr)
            return 2
        try:
            accept_gap(project, args.accept_gap, args.by, args.note)
        except (OSError, ValueError) as exc:
            print(f"ERROR {exc}", file=sys.stderr)
            return 2
        print(f"Recorded: {args.by} accepted working without {args.accept_gap} for now")
    declared = {"agent_host": args.agent_host, "image_provider": args.image_provider,
                "visual_understanding": args.visual_understanding, "codex_native_comments": args.native_comments,
                "image_edit": args.image_edit}
    if args.forget and runtime_file().is_file():
        runtime_file().unlink()
    if args.remember:
        save_declared(declared)

    try:
        nature = args.task_nature
        if nature is None and project is not None and (project / "project-state.json").is_file():
            nature = json.loads((project / "project-state.json").read_text(encoding="utf-8")).get("task_nature")
        report = build_report(load_capabilities(args.capabilities, declared), args.task_mode, nature or "persuasive")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Runtime doctor failed: {exc}", file=sys.stderr)
        return 2

    decisions = record_runtime(project, report) if project is not None else {}
    for gap in report["gaps"]:
        gap["decision"] = decisions.get(gap["id"])
    update = update_notice()
    if update is not None:
        report["update"] = update
    memory = project_memory(project) if project is not None else None
    if memory is not None:
        report["proposal_memory"] = memory
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.write:
        output = Path(args.write).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    if args.json:
        print(rendered)
    else:
        if update and update.get("notify"):
            print(f"UPDATE {update['message']}（用大白话转告用户；不要自动更新，用户说要更新再运行 update_skill.py run）")
        print(f"Runtime profile: {report['runtime_profile']}")
        print(f"Task mode: {report['task_mode']}")
        caps = report["capabilities"]
        sources = caps.get("capability_sources") or {}
        label = {"agent": "agent declared", "env": "environment", "saved": "saved on this machine"}
        def show(name: str, value: str, key: str) -> None:
            print(f"{name}: {value}" + (f" ({label[sources[key]]})" if sources.get(key) else ""))
        print(f"Agent host: {caps.get('agent_host')}")
        show("Image generation", caps.get("image_provider") or "none", "image_generation")
        show("Visual understanding", "yes" if caps.get("visual_understanding") else "no", "visual_understanding")
        show("Native browser comments", "yes" if caps.get("codex_native_comments") else "no", "codex_native_comments")
        if report["task_nature"] == "visual_showcase":
            show("Image region edit", "yes" if caps.get("image_edit") else "no", "image_edit")
        for item in report["boundaries"]:
            print(f"BOUNDARY {item}")
        for item in report["blockers"]:
            print(f"BLOCKER {item}")
        open_gaps = [gap for gap in report["gaps"] if not gap.get("decision")]
        for gap in report["gaps"]:
            if gap.get("decision"):
                d = gap["decision"]
                print(f"ACCEPTED {gap['id']}: {d.get('by')} {d.get('at', '')[:10]} {d.get('note', '')}".rstrip())
        if open_gaps:
            print()
            print("先问用户，不要默认降级。逐项问用户能否补齐；补齐后重跑 doctor，"
                  "用户明确选择暂不补齐时运行 doctor.py --project <项目目录> --accept-gap <缺口> --by <Owner> --note <原因>。")
            for gap in open_gaps:
                print(f"GAP {gap['id']}（影响：{'、'.join(gap['blocks'])}）：{gap['question']}")
                for n, option in enumerate(gap["options"], 1):
                    print(f"    {n}. {option}")
        if memory is not None:
            print()
            print(memory["text"], end="")
    return 0


def project_memory(project: Path) -> dict | None:
    """The proposal memory for the project's phase, handed to the agent as part of the start-up check."""
    from proposal_memory import OFF_NOTICE, PHASE_STAGE, memory_enabled, memory_for_phase, write_receipt

    if not memory_enabled():
        return {"enabled": False, "text": OFF_NOTICE + "\n"}
    state_path = project / "project-state.json"
    phase = json.loads(state_path.read_text(encoding="utf-8")).get("phase") if state_path.is_file() else None
    if phase not in PHASE_STAGE:
        return None
    text, digest, count = memory_for_phase(project, phase)
    write_receipt(project, phase, digest, "doctor")
    return {"enabled": True, "phase": phase, "entries": count, "text": text}


if __name__ == "__main__":
    raise SystemExit(main())
