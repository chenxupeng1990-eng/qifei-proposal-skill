#!/usr/bin/env python3
"""Validate the template -> Image2 -> HTML -> validation design loop for one chapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from validate_deck_spec import png_has_alpha


LOOP_STEPS = ["template", "image2", "html", "validate"]
VISUAL_MODES = {"none", "background", "opaque-module", "transparent-png"}
# image_plus_html: a design base with an HTML text layer. image_full: the generator draws the whole page,
# text included; the default for visual_showcase tasks (brand books), an Owner exception elsewhere.
RENDER_ROUTES = {"image_plus_html", "image_full"}
DOMINANT_TYPES = {"information_first", "design_first"}
EXPRESSION_OBJECTS = {
    "data_evidence",
    "comparison",
    "trend",
    "process",
    "system",
    "scene",
    "mechanism",
    "work_artifact",
    "statement",
}
ANCHOR_KINDS = {"html", "image2", "hybrid"}
IMAGE2_DECISIONS = {"generate", "not_generate"}
IMAGE2_SEMANTIC_ROLES = {"scene", "hero", "mechanism", "semantic_icon", "transparent_module", "none"}
VISUAL_ARGUMENT_FIELDS = ("first_glance", "reading_path", "end_focus")
VISUAL_HAMMER_FIELDS = ("primary_object", "supporting_elements", "orphan_element_check")
IMAGE2_DECISION_FIELDS = ("decision", "semantic_role", "reason", "html_protected_content")
# Default page route: a full-page Image2 design base composed with room for the text, HTML layered on top.
BASE_ROLES = {"scene", "hero"}
CANVAS = (1920, 1080)
PRESENTATION_ROUTE_FIELDS = (
    "service_object",
    "use_situation",
    "presentation_task",
    "content_relation",
    "expression_object",
    "best_carrier",
    "dominant_type",
    "anchor_kind",
    "image2_task",
    "html_task",
    "visual_balance_plan",
)
REQUIRED_CHECKS = (
    "manuscript_fidelity",
    "brand_consistency",
    "design_contract",
    "no_overflow",
    "image_html_cohesion",
    "visual_argument_realized",
    "visual_hammer_realized",
    "remote_readability",
    "visual_balance",
    "browser_comments_resolved",
)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def project_file(project: Path, value: object, required_root: str | None = None) -> tuple[Path | None, str | None]:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None, "path is empty"
    relative = PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        return None, f"path must be project-relative without traversal: {raw}"
    resolved = (project / Path(*relative.parts)).resolve()
    project_root = project.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None, f"path escaped project: {raw}"
    if required_root:
        root = (project_root / required_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return None, f"path must stay under {required_root}/: {raw}"
    if not resolved.is_file():
        return None, f"registered file does not exist: {raw}"
    return resolved, None


def owner_exception_ok(page: dict, approvals: dict | None) -> bool:
    """A page may leave the base-image route only with an Owner approval record naming it."""
    exception = page.get("route_exception")
    if not isinstance(exception, dict):
        return False
    record_id = str(exception.get("record_id") or "").strip()
    if not record_id or not str(exception.get("reason") or "").strip():
        return False
    if approvals is None:
        return True
    return any(
        isinstance(item, dict) and item.get("approved") is True and str(item.get("record_id") or "") == record_id
        for item in approvals.values()
    )


def image_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            length = int.from_bytes(data[index + 2:index + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2):
                return int.from_bytes(data[index + 7:index + 9], "big"), int.from_bytes(data[index + 5:index + 7], "big")
            index += 2 + length
    return None


def validate_base_image(path: Path, scope: str) -> list[str]:
    size = image_size(path)
    if size is None:
        return [f"{scope}: design base must be a PNG or JPEG image"]
    width, height = size
    if width < CANVAS[0] or height < CANVAS[1] or abs(width / height - 16 / 9) > 0.02:
        return [f"{scope}: design base is {width}×{height}; it must cover the 16:9 canvas at 1920×1080 or larger"]
    return []


def validate_presentation_route(
    page: dict, scope: str, approvals: dict | None = None, nature: str | None = None
) -> list[str]:
    """Require a page to justify its visual carrier before it can pass review."""
    errors: list[str] = []
    render_route = str(page.get("render_route") or "image_plus_html")
    if render_route not in RENDER_ROUTES:
        errors.append(f"{scope}: render_route must be one of {sorted(RENDER_ROUTES)}")
    elif render_route == "image_full":
        if nature != "visual_showcase" and not owner_exception_ok(page, approvals):
            errors.append(
                f"{scope}: render_route image_full is the visual_showcase route; on a persuasive deck it needs "
                "route_exception with an Owner approval record_id"
            )
        if str(page.get("visual_mode") or "") != "background":
            errors.append(f"{scope}: render_route image_full draws the whole page; visual_mode must be background")
    route = page.get("presentation_route")
    if not isinstance(route, dict):
        return [f"{scope}: presentation_route is required"]

    for field in PRESENTATION_ROUTE_FIELDS:
        if not str(route.get(field) or "").strip():
            errors.append(f"{scope}: presentation_route.{field} is required")

    expression_object = str(route.get("expression_object") or "").strip()
    if expression_object and expression_object not in EXPRESSION_OBJECTS:
        errors.append(
            f"{scope}: presentation_route.expression_object must be one of "
            f"{sorted(EXPRESSION_OBJECTS)}"
        )

    dominant_type = str(route.get("dominant_type") or "").strip()
    if dominant_type and dominant_type not in DOMINANT_TYPES:
        errors.append(
            f"{scope}: presentation_route.dominant_type must be one of {sorted(DOMINANT_TYPES)}"
        )

    anchor_kind = str(route.get("anchor_kind") or "").strip()
    if anchor_kind and anchor_kind not in ANCHOR_KINDS:
        errors.append(
            f"{scope}: presentation_route.anchor_kind must be one of {sorted(ANCHOR_KINDS)}"
        )

    visual_argument = route.get("visual_argument")
    if not isinstance(visual_argument, dict):
        errors.append(f"{scope}: presentation_route.visual_argument is required")
    else:
        for field in VISUAL_ARGUMENT_FIELDS:
            if not str(visual_argument.get(field) or "").strip():
                errors.append(f"{scope}: presentation_route.visual_argument.{field} is required")

    visual_hammer = route.get("visual_hammer")
    if not isinstance(visual_hammer, dict):
        errors.append(f"{scope}: presentation_route.visual_hammer is required")
    else:
        for field in VISUAL_HAMMER_FIELDS:
            if not str(visual_hammer.get(field) or "").strip():
                errors.append(f"{scope}: presentation_route.visual_hammer.{field} is required")

    image2_decision = route.get("image2_decision")
    if not isinstance(image2_decision, dict):
        errors.append(f"{scope}: presentation_route.image2_decision is required")
    else:
        for field in IMAGE2_DECISION_FIELDS:
            if not str(image2_decision.get(field) or "").strip():
                errors.append(f"{scope}: presentation_route.image2_decision.{field} is required")
        decision = str(image2_decision.get("decision") or "").strip()
        semantic_role = str(image2_decision.get("semantic_role") or "").strip()
        if decision and decision not in IMAGE2_DECISIONS:
            errors.append(
                f"{scope}: presentation_route.image2_decision.decision must be one of "
                f"{sorted(IMAGE2_DECISIONS)}"
            )
        if semantic_role and semantic_role not in IMAGE2_SEMANTIC_ROLES:
            errors.append(
                f"{scope}: presentation_route.image2_decision.semantic_role must be one of "
                f"{sorted(IMAGE2_SEMANTIC_ROLES)}"
            )
        if decision == "generate" and semantic_role == "none":
            errors.append(f"{scope}: Image2 generation requires a non-none semantic_role")
        if decision == "generate" and not str(image2_decision.get("visual_family_id") or "").strip():
            errors.append(f"{scope}: Image2 visual_family_id is required")
        if decision == "not_generate" and semantic_role != "none":
            errors.append(f"{scope}: Image2 not_generate requires semantic_role none")
        if decision == "not_generate":
            errors.append(
                f"{scope}: every formal page requires an Image2 asset; "
                "HTML may protect precise content but cannot be the only visual source"
            )
        if semantic_role == "semantic_icon":
            nodes = image2_decision.get("semantic_nodes")
            if not isinstance(nodes, list) or not any(str(node).strip() for node in nodes):
                errors.append(f"{scope}: semantic_icon requires non-empty semantic_nodes")
            if image2_decision.get("text_forbidden") is not True:
                errors.append(f"{scope}: semantic_icon must forbid in-image text")

    visual_mode = str(page.get("visual_mode") or "").strip()
    if visual_mode == "none":
        errors.append(
            f"{scope}: visual_mode none is not allowed for formal proposal pages; "
            "register an Image2 scene, hero, mechanism, semantic icon, or transparent module"
        )
    elif isinstance(image2_decision, dict) and image2_decision.get("decision") != "generate":
        errors.append(f"{scope}: visual assets require Image2 decision generate")

    if visual_mode != "background" and not owner_exception_ok(page, approvals):
        errors.append(
            f"{scope}: formal pages use a full-page Image2 design base (visual_mode background) with HTML "
            "text layered on top; a boxed or inset illustration does not count. Another route needs "
            "route_exception with an Owner approval record_id; DESIGN.md cannot grant it"
        )
    if visual_mode == "background" and isinstance(image2_decision, dict):
        if str(image2_decision.get("semantic_role") or "") not in BASE_ROLES:
            errors.append(f"{scope}: a design base is a scene or hero; semantic_role must be one of {sorted(BASE_ROLES)}")

    return errors


def validate_chapter_report(project: Path, chapter_id: str) -> list[str]:
    errors: list[str] = []
    try:
        state = load_json(project / "project-state.json")
        contracts_doc = load_json(project / "deck" / "slide-contracts.json")
        design_tokens = load_json(project / "deck" / "design-tokens.json")
        asset_manifest = load_json(project / "assets" / "asset-manifest.json")
    except ValueError as exc:
        return [str(exc)]

    chapter = next((item for item in state.get("chapters") or [] if item.get("chapter_id") == chapter_id), None)
    if not isinstance(chapter, dict):
        return [f"Unknown chapter_id: {chapter_id}"]

    report_value = chapter.get("design_loop_report") or f"reviews/design-loop/{chapter_id}.json"
    report_path, report_error = project_file(project, report_value, "reviews/design-loop")
    if report_error:
        return [f"{chapter_id}: design_loop_report {report_error}"]
    try:
        report = load_json(report_path)
    except ValueError as exc:
        return [str(exc)]

    if report.get("chapter_id") != chapter_id:
        errors.append(f"{chapter_id}: report chapter_id does not match")
    if report.get("design_version") != state.get("design_version"):
        errors.append(f"{chapter_id}: report design_version does not match project-state.json")
    if report.get("loop_steps") != LOOP_STEPS:
        errors.append(f"{chapter_id}: loop_steps must be {LOOP_STEPS}")

    chapter_html_value = report.get("chapter_html") or f"deck/chapters/{chapter_id}.html"
    _, chapter_html_error = project_file(project, chapter_html_value, "deck/chapters")
    if chapter_html_error:
        errors.append(f"{chapter_id}: chapter_html {chapter_html_error}")

    contracts = contracts_doc.get("layouts") if isinstance(contracts_doc.get("layouts"), dict) else {}
    alpha_tokens = design_tokens.get("transparent_png") if isinstance(design_tokens.get("transparent_png"), dict) else {}
    design_visual_family = str(design_tokens.get("visual_family_id") or "").strip()
    approved_alpha_dir = str(alpha_tokens.get("approved_dir") or "assets/approved/alpha").strip().rstrip("/") + "/"
    alpha_slots = {
        str(item.get("slot_id"))
        for item in alpha_tokens.get("slots") or []
        if isinstance(item, dict) and item.get("slot_id")
    }
    manifest_assets = asset_manifest.get("assets") if isinstance(asset_manifest.get("assets"), list) else []
    manifest_index = {
        str(item.get("asset_id")): item
        for item in manifest_assets
        if isinstance(item, dict) and item.get("asset_id")
    }

    expected_slides = [str(item) for item in chapter.get("slides") or []]
    pages = report.get("pages") if isinstance(report.get("pages"), list) else []
    seen: list[str] = []
    base_owner: dict[str, str] = {}
    for index, page in enumerate(pages, start=1):
        scope = f"{chapter_id}.pages[{index}]"
        if not isinstance(page, dict):
            errors.append(f"{scope}: expected object")
            continue
        slide_id = str(page.get("slide_id") or "").strip()
        scope = slide_id or scope
        seen.append(slide_id)
        if not slide_id:
            errors.append(f"{scope}: slide_id is required")
        template_id = str(page.get("template_id") or "").strip()
        if template_id not in contracts:
            errors.append(f"{scope}: unknown template_id {template_id!r}")
        if not str(page.get("core_expression") or "").strip():
            errors.append(f"{scope}: core_expression is required before Image2")
        errors.extend(validate_presentation_route(page, scope, state.get("approvals") or {}, state.get("task_nature")))
        if not isinstance(page.get("iterations"), int) or page.get("iterations") < 1:
            errors.append(f"{scope}: iterations must be a positive integer")

        visual_mode = str(page.get("visual_mode") or "").strip()
        if visual_mode not in VISUAL_MODES:
            errors.append(f"{scope}: visual_mode must be one of {sorted(VISUAL_MODES)}")
        visual = page.get("visual") if isinstance(page.get("visual"), dict) else {}
        if visual_mode == "none":
            if not str(page.get("visual_not_required_reason") or "").strip():
                errors.append(f"{scope}: visual_mode none requires visual_not_required_reason")
        elif visual_mode in VISUAL_MODES:
            asset_id = str(visual.get("asset_id") or "").strip()
            asset_path = str(visual.get("asset_path") or "").strip().replace("\\", "/")
            prompt_record = visual.get("prompt_record")
            manifest_item = manifest_index.get(asset_id)
            if not asset_id or not isinstance(manifest_item, dict):
                errors.append(f"{scope}: Image2 asset_id must exist in assets/asset-manifest.json")
            else:
                if manifest_item.get("status") != "approved":
                    errors.append(f"{scope}: Image2 asset {asset_id!r} is not approved")
                if str(manifest_item.get("path") or "").replace("\\", "/") != asset_path:
                    errors.append(f"{scope}: Image2 asset_path does not match asset manifest")
                route = page.get("presentation_route") if isinstance(page.get("presentation_route"), dict) else {}
                decision = route.get("image2_decision") if isinstance(route.get("image2_decision"), dict) else {}
                route_family = str(decision.get("visual_family_id") or "").strip()
                manifest_family = str(manifest_item.get("visual_family_id") or "").strip()
                if not manifest_family:
                    errors.append(f"{scope}: Image2 asset manifest requires visual_family_id")
                elif route_family and manifest_family != route_family:
                    errors.append(f"{scope}: Image2 asset visual_family_id does not match page route")
                if design_visual_family and route_family != design_visual_family:
                    errors.append(f"{scope}: page visual_family_id does not match design-tokens.json")
            asset_file, asset_error = project_file(project, asset_path, "assets")
            if asset_error:
                errors.append(f"{scope}: Image2 asset {asset_error}")
            _, prompt_error = project_file(project, prompt_record, "assets/image2")
            if prompt_error:
                errors.append(f"{scope}: prompt_record {prompt_error}")

            if visual_mode == "background" and asset_file:
                errors.extend(validate_base_image(asset_file, scope))
                if asset_path in base_owner:
                    errors.append(f"{scope}: shares its design base with {base_owner[asset_path]}; each page needs its own carrier")
                base_owner.setdefault(asset_path, scope)
                route = page.get("presentation_route") if isinstance(page.get("presentation_route"), dict) else {}
                decision = route.get("image2_decision") if isinstance(route.get("image2_decision"), dict) else {}
                _, master_error = project_file(project, decision.get("master_reference"), "deck")
                if master_error:
                    errors.append(f"{scope}: image2_decision.master_reference (approved master page used as Image2 reference) {master_error}")
            if visual_mode == "transparent-png" and asset_file:
                slot_id = str(visual.get("slot_id") or "").strip()
                if slot_id not in alpha_slots:
                    errors.append(f"{scope}: transparent PNG requires a known slot_id from design-tokens.json")
                if not asset_path.startswith(approved_alpha_dir):
                    errors.append(f"{scope}: transparent PNG must live under {approved_alpha_dir}")
                if asset_file.suffix.lower() != ".png" or not png_has_alpha(asset_file):
                    errors.append(f"{scope}: transparent PNG must contain a real alpha channel")

        html_output = page.get("html_output") or chapter_html_value
        _, html_error = project_file(project, html_output, "deck/chapters")
        if html_error:
            errors.append(f"{scope}: html_output {html_error}")

        checks = page.get("validation") if isinstance(page.get("validation"), dict) else {}
        for check in REQUIRED_CHECKS:
            if checks.get(check) is not True:
                errors.append(f"{scope}: validation.{check} must pass")
        if page.get("result") != "pass" or page.get("next_action") != "pass":
            errors.append(f"{scope}: latest loop iteration is not closed")

    missing = [slide_id for slide_id in expected_slides if slide_id not in seen]
    unexpected = [slide_id for slide_id in seen if slide_id not in expected_slides]
    if missing:
        errors.append(f"{chapter_id}: design loop report is missing slides: {', '.join(missing)}")
    if unexpected:
        errors.append(f"{chapter_id}: design loop report contains unexpected slides: {', '.join(unexpected)}")
    if len(seen) != len(set(seen)):
        errors.append(f"{chapter_id}: design loop report contains duplicate slide ids")

    if report.get("status") != "passed":
        errors.append(f"{chapter_id}: design loop report status must be passed")
    if not str(report.get("approved_by") or "").strip() or not str(report.get("approval_record_id") or "").strip():
        errors.append(f"{chapter_id}: passed design loop requires approval metadata")
    if str(chapter.get("design_loop_record_id") or "") != str(report.get("approval_record_id") or ""):
        errors.append(f"{chapter_id}: chapter design_loop_record_id does not match report approval")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--chapter-id", required=True)
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    errors = validate_chapter_report(project, args.chapter_id)
    if errors:
        print("Design loop validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Design loop valid: {args.chapter_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
