# Page contract and QA gate

Use this contract before every Image2 prompt or HTML layout. It prevents pages from becoming attractive topic posters that do not advance the proposal.

## 1. Page contract

Before writing page contracts, define the deck communication job:

```text
Audience:
Audience outcome:
Central takeaway:
Communication job: By the end, [audience] should [outcome] because [central takeaway]
```

Then record the following fields for every page:

```text
Audience decision:
Audience-facing copy confirmed: yes / no
Prior-page question:
Page conclusion:
Causal statement: because ___, therefore ___, so the audience should ___
Semantic role: raise / answer / prove / interpret / choose / operationalize / transition
New understanding created:
Strategy link:
Communication object: data / comparison / progression / mechanism / scene / behavior / decision / system / proof / transition
Primary carrier:
What the carrier must make visible:
Visual hammer:
Product role: none / evidence / mechanism / usage / choice / transaction
Product reference required in Image2: yes / no
Exact sparse labels allowed in Image2:
Exact content retained in HTML:
Production route: HTML / HTML + transparent PNG / Image2 + HTML / direct PNG + Cowart
Why HTML is required or can be skipped:
Visual frame: aspect ratio / subject position / gaze or direction / protected text zone / crop tolerance / reuse allowed
Typography plan: title size / title line intent / mid-level size / body minimum
Failure if the page becomes:
Next-page question:
```

Do not produce the page until the causal statement and carrier answer each other. A page about opportunity cannot use a generic premium KV; it needs to reveal the market tension, narrowing choice, or decision path that creates the opportunity.

Visible slide copy must be written for the audience. Reject copy such as `本页展示`、`建议呈现`、`章节视觉`、`设计说明`、`页面任务` or production comments unless the audience explicitly needs that information.

## 2. Carrier fitness tests

Run all four tests before generation:

1. **Removal test** — if the carrier disappears, which essential understanding disappears with it?
2. **Swap test** — could another image from the same category replace it without changing the page? If yes, it is topic illustration, not explanation.
3. **Thumbnail test** — at roughly 480px width, can the audience identify the page's primary contrast, path, mechanism, scene, or decision before reading body copy?
4. **Narrative test** — does the page answer the question created by the previous page and create a useful question for the next?

Failure in any test sends the page back to carrier selection. Do not repair a semantic failure with more labels, cards, decoration, or smaller text.

## 3. Image2 text gate

Sparse text can be generated into Image2 only when all conditions are true:

- no more than three short semantic labels;
- the labels are spatially inseparable from one visual hammer;
- every character can be checked at full resolution;
- the page remains understandable if the HTML title is read first;
- a wrong label can be regenerated without changing evidence or page logic.

Keep large copy, exact data, sources, dense logic, qualifications, and unverifiable labels in HTML. If a generated label is wrong, regenerate it or move it to HTML; never accept approximate text.

## 4. Product integration gate

When the product performs a narrative role, its official reference must enter the same Image2 generation call as the scene or mechanism. Generate shared perspective, lighting, reflections, scale, contact shadows and environmental interaction in one image.

Reject the visual if:

- packaging recognition is materially wrong;
- the product appears pasted, floating, or lit by a different source;
- the product is decorative and does not function as evidence, mechanism, usage, choice, or transaction;
- the scene was generated first and the product was later added to simulate integration.

## 5. QA order

Review every page in this order:

1. **Semantic QA** — source truth, conclusion, causal logic, carrier fitness, product role.
2. **Visual QA** — visual hammer, hierarchy, whitespace, orphan elements, font bands, thumbnail balance.
3. **Technical QA** — 1920x1080, clipping, overlap, asset loading, generated-text fidelity, browser/PPT parity.

Passing technical QA never compensates for semantic or visual failure.

Inspect each slide independently at full size. Use a montage only to inspect deck rhythm, visual authority, density variation and cross-page consistency; never use it as a substitute for full-size QA. Any unintended overlap warning requires inspection and correction.

### Cross-page semantic review

After page-level QA, review the chapter and full deck as a sequence:

- confirm that each page answers, proves, interprets or operationalizes something created by the previous page;
- identify pages that restate the same conclusion without adding evidence, meaning, choice, action or validation;
- review repeated title syntax, motifs, people, skeletons and fixed components as semantic patterns, not only visual frequency;
- preserve intentional repetition when its role evolves; remove, merge or reorder repetition that adds no new understanding;
- use continuous playback and a montage together. Statistics may flag a pattern, but the reviewer decides whether it is intentional.

Confirmed semantic breaks return to narrative or page-contract correction. Do not repair them with more labels, decoration or smaller text.

## 6. QA ledger row

```text
Page:
Observed problem:
Violated gate:
Root cause:
Correction layer: narrative / carrier / Image2 / HTML / typography / assembly
New carrier decision:
Full-size result:
Thumbnail result:
Product-reference result:
Exact-text result:
Status: revise / review / approved / assembly-ready
```
