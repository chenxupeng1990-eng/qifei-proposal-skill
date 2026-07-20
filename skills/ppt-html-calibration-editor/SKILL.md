---
name: ppt-html-calibration-editor
description: Use when a fixed 16:9 HTML slide, presentation page, or PNG-rendering template needs browser-based copy editing, text-box adjustment, image replacement, drag/resize calibration, local persistence, JSON handoff, or a clean separation between edit mode and screenshot mode.
---

# PPT HTML Calibration Editor

## Purpose

Add a lightweight browser calibration layer to fixed 1920×1080 slide HTML. This is for review and precise handoff, not a replacement for Figma or PowerPoint.

Read `references/editor-contract.md` before modifying an existing renderer. Copy `assets/browser-editor/` into the target project when the editor is not already present.

## Integration

1. Keep the logical slide at exactly 1920×1080.
2. Load `editor.css` and `loader.js` from the copied editor package.
3. Set a stable document ID on `body`:

```html
<body data-document-id="proposal-name">
```

4. Opt in only elements the user may change:

```html
<h1 data-editable="text" data-edit-id="slide12.title">Title</h1>
<img data-editable="image" data-edit-id="slide12.product" src="product.png" alt="">
```

5. Leave backgrounds, decorative layers, page spines, logos, and fixed brand identifiers locked unless the user explicitly requests access.

## Modes

- Preview: open normally; editor does not mount.
- Edit: `?edit=1&capture=<slide-id>`.
- Screenshot: `?capture=<slide-id>`; editor DOM must not exist.
- Dedicated clickable review entry: create a thin HTML wrapper or set `data-editor-auto="true"` only on a demo/review page. Never auto-enable editing on a production capture page.

Serve through HTTP rather than `file://`:

```bash
python3 -m http.server 4173
```

ChatGPT/GPT Work web previews may render HTML without executing local modules or interactive file APIs. For real editing, use Codex desktop/local preview or a normal browser connected to the local server.

## Required behavior

- Single click selects; double click edits text; Escape exits editing.
- Drag uses 1920×1080 logical coordinates independent of display scale.
- Text boxes resize freely; images resize proportionally.
- Text properties include font size, weight, line-height ratio, color, and alignment.
- Image properties include replacement, opacity, and z-index.
- Persist after a 300 ms debounce to `ppt-editor:<documentId>:<slideId>:v1`.
- Support undo/redo and validated schema-versioned JSON import/export.
- Make the UI explicit that browser saving does not rewrite source HTML.
- Keep replacement images below the configured local-storage limit; default to 2.5 MB because data-URL encoding expands the stored payload.
- Text calibration is plain text only. Imported legacy `html` values must be stripped to text before application; never inject imported markup into a slide.

## Source handoff

Treat exported JSON as a calibration record. Read it, apply copy/geometry/style changes to HTML/CSS, copy replacement image files into project assets, then rerender the slide. Never assume localStorage is the production source of truth.

## Verification

Before delivery, use a real browser to verify:

1. no-query production capture has no `.ppt-editor-root`;
2. edit mode mounts and selects opted-in elements;
3. double-click creates `contenteditable="true"`;
4. drag, resize, typography, image replacement, undo/redo, reload persistence, JSON exchange, and proportional image sizing work;
5. the clean render remains 1920×1080 with no new overflow;
6. a direct review entry actually starts edit mode without requiring the user to type query parameters.
