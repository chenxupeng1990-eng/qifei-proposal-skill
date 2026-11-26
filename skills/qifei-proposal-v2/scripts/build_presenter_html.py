#!/usr/bin/env python3
"""Build a standalone, zero-dependency offline Presenter HTML deck for qifei-proposal-v2.

Features:
- Single-language (zh or en) or bilingual (zh,en) mode with instant 'L' toggle
- Optional inline speaker-notes editor (auto-saved to localStorage; export HTML / MD / JSON)
- Dual-Screen Presenter Mode: pure full-screen Audience Window on projector + Presenter Console
  (current slide preview, next-slide preview, timer, large-type script, remote replay/blackout)
  working 100% offline over file:// via window.open + postMessage
- Subtle chapter-aware slide transitions (220ms intra-chapter, 320ms cross-chapter)
- Motion-plan pacing checker (--check-motion-plan) flagging >=12 warning / >=20 consecutive static slides
- Optional motion plugin injection (--motion-css / --motion-dom / --motion-js)
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any


def encode_image_data_uri(img_path: pathlib.Path, webp_quality: int = 84) -> str:
    ext = img_path.suffix.lower()
    if ext == ".webp":
        return "data:image/webp;base64," + base64.b64encode(img_path.read_bytes()).decode("ascii")
    if ext in (".png", ".jpg", ".jpeg") and shutil.which("cwebp"):
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tf:
            tmp_webp = pathlib.Path(tf.name)
        try:
            subprocess.run(
                ["cwebp", "-quiet", "-q", str(webp_quality), "-m", "4", str(img_path), "-o", str(tmp_webp)],
                check=True,
            )
            return "data:image/webp;base64," + base64.b64encode(tmp_webp.read_bytes()).decode("ascii")
        finally:
            tmp_webp.unlink(missing_ok=True)
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(img_path.read_bytes()).decode("ascii")


def analyze_motion_pacing(slide_ids: list[str], motion_plan: dict[str, Any]) -> dict[str, Any]:
    """Check consecutive static-slide gaps against the >=12 warn / >=20 required pacing guardrail."""
    active_ids: set[str] = set()
    for item in motion_plan.get("slides", []):
        sid = item.get("slide_id")
        tier = str(item.get("tier", "none")).lower()
        if sid and tier not in ("none", "static", ""):
            active_ids.add(sid)

    runs: list[dict[str, Any]] = []
    cur_start: int | None = None
    for idx, sid in enumerate(slide_ids):
        if sid not in active_ids:
            if cur_start is None:
                cur_start = idx
        else:
            if cur_start is not None:
                runs.append({
                    "start_idx": cur_start + 1,
                    "end_idx": idx,
                    "start_id": slide_ids[cur_start],
                    "end_id": slide_ids[idx - 1],
                    "length": idx - cur_start,
                })
                cur_start = None
    if cur_start is not None:
        runs.append({
            "start_idx": cur_start + 1,
            "end_idx": len(slide_ids),
            "start_id": slide_ids[cur_start],
            "end_id": slide_ids[-1],
            "length": len(slide_ids) - cur_start,
        })

    max_run = max((r["length"] for r in runs), default=0)
    warnings = [r for r in runs if 12 <= r["length"] < 20]
    violations = [r for r in runs if r["length"] >= 20]
    return {
        "total_slides": len(slide_ids),
        "motion_slides": len(active_ids & set(slide_ids)),
        "max_static_run": max_run,
        "warnings_12_to_19": warnings,
        "violations_ge_20": violations,
        "status": "FAIL_PACING_GAP" if violations else ("WARN_PACING_GAP" if warnings else "PASS"),
    }


def collect_slides(
    slides_manifest: list[dict[str, Any]],
    langs: list[str],
    webp_quality: int = 84,
) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for num, raw in enumerate(slides_manifest, 1):
        entry: dict[str, Any] = {
            "id": raw["slide_id"],
            "num": num,
            "ch_id": raw.get("ch_id", "CH01"),
            "ch_zh": raw.get("ch_zh", raw.get("chapter", "")),
            "ch_en": raw.get("ch_en", raw.get("chapter", "")),
            "title_zh": raw.get("title_zh", raw.get("title", "")),
            "title_en": raw.get("title_en", raw.get("title", "")),
            "duration": int(raw.get("duration", 60) or 60),
            "kp_zh": raw.get("kp_zh", ""),
            "kp_en": raw.get("kp_en", ""),
            "note_zh": raw.get("note_zh", ""),
            "note_en": raw.get("note_en", ""),
        }
        if "zh" in langs:
            p_zh = pathlib.Path(raw["img_zh"])
            entry["img_zh"] = encode_image_data_uri(p_zh, webp_quality)
        if "en" in langs:
            p_en = pathlib.Path(raw.get("img_en") or raw["img_zh"])
            entry["img_en"] = encode_image_data_uri(p_en, webp_quality)
        slides.append(entry)
    return slides


def build_html(
    *,
    brand_name: str,
    subtitle: str,
    chapters: list[list[Any]],
    slides: list[dict[str, Any]],
    langs: list[str],
    editable_notes: bool = True,
    motion_css: str = "",
    motion_dom: str = "",
    motion_js: str = "",
    storage_key: str = "qifei_presenter_notes_v1",
) -> str:
    bilingual = len(langs) > 1
    default_lang = langs[0]
    has_motion = bool(motion_js.strip() or motion_dom.strip())
    data_json = json.dumps(
        {
            "brand": brand_name,
            "langs": langs,
            "editable_notes": editable_notes,
            "has_motion": has_motion,
            "chapters": chapters,
            "slides": slides,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    lang_seg_html = (
        '<div class="seg" role="group" aria-label="切换语言">'
        '<button type="button" data-lang="zh" class="active">中文</button>'
        '<button type="button" data-lang="en">EN</button>'
        '</div>'
        if bilingual
        else ""
    )
    motion_btn_html = (
        '<button type="button" class="btn active" id="btn-motion" title="开关沉浸动效 (V)">沉浸动效: 开</button>'
        if has_motion
        else ""
    )
    nmode_html = (
        '<div class="seg" role="group" aria-label="讲稿显示模式">'
        '<button type="button" data-nmode="both" class="active">双语</button>'
        '<button type="button" data-nmode="zh">中</button>'
        '<button type="button" data-nmode="en">EN</button>'
        '</div>'
        if bilingual
        else ""
    )
    edit_btn_html = (
        '<button type="button" class="btn sm" id="btn-edit" title="编辑当前页讲稿 (E)">编辑讲稿</button>'
        if editable_notes
        else ""
    )
    toolbar_html = (
        '<div class="notes-toolbar" id="notes-toolbar">'
        '  <span class="edit-status" id="edit-status">本机自动保存</span>'
        '  <button type="button" class="btn sm primary" id="btn-save-html" title="将修改打包为新的单文件离线 HTML">存为新 HTML</button>'
        '  <button type="button" class="btn sm" id="btn-export-md" title="导出最新讲稿为 Markdown">导出 MD</button>'
        '  <button type="button" class="btn sm ghost" id="btn-export-json" title="导出讲稿 JSON">JSON</button>'
        '  <button type="button" class="btn sm ghost" id="btn-import-json" title="从 JSON 导入讲稿">导入</button>'
        '  <input type="file" id="file-import-json" accept="application/json,.json" hidden>'
        '</div>'
        if editable_notes
        else ""
    )

    hint_parts = ["← → 翻页"]
    if bilingual:
        hint_parts.append("L 中/英")
    if has_motion:
        hint_parts.append("R 重播动效")
    if editable_notes:
        hint_parts.append("E 编辑")
    hint_parts.append("F 全屏 · B 黑屏")
    hint_text = " · ".join(hint_parts)

    return f"""<!doctype html>
<html lang="{ 'zh-CN' if default_lang == 'zh' else 'en' }" translate="no" class="notranslate">
<head>
<meta charset="utf-8">
<meta name="google" content="notranslate">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand_name} · 离线讲解台（{len(slides)} 页）</title>
<style>
:root {{
  --bg: #f4f3ef;
  --surface: #ffffff;
  --ink: #181a18;
  --muted: #5d635e;
  --line: rgba(24,26,24,.10);
  --accent: #2f3a34;
  --accent-soft: rgba(47,58,52,.08);
  --edit-bg: #faf9f5;
  --bar-h: 56px;
  --nav-w: 268px;
  --notes-w: 460px;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; height: 100%; background: var(--bg); color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", "PingFang SC", "Noto Sans SC", Inter, Arial, sans-serif; overflow: hidden; }}
.topbar {{
  height: var(--bar-h); background: var(--surface); border-bottom: 1px solid var(--line);
  display: flex; align-items: center; padding: 0 16px; gap: 10px; position: relative; z-index: 20;
}}
.brand {{ display: flex; align-items: baseline; gap: 10px; min-width: 0; }}
.brand-name {{ font-weight: 600; letter-spacing: .16em; font-size: 13.5px; color: var(--accent); white-space: nowrap; }}
.brand-sub {{ font-size: 12.5px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.spacer {{ flex: 1; }}
.seg {{ display: inline-flex; border: 1px solid rgba(24,26,24,.16); border-radius: 999px; overflow: hidden; background: #faf9f6; }}
.seg button {{ border: 0; background: transparent; padding: 4px 11px; font-size: 12px; font-weight: 500; color: #555; cursor: pointer; transition: .15s; }}
.seg button.active {{ background: var(--accent); color: #fff; }}
.btn {{
  border: 1px solid rgba(24,26,24,.16); background: var(--surface); color: var(--ink);
  border-radius: 999px; padding: 5px 12px; font-size: 12.5px; font-weight: 500; cursor: pointer;
  display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; transition: .15s;
}}
.btn:hover {{ background: #f0efe9; }}
.btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.btn.sm {{ padding: 4px 10px; font-size: 12px; }}
.btn.primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.btn.ghost {{ border-color: transparent; background: transparent; color: var(--muted); }}
.btn:disabled {{ opacity: .35; cursor: not-allowed; }}

.workspace {{ display: flex; height: calc(100vh - var(--bar-h)); overflow: hidden; }}
.sidebar {{
  width: var(--nav-w); background: var(--surface); border-right: 1px solid var(--line);
  display: flex; flex-direction: column; flex-shrink: 0; overflow: hidden; transition: width .18s ease;
}}
.sidebar.collapsed {{ width: 0; border-right: 0; }}
.sidebar-head {{ padding: 12px 14px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--muted); }}
.sidebar-list {{ flex: 1; overflow-y: auto; padding: 8px; }}
.ch-group {{ margin-bottom: 10px; }}
.ch-title {{ font-size: 11px; font-weight: 600; letter-spacing: .04em; color: var(--accent); padding: 6px 8px 4px; text-transform: uppercase; }}
.slide-item {{
  width: 100%; border: 0; background: transparent; text-align: left; padding: 7px 9px;
  border-radius: 6px; cursor: pointer; display: flex; gap: 8px; align-items: baseline; color: var(--ink); font-size: 12.5px; line-height: 1.35; position: relative;
}}
.slide-item:hover {{ background: var(--accent-soft); }}
.slide-item.active {{ background: var(--accent); color: #fff; }}
.slide-item .sid {{ font-variant-numeric: tabular-nums; font-weight: 600; font-size: 11.5px; opacity: .75; flex-shrink: 0; width: 32px; }}
.slide-item.active .sid {{ opacity: 1; }}
.slide-item .stitle {{ overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; flex: 1; }}
.slide-item .edot {{ width: 6px; height: 6px; border-radius: 50%; background: #c07a28; flex-shrink: 0; align-self: center; }}

.stage-col {{ flex: 1; display: flex; flex-direction: column; min-width: 0; padding: 14px 20px 16px; position: relative; }}
.stage-meta {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 13px; color: var(--muted); min-height: 24px; }}
.stage-meta strong {{ color: var(--ink); font-weight: 600; }}
.stage-meta .ch-tag {{ font-size: 11.5px; padding: 2px 8px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); white-space: nowrap; flex-shrink: 0; }}
.stage-meta .hint {{ margin-left: auto; font-size: 12px; color: #7a807b; white-space: nowrap; flex-shrink: 0; }}

.canvas-wrap {{ flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; position: relative; }}
.slide-frame {{
  position: relative; max-width: 100%; max-height: 100%; aspect-ratio: 16 / 9;
  background: #f4f3ef; border-radius: 6px; box-shadow: 0 12px 38px rgba(20,24,21,.10); overflow: hidden;
  border: 1px solid rgba(20,20,20,.08);
}}
.slide-frame img#slide-img {{
  width: 100%; height: 100%; object-fit: contain; display: block; user-select: none;
  transition: opacity .22s ease, transform .26s cubic-bezier(.22,1,.36,1);
}}
.slide-frame img#slide-img.swapping {{ opacity: .18; }}
.slide-frame img#slide-img.swapping-ch {{ opacity: .05; transform: scale(.992); transition-duration: .32s; }}

.stage-foot {{ display: flex; align-items: center; gap: 12px; margin-top: 12px; }}
.progress-track {{ flex: 1; height: 4px; background: rgba(24,26,24,.10); border-radius: 999px; overflow: hidden; cursor: pointer; }}
.progress-fill {{ height: 100%; background: var(--accent); width: 0%; transition: width .15s; }}
.page-counter {{ font-size: 12.5px; font-variant-numeric: tabular-nums; color: var(--muted); min-width: 64px; text-align: center; }}

.notes-pane {{
  width: var(--notes-w); background: var(--surface); border-left: 1px solid var(--line);
  display: flex; flex-direction: column; flex-shrink: 0; overflow: hidden; transition: width .18s ease;
}}
.notes-pane.collapsed {{ width: 0; border-left: 0; }}
.notes-head {{ padding: 10px 14px; border-bottom: 1px solid var(--line); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
.notes-head-title {{ font-size: 13px; font-weight: 600; color: var(--accent); }}
.notes-dur {{ font-size: 11.5px; color: var(--muted); background: var(--accent-soft); padding: 2px 8px; border-radius: 999px; }}
.notes-toolbar {{ padding: 8px 14px; border-bottom: 1px solid var(--line); background: #faf9f6; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 12px; }}
.edit-status {{ font-size: 11.5px; color: #3a6b48; margin-right: auto; }}
.edit-badge {{ font-size: 11px; padding: 2px 7px; border-radius: 999px; background: rgba(192,122,40,.14); color: #8c5514; font-weight: 600; }}
.edit-badge[hidden] {{ display: none; }}
.notes-body {{ flex: 1; overflow-y: auto; padding: 14px 16px 28px; }}
.kp-box {{ background: #f6f5f0; border-left: 3px solid var(--accent); padding: 10px 12px; border-radius: 4px; margin-bottom: 16px; font-size: 13px; line-height: 1.55; }}
.kp-label {{ font-size: 11px; font-weight: 600; letter-spacing: .06em; color: var(--accent); text-transform: uppercase; margin-bottom: 4px; }}
.script-block {{ margin-bottom: 20px; }}
.script-lang {{ font-size: 11px; font-weight: 600; letter-spacing: .08em; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }}
.script-lang::after {{ content: ""; flex: 1; height: 1px; background: var(--line); }}
.script-text p {{ margin: 0 0 11px; font-size: 14px; line-height: 1.72; color: #222522; }}
.script-text.en p {{ font-size: 13.7px; line-height: 1.66; color: #272b28; }}
.ed-group {{ margin-bottom: 14px; }}
.ed-label {{ display: flex; align-items: center; justify-content: space-between; font-size: 11.5px; font-weight: 600; color: var(--accent); margin-bottom: 5px; }}
.ed-input, .ed-textarea {{ width: 100%; border: 1px solid rgba(24,26,24,.18); border-radius: 6px; padding: 9px 11px; background: var(--edit-bg); color: var(--ink); font-family: inherit; font-size: 13.5px; line-height: 1.64; }}
.ed-textarea {{ resize: vertical; min-height: 140px; }}
.ed-textarea.sm {{ min-height: 60px; font-size: 13px; }}
.ed-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }}
.ed-dur {{ width: 84px; padding: 5px 8px; font-size: 13px; }}
.ed-actions {{ display: flex; gap: 8px; flex-wrap: wrap; padding-top: 8px; border-top: 1px solid var(--line); margin-top: 12px; }}

.toast {{
  position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%) translateY(16px);
  background: rgba(24,28,25,.92); color: #fff; font-size: 13px; padding: 9px 16px; border-radius: 999px;
  opacity: 0; pointer-events: none; transition: opacity .18s, transform .18s; z-index: 80;
}}
.toast.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}

/* Fullscreen mode */
body.is-fs .topbar, body.is-fs .sidebar, body.is-fs .notes-pane {{ display: none; }}
body.is-fs .workspace {{ height: 100vh; }}
body.is-fs .stage-col {{ background: #141615; padding: 14px 20px; }}
body.is-fs .stage-meta {{ color: rgba(255,255,255,.72); }}
body.is-fs .stage-meta strong {{ color: #fff; }}
body.is-fs .stage-meta .ch-tag {{ background: rgba(255,255,255,.12); color: #e2e8e4; }}
.btn-exit-fs {{ display: none; }}
body.is-fs .btn-exit-fs {{ display: inline-flex; margin-left: 10px; background: rgba(255,255,255,.14); border-color: rgba(255,255,255,.28); color: #fff; }}

/* Blackout curtain ('B') */
.blackout-curtain {{
  position: fixed; inset: 0; background: #000; z-index: 95;
  opacity: 0; visibility: hidden; pointer-events: none; transition: opacity .25s ease;
}}
body.is-blackout .blackout-curtain {{ opacity: 1; visibility: visible; pointer-events: auto; }}

/* === DUAL-SCREEN AUDIENCE STAGE MODE (#audience) === */
body.is-audience .topbar,
body.is-audience .sidebar,
body.is-audience .notes-pane,
body.is-audience .stage-meta,
body.is-audience .stage-foot,
body.is-audience .presenter-bar,
body.is-audience .next-preview-box {{ display: none !important; }}
body.is-audience .workspace {{ height: 100vh; background: #000; }}
body.is-audience .stage-col {{ padding: 0; background: #000; }}
body.is-audience .slide-frame {{ border-radius: 0; border: 0; box-shadow: none; width: 100vw; max-width: 100vw; max-height: 100vh; }}
.aud-float-bar {{
  display: none; position: fixed; top: 14px; left: 50%; transform: translateX(-50%); z-index: 90;
  background: rgba(20,24,22,.82); backdrop-filter: blur(12px); color: #fff;
  border: 1px solid rgba(255,255,255,.18); border-radius: 999px; padding: 7px 16px;
  font-size: 13px; align-items: center; gap: 12px; opacity: 0; transition: opacity .25s ease;
}}
body.is-audience .aud-float-bar {{ display: inline-flex; }}
body.is-audience.aud-ui-show .aud-float-bar,
body.is-audience .aud-float-bar:hover {{ opacity: 1; }}
.aud-float-bar button {{
  background: #fff; color: #181a18; border: 0; border-radius: 999px; padding: 4px 12px; font-size: 12px; font-weight: 600; cursor: pointer;
}}

/* === DUAL-SCREEN PRESENTER CONSOLE MODE (laptop while projector shows Audience) === */
.presenter-bar {{
  display: none; align-items: center; gap: 10px; padding: 8px 14px;
  background: #1f2723; color: #f4f3ef; border-bottom: 1px solid rgba(255,255,255,.1); font-size: 12.5px;
}}
body.is-presenter .presenter-bar {{ display: flex; }}
body.is-presenter .workspace {{ height: calc(100vh - var(--bar-h) - 44px); }}
body.is-presenter .sidebar {{ width: 0; border-right: 0; }}
body.is-presenter .stage-col {{ flex: 0 0 43%; background: #181d1a; color: #e8ece9; padding: 12px 16px; }}
body.is-presenter .stage-meta {{ color: rgba(255,255,255,.72); }}
body.is-presenter .stage-meta strong {{ color: #fff; }}
body.is-presenter .stage-meta .hint {{ display: none; }}
body.is-presenter .page-counter {{ color: rgba(255,255,255,.76); }}
body.is-presenter .notes-pane {{ flex: 1; width: auto; background: #fcfbf8; }}
body.is-presenter .notes-pane.collapsed {{ width: auto; flex: 1; }}
body.is-presenter .script-text p {{ font-size: 17.5px; line-height: 1.78; }}
body.is-presenter .script-text.en p {{ font-size: 16.5px; line-height: 1.72; }}
body.is-presenter .kp-box {{ font-size: 15px; }}
.p-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #52c47a; display: inline-block; }}
.p-timer {{ font-variant-numeric: tabular-nums; font-weight: 600; font-size: 14px; padding: 2px 10px; border-radius: 999px; background: rgba(255,255,255,.12); }}
.p-btn {{
  background: rgba(255,255,255,.12); color: #fff; border: 1px solid rgba(255,255,255,.22);
  border-radius: 999px; padding: 4px 11px; font-size: 12px; cursor: pointer;
}}
.p-btn:hover {{ background: rgba(255,255,255,.24); }}
.p-btn.warn {{ background: #b43c3c; border-color: #c95252; }}
.next-preview-box {{
  display: none; margin-top: 10px; padding: 10px 12px; border-radius: 8px;
  background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12);
  align-items: center; gap: 12px;
}}
body.is-presenter .next-preview-box {{ display: flex; }}
.next-preview-thumb {{ width: 156px; aspect-ratio: 16/9; border-radius: 4px; overflow: hidden; background: #2c312e; flex-shrink: 0; }}
.next-preview-thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.next-preview-meta {{ min-width: 0; font-size: 12.5px; color: rgba(255,255,255,.86); }}
.next-preview-lbl {{ font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: #9ec0a8; margin-bottom: 4px; }}
{motion_css}
</style>
</head>
<body>
<div class="blackout-curtain" id="blackout-curtain" title="按 B 恢复画面"></div>
<div class="aud-float-bar" id="aud-float-bar">
  <span>观众大屏窗口 · 拖至外接屏后点击全屏</span>
  <button type="button" id="aud-btn-fs">进入全屏 (F)</button>
</div>
<header class="topbar">
  <div class="brand">
    <span class="brand-name">{brand_name}</span>
    <span class="brand-sub" id="top-sub">{subtitle}</span>
  </div>
  <div class="spacer"></div>
  <button type="button" class="btn active" id="btn-nav" title="显示/隐藏目录 (M)">目录</button>
  {lang_seg_html}
  <button type="button" class="btn active" id="btn-notes" title="显示/隐藏讲稿 (N)">讲稿</button>
  {motion_btn_html}
  <button type="button" class="btn" id="btn-dual" title="投屏双屏演示：大屏全屏画面，本机显示讲稿与下一页预告">双屏演示</button>
  <button type="button" class="btn" id="btn-fs" title="全屏演示 (F)">全屏</button>
</header>
<div class="presenter-bar" id="presenter-bar">
  <span class="p-dot"></span>
  <strong>双屏演讲者控制台</strong>
  <span class="p-timer" id="p-timer">00:00</span>
  <button type="button" class="p-btn" id="p-timer-reset">计时归零</button>
  <span class="spacer"></span>
  <button type="button" class="p-btn" id="p-remote-replay" title="远程重播大屏当前页动效 (R)">↺ 重播大屏动效</button>
  <button type="button" class="p-btn" id="p-remote-blackout" title="大屏黑屏/恢复 (B)">⬛ 黑屏</button>
  <button type="button" class="p-btn warn" id="p-close-dual">结束双屏</button>
</div>
<div class="workspace">
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-head">
      <span id="nav-label">{len(chapters)} 章 · {len(slides)} 页</span>
      <span class="edit-badge" id="edited-count" hidden>已改 0 页</span>
    </div>
    <div class="sidebar-list" id="nav-list"></div>
  </aside>
  <main class="stage-col">
    <div class="stage-meta">
      <strong id="meta-sid">{slides[0]['id'] if slides else 'P01'}</strong>
      <span class="ch-tag" id="meta-ch"></span>
      <span id="meta-title" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span>
      <span class="hint">{hint_text}</span>
      <button type="button" class="btn sm btn-exit-fs" id="btn-exit-fs" title="退出全屏并返回讲稿视图 (F)">退出全屏 · 看讲稿</button>
    </div>
    <div class="canvas-wrap">
      <div class="slide-frame">
        <img id="slide-img" alt="" draggable="false">
        {motion_dom}
      </div>
    </div>
    <div class="next-preview-box" id="next-preview-box">
      <div class="next-preview-thumb"><img id="next-thumb-img" alt=""></div>
      <div class="next-preview-meta">
        <div class="next-preview-lbl">NEXT SLIDE · 下一页预告</div>
        <div id="next-preview-title"></div>
      </div>
    </div>
    <div class="stage-foot">
      <button type="button" class="btn" id="btn-prev">← 上一页</button>
      <span class="page-counter" id="page-counter">1 / {len(slides)}</span>
      <div class="progress-track" id="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
      <button type="button" class="btn" id="btn-next">下一页 →</button>
    </div>
  </main>
  <aside class="notes-pane" id="notes-pane">
    <div class="notes-head">
      <span class="notes-head-title">演讲讲稿 · Speaker Notes</span>
      <span class="notes-dur" id="notes-dur">~60s</span>
      <div class="spacer"></div>
      {nmode_html}
      {edit_btn_html}
    </div>
    {toolbar_html}
    <div class="notes-body" id="notes-body"></div>
  </aside>
</div>
<div class="toast" id="toast"></div>

<script type="application/json" id="deck-data">{data_json}</script>
<script>
(() => {{
  "use strict";
  const STORAGE_KEY = "{storage_key}";
  const DATA = JSON.parse(document.getElementById("deck-data").textContent);
  const slides = DATA.slides;
  const chapters = DATA.chapters;
  const langs = DATA.langs || ["zh"];
  const editableNotes = Boolean(DATA.editable_notes);
  const isAudience =
    new URLSearchParams(location.search).get("audience") === "1" ||
    location.hash.startsWith("#audience") ||
    window.name === "qifei_audience_stage";
  const defaults = slides.map(s => ({{ duration: s.duration, kp_zh: s.kp_zh, kp_en: s.kp_en, note_zh: s.note_zh, note_en: s.note_en }}));
  const $ = id => document.getElementById(id);

  let idx = 0;
  let lang = langs[0] || "zh";
  let noteMode = langs.length > 1 ? "both" : lang;
  let isEditing = false;
  let edits = {{}};
  let lastChId = "";
  let audWin = null;
  let blackout = false;
  let timerSec = 0;
  let timerHandle = 0;

  if (isAudience) {{
    document.body.classList.add("is-audience", "aud-ui-show");
    let hideT = setTimeout(() => document.body.classList.remove("aud-ui-show"), 4500);
    document.addEventListener("mousemove", () => {{
      document.body.classList.add("aud-ui-show");
      clearTimeout(hideT);
      hideT = setTimeout(() => document.body.classList.remove("aud-ui-show"), 2400);
    }});
    $("aud-btn-fs")?.addEventListener("click", () => document.documentElement.requestFullscreen?.());
  }}

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({{ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }}[c]));
  const toParas = txt => String(txt || "").split(/\\n+/).filter(Boolean).map(p => `<p>${{esc(p)}}</p>`).join("");
  const fmtTime = sec => `${{String(Math.floor(sec/60)).padStart(2,"0")}}:${{String(sec%60).padStart(2,"0")}}`;

  function toast(msg) {{
    if (isAudience) return;
    const el = $("toast");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.remove("show"), 2500);
  }}

  function postToAudience(payload) {{
    if (isAudience || !audWin || audWin.closed) return;
    try {{ audWin.postMessage({{ __qifeiDual: true, ...payload }}, "*"); }} catch (_) {{}}
  }}
  function postToOpener(payload) {{
    if (!isAudience || !window.opener || window.opener.closed) return;
    try {{ window.opener.postMessage({{ __qifeiDual: true, ...payload }}, "*"); }} catch (_) {{}}
  }}

  function loadEdits() {{
    if (!editableNotes) return;
    try {{
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && typeof saved === "object") {{
        edits = saved;
        slides.forEach(s => {{
          const e = edits[s.id];
          if (e) Object.assign(s, e);
        }});
      }}
    }} catch (_) {{}}
  }}
  function persistEdits() {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(edits)); }} catch (_) {{}}
    updateEditedBadge();
  }}
  function isSlideEdited(s, i) {{
    const d = defaults[i];
    return s.kp_zh !== d.kp_zh || s.kp_en !== d.kp_en || s.note_zh !== d.note_zh || s.note_en !== d.note_en || Number(s.duration) !== Number(d.duration);
  }}
  function updateEditedBadge() {{
    const badge = $("edited-count");
    if (!badge) return;
    const count = slides.filter((s, i) => isSlideEdited(s, i)).length;
    badge.hidden = count === 0;
    badge.textContent = `已改 ${{count}} 页`;
  }}

  function readHash() {{
    let h = decodeURIComponent((location.hash || "").replace(/^#/, "")).trim();
    if (h.startsWith("audience:")) h = h.slice("audience:".length);
    if (!h || h === "audience") return;
    const found = slides.findIndex(s => s.id.toLowerCase() === h.toLowerCase());
    if (found >= 0) idx = found;
  }}

  function buildNav() {{
    const html = chapters.map(([cid, chZh, chEn, start, end]) => {{
      const items = slides.filter(s => s.num >= start && s.num <= end).map(s => {{
        const i = s.num - 1;
        const title = lang === "zh" ? s.title_zh : s.title_en;
        return `<button type="button" class="slide-item${{i === idx ? " active" : ""}}" data-idx="${{i}}"><span class="sid">${{s.id}}</span><span class="stitle">${{esc(title)}}</span></button>`;
      }}).join("");
      return `<div class="ch-group"><div class="ch-title">${{esc(lang === "zh" ? chZh : chEn)}}</div>${{items}}</div>`;
    }}).join("");
    $("nav-list").innerHTML = html;
    updateEditedBadge();
  }}

  function renderNotes(s) {{
    if (isAudience) return;
    $("notes-dur").textContent = `~${{s.duration || 60}}s`;
    if ($("btn-edit")) {{
      $("btn-edit").classList.toggle("active", isEditing);
      $("btn-edit").textContent = isEditing ? "完成编辑" : "编辑讲稿";
    }}
    if (isEditing && editableNotes) {{
      const showZh = noteMode !== "en" && langs.includes("zh");
      const showEn = noteMode !== "zh" && langs.includes("en");
      $("notes-body").innerHTML = `
        <div class="ed-row"><label style="font-size:12px;color:var(--muted);font-weight:600">建议时长(秒)</label><input type="number" min="10" max="600" step="5" id="ed-dur" class="ed-input ed-dur" value="${{Number(s.duration || 60)}}"></div>
        ${{showZh ? `<div class="ed-group"><div class="ed-label"><span>中文核心要点</span></div><textarea id="ed-kp-zh" class="ed-textarea sm">${{esc(s.kp_zh)}}</textarea></div><div class="ed-group"><div class="ed-label"><span>中文讲稿</span></div><textarea id="ed-note-zh" class="ed-textarea">${{esc(s.note_zh)}}</textarea></div>` : ""}}
        ${{showEn ? `<div class="ed-group"><div class="ed-label"><span>English Takeaway</span></div><textarea id="ed-kp-en" class="ed-textarea sm">${{esc(s.kp_en)}}</textarea></div><div class="ed-group"><div class="ed-label"><span>English Script</span></div><textarea id="ed-note-en" class="ed-textarea">${{esc(s.note_en)}}</textarea></div>` : ""}}
        <div class="ed-actions"><button type="button" class="btn sm primary" id="ed-done">完成编辑</button><button type="button" class="btn sm" id="ed-reset">还原本页</button></div>`;
      ["ed-dur","ed-kp-zh","ed-note-zh","ed-kp-en","ed-note-en"].forEach(id => $(id)?.addEventListener("input", () => {{
        if ($("ed-dur")) s.duration = Math.max(10, Math.min(600, Number($("ed-dur").value) || 60));
        if ($("ed-kp-zh")) s.kp_zh = $("ed-kp-zh").value;
        if ($("ed-note-zh")) s.note_zh = $("ed-note-zh").value;
        if ($("ed-kp-en")) s.kp_en = $("ed-kp-en").value;
        if ($("ed-note-en")) s.note_en = $("ed-note-en").value;
        edits[s.id] = {{ duration: s.duration, kp_zh: s.kp_zh, kp_en: s.kp_en, note_zh: s.note_zh, note_en: s.note_en }};
        persistEdits();
      }}));
      $("ed-done")?.addEventListener("click", () => {{ isEditing = false; renderNotes(s); }});
      $("ed-reset")?.addEventListener("click", () => {{ Object.assign(s, defaults[idx]); delete edits[s.id]; persistEdits(); renderNotes(s); toast(`已还原 ${{s.id}}`); }});
      return;
    }}
    let html = "";
    if (s.kp_zh || s.kp_en) {{
      const lines = [];
      if (noteMode !== "en" && s.kp_zh) lines.push(`<div><strong>核心要点：</strong>${{esc(s.kp_zh)}}</div>`);
      if (noteMode !== "zh" && s.kp_en) lines.push(`<div style="margin-top:4px;color:#3d443f"><strong>Takeaway:</strong> ${{esc(s.kp_en)}}</div>`);
      if (lines.length) html += `<div class="kp-box"><div class="kp-label">KEY POINT</div>${{lines.join("")}}</div>`;
    }}
    if (noteMode !== "en" && langs.includes("zh")) html += `<div class="script-block"><div class="script-lang">中文讲稿</div><div class="script-text zh">${{toParas(s.note_zh) || "<p>暂无讲稿</p>"}}</div></div>`;
    if (noteMode !== "zh" && langs.includes("en")) html += `<div class="script-block"><div class="script-lang">English Script</div><div class="script-text en">${{toParas(s.note_en) || "<p>No script.</p>"}}</div></div>`;
    $("notes-body").innerHTML = html;
    $("notes-body").scrollTop = 0;
  }}

  function render(fromSync = false) {{
    const s = slides[idx];
    const imgEl = $("slide-img");
    const crossCh = Boolean(lastChId && lastChId !== s.ch_id);
    const swapCls = crossCh ? "swapping-ch" : "swapping";
    imgEl.classList.add(swapCls);
    requestAnimationFrame(() => {{
      imgEl.src = lang === "zh" ? (s.img_zh || s.img_en) : (s.img_en || s.img_zh);
      requestAnimationFrame(() => imgEl.classList.remove("swapping", "swapping-ch"));
    }});
    lastChId = s.ch_id;

    $("meta-sid").textContent = s.id;
    $("meta-ch").textContent = lang === "zh" ? s.ch_zh : s.ch_en;
    $("meta-title").textContent = lang === "zh" ? s.title_zh : s.title_en;
    $("page-counter").textContent = `${{idx + 1}} / ${{slides.length}}`;
    $("progress-fill").style.width = `${{((idx + 1) / slides.length) * 100}}%`;
    $("btn-prev").disabled = idx === 0;
    $("btn-next").disabled = idx === slides.length - 1;
    document.querySelectorAll("[data-lang]").forEach(b => b.classList.toggle("active", b.dataset.lang === lang));
    document.querySelectorAll(".slide-item").forEach(b => {{
      const active = Number(b.dataset.idx) === idx;
      b.classList.toggle("active", active);
      if (active) b.scrollIntoView({{ block: "nearest" }});
    }});
    const nxt = slides[idx + 1];
    if (nxt) {{
      $("next-thumb-img").src = lang === "zh" ? (nxt.img_zh || nxt.img_en) : (nxt.img_en || nxt.img_zh);
      $("next-preview-title").textContent = `${{nxt.id}} · ${{lang === "zh" ? nxt.title_zh : nxt.title_en}}`;
    }} else {{
      $("next-thumb-img").removeAttribute("src");
      $("next-preview-title").textContent = "已到最后一页";
    }}
    if (!isAudience) {{
      if (location.hash !== `#${{s.id}}`) history.replaceState(null, "", `#${{s.id}}`);
      renderNotes(s);
      if (!fromSync) postToAudience({{ type: "sync", idx, lang, blackout }});
    }} else if (!fromSync) {{
      postToOpener({{ type: "sync", idx, lang }});
    }}
  }}

  function go(nextIdx, fromSync = false) {{
    idx = Math.max(0, Math.min(slides.length - 1, nextIdx));
    render(fromSync);
  }}
  function toggleLang(target, fromSync = false) {{
    if (langs.length < 2) return;
    lang = target || (lang === "zh" ? "en" : "zh");
    buildNav();
    render(fromSync);
  }}
  function setBlackout(val, fromSync = false) {{
    blackout = val;
    if (isAudience) document.body.classList.toggle("is-blackout", blackout);
    else {{
      $("p-remote-blackout").textContent = blackout ? "☀ 恢复画面" : "⬛ 黑屏";
      if (!fromSync) postToAudience({{ type: "blackout", blackout }});
    }}
  }}

  function openDualScreen() {{
    const base = location.href.split("#")[0].split("?")[0];
    const url = `${{base}}?audience=1#${{slides[idx].id}}`;
    audWin = window.open(url, "qifei_audience_stage", "width=1280,height=720,menubar=no,toolbar=no,location=no,status=no");
    if (!audWin) {{ toast("浏览器拦截了弹窗，请允许弹出观众窗口"); return; }}
    document.body.classList.add("is-presenter");
    $("btn-dual").classList.add("active");
    if (!timerHandle) timerHandle = setInterval(() => {{ timerSec++; $("p-timer").textContent = fmtTime(timerSec); }}, 1000);
    setTimeout(() => postToAudience({{ type: "sync", idx, lang, blackout }}), 500);
    toast("已打开观众大屏窗口：请拖至外接屏并点击全屏");
  }}
  function closeDualScreen() {{
    if (audWin && !audWin.closed) audWin.close();
    audWin = null;
    document.body.classList.remove("is-presenter");
    $("btn-dual").classList.remove("active");
    if (timerHandle) {{ clearInterval(timerHandle); timerHandle = 0; }}
  }}

  window.addEventListener("message", e => {{
    const msg = e.data;
    if (!msg || !msg.__qifeiDual) return;
    if (msg.type === "sync") {{
      if (msg.lang && msg.lang !== lang) toggleLang(msg.lang, true);
      if (typeof msg.idx === "number" && msg.idx !== idx) go(msg.idx, true);
      if (typeof msg.blackout === "boolean") setBlackout(msg.blackout, true);
    }} else if (msg.type === "blackout") {{
      setBlackout(Boolean(msg.blackout), true);
    }} else if (msg.type === "replay") {{
      document.dispatchEvent(new KeyboardEvent("keydown", {{ key: "r", bubbles: true }}));
    }} else if (msg.type === "ready" && !isAudience) {{
      postToAudience({{ type: "sync", idx, lang, blackout }});
    }}
  }});

  if (isAudience) {{
    setTimeout(() => postToOpener({{ type: "ready" }}), 150);
  }}

  document.addEventListener("click", e => {{
    const item = e.target.closest(".slide-item");
    if (item) return go(Number(item.dataset.idx));
    const lbtn = e.target.closest("[data-lang]");
    if (lbtn) return toggleLang(lbtn.dataset.lang);
    const nbtn = e.target.closest("[data-nmode]");
    if (nbtn) {{
      noteMode = nbtn.dataset.nmode;
      document.querySelectorAll("[data-nmode]").forEach(b => b.classList.toggle("active", b === nbtn));
      return renderNotes(slides[idx]);
    }}
  }});
  $("btn-prev").addEventListener("click", () => go(idx - 1));
  $("btn-next").addEventListener("click", () => go(idx + 1));
  $("btn-nav").addEventListener("click", () => {{ const c = $("sidebar").classList.toggle("collapsed"); $("btn-nav").classList.toggle("active", !c); }});
  $("btn-notes").addEventListener("click", () => {{ const c = $("notes-pane").classList.toggle("collapsed"); $("btn-notes").classList.toggle("active", !c); }});
  $("btn-edit")?.addEventListener("click", () => {{ isEditing = !isEditing; renderNotes(slides[idx]); }});
  $("btn-dual")?.addEventListener("click", () => audWin && !audWin.closed ? closeDualScreen() : openDualScreen());
  $("p-close-dual")?.addEventListener("click", closeDualScreen);
  $("p-timer-reset")?.addEventListener("click", () => {{ timerSec = 0; $("p-timer").textContent = "00:00"; }});
  $("p-remote-replay")?.addEventListener("click", () => postToAudience({{ type: "replay" }}));
  $("p-remote-blackout")?.addEventListener("click", () => setBlackout(!blackout));
  $("btn-fs").addEventListener("click", () => document.fullscreenElement ? document.exitFullscreen?.() : document.documentElement.requestFullscreen?.());
  $("btn-exit-fs").addEventListener("click", () => {{ document.exitFullscreen?.(); if ($("notes-pane").classList.contains("collapsed")) $("btn-notes").click(); }});
  document.addEventListener("fullscreenchange", () => document.body.classList.toggle("is-fs", Boolean(document.fullscreenElement)));
  $("progress-track").addEventListener("click", e => {{
    const r = $("progress-track").getBoundingClientRect();
    go(Math.round(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * (slides.length - 1)));
  }});
  document.addEventListener("keydown", e => {{
    if (e.target.closest("input, textarea")) {{ if (e.key === "Escape") {{ isEditing = false; renderNotes(slides[idx]); }} return; }}
    if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {{ e.preventDefault(); go(idx + 1); }}
    else if (e.key === "ArrowLeft" || e.key === "PageUp") {{ e.preventDefault(); go(idx - 1); }}
    else if (e.key === "l" || e.key === "L") toggleLang();
    else if (e.key === "n" || e.key === "N") $("btn-notes").click();
    else if (e.key === "e" || e.key === "E") $("btn-edit")?.click();
    else if (e.key === "m" || e.key === "M") $("btn-nav").click();
    else if (e.key === "f" || e.key === "F") $("btn-fs").click();
    else if (e.key === "b" || e.key === "B") setBlackout(!blackout);
    else if ((e.key === "r" || e.key === "R") && !isAudience && audWin && !audWin.closed) postToAudience({{ type: "replay" }});
  }});

  loadEdits();
  readHash();
  buildNav();
  render(true);
}})();
</script>
{motion_js}
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build standalone offline Presenter HTML deck.")
    ap.add_argument("--manifest", help="JSON file containing {brand_name, subtitle, chapters, slides:[{slide_id,title_zh,title_en,img_zh,img_en,note_zh,note_en,duration}]}")
    ap.add_argument("--langs", default="zh", help="Comma-separated languages: zh | en | zh,en")
    ap.add_argument("--no-edit-notes", action="store_true", help="Disable inline speaker-notes editing")
    ap.add_argument("--motion-css", help="Optional extra CSS file for motion layers")
    ap.add_argument("--motion-dom", help="Optional extra HTML snippet injected inside .slide-frame")
    ap.add_argument("--motion-js", help="Optional extra <script> bundle appended before </body>")
    ap.add_argument("--out", help="Output HTML file path")
    ap.add_argument("--check-motion-plan", help="Validate a motion-plan.json for consecutive static-slide pacing (>=12 warn, >=20 fail)")
    ap.add_argument("--slide-ids-json", help="JSON list of slide_ids (or deck-spec.json) used with --check-motion-plan")
    args = ap.parse_args(argv)

    if args.check_motion_plan:
        plan = json.loads(pathlib.Path(args.check_motion_plan).read_text(encoding="utf-8"))
        if args.slide_ids_json:
            raw_ids = json.loads(pathlib.Path(args.slide_ids_json).read_text(encoding="utf-8"))
            slide_ids = [s["slide_id"] for s in raw_ids["slides"]] if isinstance(raw_ids, dict) else list(raw_ids)
        else:
            slide_ids = list(plan.get("slide_order", []))
        report = analyze_motion_pacing(slide_ids, plan)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if report["status"] == "FAIL_PACING_GAP" else 0

    if not args.manifest or not args.out:
        ap.error("--manifest and --out are required unless using --check-motion-plan")

    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    langs = [x.strip() for x in args.langs.split(",") if x.strip() in ("zh", "en")] or ["zh"]
    slides = collect_slides(manifest["slides"], langs)
    chapters = manifest.get("chapters") or [["CH01", "全案", "Deck", 1, len(slides)]]

    html = build_html(
        brand_name=manifest.get("brand_name", "PROPOSAL"),
        subtitle=manifest.get("subtitle", f"{len(slides)} Slides · 离线讲解台"),
        chapters=chapters,
        slides=slides,
        langs=langs,
        editable_notes=not args.no_edit_notes,
        motion_css=pathlib.Path(args.motion_css).read_text(encoding="utf-8") if args.motion_css else "",
        motion_dom=pathlib.Path(args.motion_dom).read_text(encoding="utf-8") if args.motion_dom else "",
        motion_js=pathlib.Path(args.motion_js).read_text(encoding="utf-8") if args.motion_js else "",
    )
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {out_path} ({size_mb:.2f} MB, {len(slides)} slides, langs={','.join(langs)})")
    if size_mb > 60.0:
        print("WARNING: Offline single-file HTML exceeds 60 MB soft threshold; consider compressing video bitrate or external media/ folder.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
