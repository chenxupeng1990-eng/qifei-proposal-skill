---
name: proposal-ppt-production
description: Use when turning a proposal, strategy document, report, or page outline into a high-design 16:9 presentation; when generating slide PNGs or PPTX; or when revising a deck whose narrative, information density, visual carrier, typography, whitespace, product integration, and cross-page consistency must be controlled.
---

# Proposal PPT Production

## Principle

Visualize the source information; do not turn all source information into visual spectacle. Preserve the argument and necessary detail while giving each page one clear focus.

**REQUIRED SUB-SKILL:** Use `Presentations` for PPTX work. Use `imagegen` for generated scenes, objects, textures, or visual carriers.

Always read `references/production-sop.md`, `references/design-system-contract.md`, `references/page-contract-and-qa.md`, and `references/deterministic-production-utilities.md`. The active project's confirmed `DESIGN.md` is the styling authority and overrides all generic examples. If the user provides a PPTX that must function as the actual template or editable source deck, also read `references/template-exact-mode.md` and use the Presentations template-following workflow.

When the proposal contains industry, competitor, people, product, channel, or operating data, also read `references/data-analysis-and-comparison-methods.md` before writing page contracts.

## Role in a larger proposal workflow

This skill starts only after the content, page contracts, and design direction have been confirmed. It may produce review HTML and/or PNGs, but it cannot mark a page approved, alter evidence, or authorize final assembly. During review, use the lightest valid artifact: direct PNG plus Cowart annotation for image-native pages, or HTML plus PNG for pages with editable exact text, data or structured labels. Assemble PPTX/PDF only after the controlling workflow records explicit final approval for every required page. When the requested handoff requires editable copy, use the measured-HTML bridge after approval: keep approved visuals as the background layer and compile measured HTML text boxes into native PowerPoint text. This bridge is an export mode, never a replacement for HTML/PNG review.

## Judgment and automation boundary

Proposal judgment stays with the agent and proposal owner: business question, conclusion, evidence chain, narrative role, communication object, carrier, visual hammer, product role, and audience decision. Deterministic utilities may validate fields, stage media, measure HTML, render, compare, package, and report errors. They may not autofill a missing decision, choose a convenient template, rewrite strategy, shrink copy to force a fit, or infer approval from a successful export.

## Visual-direction preflight gate

Before producing content pages, verify that the project has an explicit approval record for a visual core sample. A palette, font list, client reference deck, or agent-authored DESIGN.md does not count as approval. If the sample approval is missing:

1. stop content-page production;
2. produce 2–3 genuinely different visual core samples using the same confirmed copy;
3. record the selected primary direction and any named chapter variant;
4. build and approve the required calibration page types;
5. only then compile and freeze DESIGN.md.

Any DESIGN.md written before visual-sample approval must be marked `draft` or `rejected` and cannot be treated as styling authority.

Before calibration, choose exactly one deck-level visual authority:

1. an actual user PPTX template to inherit exactly;
2. an explicitly approved custom brand direction;
3. a newly calibrated direction when neither exists.

Do not mix unrelated templates, default layout libraries, reference-deck styling and custom visual systems in one deck.

## Workflow

1. **Lock source truth and choose the analysis loop.** Inventory confirmed copy, evidence, numbers, sources, logos, product images, fonts, and prohibited changes. For analytical proposals, declare whether each major argument begins as a strategy hypothesis seeking evidence or as a data pattern seeking a strategy. In the first mode, search supporting and conflicting evidence and revise the hypothesis when needed. In the second mode, test competing explanations before converting a pattern into a strategy. Never invent proof, cherry-pick evidence, or silently alter conclusions.
2. **Define the communication job and map the narrative.** Write: `By the end, [audience] should [outcome] because [central takeaway].` Give every page one role and one conclusion. Build cumulative logic rather than independent posters. For analytical proposals, require every major finding to produce a strategy choice, downstream chapter task and verification metric. Reject an insight that does not change the later proposal, and reject a strategy that cannot be traced back to evidence.
3. **Pass the logic-to-visual gate.** Before styling or prompting Image2, write the page's causal statement as `because -> therefore -> audience decision`. Reject any proposed carrier that merely illustrates the topic or mood without making that reasoning easier to see.
4. **Choose the carrier before styling.** Use chart/table for data; image/storyboard for scenes and actions; path/loop/diagram for relationships; realistic UI or work artifact for execution; KV only for claims and transitions.
5. **Choose production mode.** HTML owns exact copy, labels, data, sources, and typography. Image2 owns composition, material, people, scenes, and relationship carriers. Use hybrid pages when both are essential. If the page is image-native and contains no required editable text, exact data, source or dense labels, generate a complete 16:9 PNG directly, review and annotate it in Cowart, and skip HTML. When the visual hammer includes a real product, supply the official product image to Image2 as a strong reference and generate product, scene, lighting, reflections, contact shadows, scale and perspective as one composition. Do not generate an empty scene and paste the product into it later with HTML/CSS.
6. **Calibrate, then scale.** Produce 2–3 representative pages, review at full and thumbnail size, lock tokens, then continue in small batches. Validate independent 1920×1080 PNGs before final assembly.
7. **Run semantic, visual, and technical QA in that order.** A technically clean or beautiful page still fails when its carrier does not express the page conclusion. Fix only the affected layer and preserve approved pages.

Before visual production, store page contracts as JSON and run:

```bash
node scripts/validate_page_contracts.mjs <page-contracts.json>
```

Do not write Image2 prompts or batch HTML for pages that fail this gate.

## Hard rules

- Never default the deck to KV, equal cards, 50/50 splits, or full-page dark blue.
- A visually polished page fails when its primary carrier can be swapped for another on-topic image without changing the conclusion. This is the topic-illustration failure and requires carrier redesign, not cosmetic adjustment.
- Every generated page must pass a removal test: hide the primary carrier and ask what understanding is lost. If no essential relationship, action, contrast, mechanism, proof, or decision is lost, the carrier is decorative and the page is rejected.
- Information-led pages need visible structure or a restrained auxiliary visual. The auxiliary cannot outrank the information.
- Except for pages dominated by large volumes of exact data, a content page may not be completed through text layout alone. It must contain a primary carrier that visibly performs part of the explanation: a diagram, progression, mechanism, scene, simulation, evidence artifact, workbench, product architecture, or semantic no-text image system. If removing the carrier leaves the page meaning unchanged, it is decoration and the page fails review.
- For light information pages, prefer a semantic transparent PNG behind HTML; keep precise text in HTML.
- Sparse, short and exact labels may be integrated into Image2 when they are inseparable from one visual hammer and can be checked word-for-word at full size. If any character, hierarchy or pointer relationship is wrong, regenerate the visual or move the labels back to HTML.
- Large copy, exact data, sources, dense causal logic and unverifiable labels stay outside Image2. A successful sparse-label exception does not authorize generated text elsewhere in the deck.
- Do not create HTML merely to satisfy a pipeline convention. A page may remain a direct PNG when all necessary meaning is already carried by the generated composition and all embedded sparse text has been verified. The moment exact editable copy, charts, tables, citations or dense logic are required, return to HTML or a hybrid route.
- Scene-led pages must show what happens. Do not reduce live rooms, phone demos, or behavior to tables merely because they contain many details.
- Integrate product through shared light, perspective, contact, and narrative function during primary-visual generation. If it still looks false, regenerate with stronger official-product references; do not repair the scene with a pasted product cutout.
- Use real packaging artwork. Reject generated logo, label, claim, or pack hallucinations.
- Semantic no-text icons are valid visual anchors when they improve recognition without replacing precise information.
- Keep same-role font sizes in one band across pages. Do not solve overflow by making a single page much smaller.
- Unless an approved template specifies otherwise, use at least 50pt for deck titles, 35pt for slide titles, 24pt for mid-level headings and 16pt for body copy. Shorten, restructure or split before shrinking. A title intended as one line may not wrap silently.
- Visible copy must address the proposal audience. Production instructions, visual-design notes, page tasks, prompt language, timing scaffolds and agent reasoning belong in page contracts, notes or QA records—not on the slide.
- Treat unintended overlap, clipping and overflow as hard failures. Inspect every page at full size; use the montage only for cross-page pacing and consistency.
- Reject unexplained continuous whitespace above about 8% of the canvas and thumbnail-level weight imbalance.
- Regenerate only the visual region when Image2 introduces text errors; exact copy and data stay outside generated images.
- HTML may hold exact proposal copy and independent brand marks, but it must not be used to simulate product-scene integration.
- Mechanical validation must fail closed on missing fields, duplicate IDs, unresolved placeholders, internal production language, stale versions, missing assets, or local-path leakage. It reports the page and violated field; it does not repair meaning by autofill.

## Review loop

For every revision record: observed problem, violated rule, correction layer, affected pages, and regression checks. Stop for direction if the change would alter strategy, evidence, page count, or previously approved content.

For every calibration page, record five QA decisions before approval: the page conclusion, the communication object, the selected carrier, the visual hammer, and the full-size plus thumbnail checks. A visually polished page fails if its carrier does not make the conclusion easier to understand.

## Completion gate

Use current renders—not assumptions—to prove 1920×1080 output, no clipping, readable text, balanced whitespace, consistent type and brand language, faithful product artwork, and deliberate montage rhythm. When the controlling workflow authorizes assembly, additionally prove PPTX parity with all approved PNGs. For editable-text handoff, also prove frozen-field fidelity, slide-note traceability, measured-box coordinate fidelity, and a full rendered comparison; a text-field PASS alone does not prove visual parity.
