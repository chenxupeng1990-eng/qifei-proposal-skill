# Deterministic production utilities

This reference defines the boundary between proposal judgment and repeatable production work. Automation is allowed to reduce mechanical errors; it may not replace the reasoning that makes a proposal persuasive.

## 1. Two layers with different authority

### Judgment layer — agent and proposal owner

The following decisions require proposal reasoning and cannot be delegated to a template, layout library, or autofill routine:

- the business question and audience decision;
- the conclusion and its evidence chain;
- the narrative relationship with the previous and next page;
- the communication object and best visual carrier;
- the visual hammer, product role, and information hierarchy;
- whether a page is information-led, design-led, or hybrid;
- whether a visual result is semantically correct and persuasive.

Automation may expose options or report violations. It must not silently choose these answers, rewrite them, or fill missing decisions with generic copy.

### Mechanical layer — deterministic utilities

The following work is safe to automate when its input contract is already approved:

- stage media into project-owned relative paths;
- normalize image formats, dimensions, and naming;
- verify asset existence, file type, alpha channel, dimensions, and duplicate IDs;
- verify required fields, exact-copy arrays, version IDs, hashes, and page order;
- detect placeholder copy, internal production notes, default-demo text, and local-path leakage;
- capture measured HTML boxes and compile approved layers;
- render review PNGs, build montages, package exports, and generate QA reports;
- compare frozen fields, coordinates, slide notes, page count, and approved hashes.

Mechanical utilities return a result and diagnostics. They do not change strategy, evidence, copy, carrier, page count, or design direction.

## 2. Required interface

Every utility must have a narrow input and an inspectable output:

| Stage | Authoritative input | Mechanical output | Failure behavior |
|---|---|---|---|
| Pre-generation | `page-contracts.json` | validation report | block the page and name the missing or invalid field |
| Asset staging | approved source assets | normalized project-relative assets plus manifest | preserve the original; fail on missing or ambiguous source |
| Review build | approved contracts, `DESIGN.md`, local assets | HTML and/or independent 16:9 PNGs | fail on missing asset, overflow, or unresolved placeholder |
| Approval record | explicit page approval | page ID, content hash, design version, approved PNG | never infer approval from a successful render |
| Final assembly | complete approved manifest | PPTX/PDF/PNG package plus validation report | fail closed on stale hash, wrong order, missing page, or path leak |

Diagnostics must identify the page, field or asset, the violated rule, and the next correction layer. A utility must not hide an error by choosing a different template or shrinking text.

## 3. Default-copy and path leak gate

Client-visible copy fails when it contains unresolved markers or production language such as:

```text
TBD / TODO / PLACEHOLDER / Lorem ipsum / 待补充 / 待确认 / 占位
本页展示 / 建议呈现 / 章节视觉 / 设计说明 / 页面任务 / 示例文案
```

Final production metadata and client-visible files must not contain:

- `file://` URLs;
- local absolute paths such as `/Users/...`, `/home/...`, or `C:\...`;
- remote media URLs used as final production assets;
- inline `data:` media where project-owned files are required.

Sources and citations may contain public web URLs when the page contract explicitly identifies them as sources. Media assets still need to be staged locally.

## 4. No autofill fallback

When a required field is absent, stop and report it. Never:

- copy the previous page's field;
- select a visually convenient carrier;
- insert generic business language;
- invent a number, label, source, or audience judgment;
- force content into an available theme slot;
- treat a technically successful export as page approval.

This is the main protection against a polished but strategically empty deck.

## 5. QA sequence

Automation supplements, but does not reorder, the review sequence:

1. **Semantic QA** — judgment layer confirms source truth, conclusion, logic, carrier, and product role.
2. **Visual QA** — human review confirms visual hammer, hierarchy, whitespace, font scale, and thumbnail focus.
3. **Mechanical QA** — utilities confirm fields, paths, assets, geometry, versions, hashes, and exports.
4. **Approval gate** — proposal owner explicitly marks the page approved.
5. **Assembly gate** — only fully approved pages enter final PPT/PDF assembly.

Mechanical PASS means the artifact is internally consistent. It does not mean the page is strategically correct, visually persuasive, or approved.
