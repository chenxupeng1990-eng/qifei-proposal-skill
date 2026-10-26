<p align="center">
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

<p align="center">
  <img src="docs/readme-assets/hero-system.webp" alt="A governed production system that turns scattered material into a finished presentation" width="100%">
</p>

<h1 align="center">Proposal Skill V2</h1>

<p align="center">
  <strong>Take an idea all the way to a proposal you can present, verify and deliver.</strong><br>
  A proposal production system for AI agents: strategy, manuscript, visuals, review and delivery, each step confirmed by a person and checked by a machine.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-0.3.1-ff5f4d">
  <img alt="Tests" src="https://img.shields.io/badge/tests-186%20passing-1f8b4c">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776ab">
  <img alt="Node" src="https://img.shields.io/badge/Node.js-18%2B-339933">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-111827">
  <img alt="License" src="https://img.shields.io/badge/license-PolyForm%20Noncommercial-6b7280">
</p>

<p align="center">
  <a href="#overview">Overview</a> ·
  <a href="#whats-new">What's new in v0.3</a> ·
  <a href="#pipeline">Pipeline</a> ·
  <a href="#gates">Gates</a> ·
  <a href="#quickstart">Quick start</a> ·
  <a href="#runtime">Runtime tiers</a> ·
  <a href="#license">License</a>
</p>

> The tools are built for Chinese-language proposals, so the screenshots below show Chinese interfaces.

---

<a id="overview"></a>

## Overview

Most slide skills optimise the last step: pouring finished text into a template.

Proposal Skill V2 governs the whole chain: understanding the material, forming a point of view, writing the manuscript, locking a visual language, producing pages, absorbing review comments and checking the delivery. The agent drives the work, the Owner makes the calls, and scripts enforce the checks. Those boundaries live in the workflow itself, not in a prompt the agent may or may not follow.

> **Strategy sets the ceiling. Quality gates protect the floor.**

### The whole flow in 80 seconds

[![Watch the 80-second walkthrough](docs/readme-assets/intro-github-poster.jpg)](docs/readme-assets/intro-github.mp4)

[Click the cover or play the video here](docs/readme-assets/intro-github.mp4) · 80 seconds · 1080p

### Recent work

Anonymised page thumbnails from recent proposals across nutrition and wellness, dermocosmetics, market strategy and brand visual systems. They are visual references only, not client material or a fact base.

<table>
  <tr>
    <td width="50%"><img src="docs/readme-assets/cases/case-01-nutrition.png" alt="Nutrition and wellness proposal"></td>
    <td width="50%"><img src="docs/readme-assets/cases/case-02-dermocosmetics.png" alt="Dermocosmetics proposal"></td>
  </tr>
  <tr>
    <td align="center"><sub>Nutrition &amp; wellness</sub></td>
    <td align="center"><sub>Dermocosmetics</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/readme-assets/cases/case-03-sunscreen-strategy.png" alt="Market strategy proposal"></td>
    <td width="50%"><img src="docs/readme-assets/cases/case-04-brand-system.png" alt="Brand visual system proposal"></td>
  </tr>
  <tr>
    <td align="center"><sub>Market strategy</sub></td>
    <td align="center"><sub>Brand visual system</sub></td>
  </tr>
</table>

The same content is never forced into a template. The system first renders two or three visual directions from real Image2 samples. The Owner picks one, it is fixed as `DESIGN.md`, and every page is produced against it.

<table>
  <tr>
    <td width="33%"><img src="docs/readme-assets/direction-editorial.webp" alt="Editorial Intelligence direction"></td>
    <td width="33%"><img src="docs/readme-assets/direction-precision.webp" alt="Precision Control direction"></td>
    <td width="33%"><img src="docs/readme-assets/direction-balanced.webp" alt="Strategy Engine direction"></td>
  </tr>
  <tr>
    <td align="center"><sub>Editorial Intelligence</sub></td>
    <td align="center"><sub>Precision Control</sub></td>
    <td align="center"><sub>Strategy Engine + Quality Gate</sub></td>
  </tr>
</table>

### How it differs

| Typical slide skill | Proposal Skill V2 |
|---|---|
| Starts formatting as soon as text arrives | Settles audience, decision goal, stance and core tension first |
| Generates pages one by one | Builds a strategy spine, chapter interfaces and a page-level argument chain |
| Relies on a template for consistency | Relies on `DESIGN.md`, master pages and a carrier decision for every page |
| Lets the agent decide a page "looks fine" | Ties every approval to an object, a version and evidence, from the Owner only |
| Leaves feedback scattered in chat | Anchors comments to exact places in the manuscript and on the page; the agent replies, the Owner decides |
| Starts every project from scratch | Turns the Owner's judgement into memory that the next project loads |
| Calls it done once a PPTX exists | Exports only after page order, on-screen text, layout and speaker notes are checked |

---

<a id="whats-new"></a>

## What's new in v0.3

v0.3 moves collaboration from Feishu to a local studio. It was then tested on a complete mock project, with an agent doing all the work and a person acting as Owner. Every gap the test exposed has been closed.

### Proposal draft studio

The single source of truth for the manuscript. Read it in the browser, edit in place, and comment on selected text. When the agent edits the draft file directly, open pages update within about half a second. The Owner confirms chapter by chapter. Each confirmation records a fingerprint of every page, so any later change sends that chapter back for confirmation.

<p align="center">
  <img src="docs/readme-assets/v03/studio.webp" alt="Draft studio: chapter confirmation, comments on selected text, agent replies" width="100%">
</p>

- Three views: full, client view, and a read-only title chain.
- Comment threads: the Owner asks, the agent answers with `draft_studio.py reply`, and the Owner agrees and resolves in one click. Decided comments stay visible as a decision record.
- `serve --detach` keeps the studio running after the agent's turn ends, so the link always works.
- No Feishu account needed; Feishu can still be chosen as the source of truth when a project starts.

### Design review: box comments on rendered pages

During page production, the Owner draws a box on the rendered page and writes the note there. No more screenshots or exported JSON.

<p align="center">
  <img src="docs/readme-assets/v03/design-review.webp" alt="Design review: box comments on a rendered page" width="100%">
</p>

- Each comment records the page, the screenshot hash, the box in 1920×1080 coordinates, the text under the box and a crop of the area.
- The agent reads comments with `design_review.py list`, fixes the page and answers with `reply`. When the page is captured again, older comments are marked as outdated.
- Only the Owner resolves. A page with open design comments cannot enter the assembly-ready library.

### Proposal memory box

The Owner's judgement carries across projects in three layers: Owner preferences, playbook and project memory. Before each phase is released, the agent drafts candidate memories from comments, edits and confirmations. The Owner accepts, rewrites or discards them in the memory box, and accepted entries load automatically at the start of each later phase.

<p align="center">
  <img src="docs/readme-assets/v03/memory-box.webp" alt="Memory box: pending candidates and three memory layers" width="100%">
</p>

- The agent needs two commands: `proposal_memory.py note` captures a correction the Owner gives in conversation, and `proposal_memory.py advance --to <phase>` handles a phase change in one step (distil signals, prompt for candidates, load the next phase's memory).
- Memory can be switched off globally with `proposal_memory.py off` or the "启用记忆" toggle at the top of the memory box.
- Loading memory does not depend on the prompt. `doctor.py` and `validate_project.py` deliver the memory and check a read receipt, and leaving a phase without distilling its signals fails validation.

### Stricter gates

| New check | What it stops |
|---|---|
| Approver check | Gate approvals must come from the Owner; the agent can neither approve its own work nor waive validator errors |
| `DESIGN.md` content check | A design spec with headings but no values: grid and safe area, type floor and split rule, text-zone share, text-layer components, batch rule, master list, QA checklist |
| On-screen caution lint | Internal hedging ("does not equal", "does not represent", "not yet") on pages the client will see |
| Line-by-line text check | On-screen text in the page or the PPTX that differs from the frozen manuscript, missing or extra |
| Layout measurement | Orphan last lines, overflow, text on busy texture and near-miss left edges, measured on the real render |
| Independent visual review | A second agent reviews every page adversarially; its report is bound to each page's screenshot hash |
| Final check | Before export, only low-level slips: page order, on-screen text, layout, a recorded proofread |

See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

---

<a id="pipeline"></a>

## From idea to deliverable

```text
Idea / brief / source material
   │
   ├─ Decision interview ········ audience, goal, stance, core tension
   ├─ Strategy spine ············ thesis, chapter interfaces, argument order
   ├─ Manuscript ················ whole chapters → studio comments → Owner confirms each chapter
   ├─ Full-draft review ········· one independent pass: logic, wording, page splits, leaked hedging
   ├─ Content freeze
   ├─ Visual direction ·········· real Image2 samples → Owner choice → DESIGN.md
   ├─ Design calibration ········ master pages, text-layer components, full pages reviewed with text
   ├─ Page production ··········· best carrier per page → full-page Image2 base + HTML text layer → batches
   ├─ Design review ············· box comments → agent fixes → Owner resolves → assembly-ready library
   ├─ Independent visual review · layout measurement + a second agent reviewing every page
   ├─ Speaker notes ············· written once, against the final page numbers
   └─ Final check → export ······ PNG / PDF / PPTX
```

Every phase answers three questions: what checkable object it produces, who may confirm it, and which conditions stop the flow. At the start of each phase the agent loads the memory relevant to it.

<a id="gates"></a>

## Gates

Two kinds of gate: scripts check what a machine can judge, and the Owner confirms what needs judgement. A passing script is not an Owner approval.

| Phase | Script checks | Owner confirms |
|---|---|---|
| Manuscript | Single draft format, on-screen caution lint, title chain, revision and registration hashes | Each chapter |
| Full-draft review | Independent agent report and id | Content freeze |
| Visual direction and calibration | Real image assets, brand sources, `DESIGN.md` content | Direction choice, calibration |
| Page production | Page contract, build identity, line-by-line on-screen text, no open design comments | Each page into the assembly-ready library |
| Visual review | Zero measured layout problems; independent review covers every page with matching hashes | — |
| Export | Final check passed, speaker notes match the page order, PPTX text checked again | Final delivery |

A memory gate sits between phases: signals must be distilled before leaving a phase, and updated memory must be read before validation passes.

## Task modes

| Mode | Use it for | What remains controlled |
|---|---|---|
| `full_deck` | A new proposal, report or presentation | Full strategy, full-draft review, freeze, visual direction, notes, export |
| `inherited_module` | Adding or replacing a module in an existing governed deck | Parent strategy and design, module interfaces, page quality |
| `standalone_module` | A single page or a 2–8 page module | Lightweight brief, module logic, visual baseline, page loop, export |

---

<a id="quickstart"></a>

## Quick start

### 1. Download and check the environment

```bash
git clone https://github.com/chenxupeng1990-eng/qifei-proposal-skill.git
cd qifei-proposal-skill
python3 scripts/bootstrap.py --suite v2
```

On macOS you can double-click [`scripts/install_v2.command`](scripts/install_v2.command); on Windows use [`scripts/install_v2.ps1`](scripts/install_v2.ps1). The installer checks Python, Node.js, npm and a browser.

### 2. Install the skill suite

```bash
python3 scripts/install_skills.py --suite v2
```

Skills install to `~/.codex/skills` by default. The installer stops if a skill with the same name exists; add `--force` to replace it. Restart your agent and call:

```text
$qifei-proposal-v2
```

### 3. Create a project

```bash
# See how far the current agent and machine can go
python3 skills/qifei-proposal-v2/scripts/doctor.py --task-mode full_deck --json

# Start a full proposal
python3 skills/qifei-proposal-v2/scripts/init_project.py \
  --project <project-dir> --name <project-name> --owner <owner> --task-mode full_deck
```

### 4. Open the studio and the memory box

```bash
# Draft studio (with the /design review page); keeps running after the agent's turn
python3 skills/qifei-proposal-v2/scripts/draft_studio.py serve <project-dir> --detach

# Proposal memory box
python3 skills/qifei-proposal-v2/scripts/memory_box.py
```

On Windows replace `python3` with `py -3` or `python`, and quote paths that contain spaces or non-ASCII characters.

<a id="runtime"></a>

## Runtime tiers: not tied to a Codex subscription

Doctor detects what the agent and the machine can actually do and picks the highest tier available, regardless of the agent's brand.

| Tier | What it can do |
|---|---|
| `codex_full` | Native image generation, visual understanding, local rendering and comments: full production |
| `api_full` | Another agent with files, commands, an image API, visual understanding and a local runtime: full production |
| `local_production` | Rendering, review and export; without formal image capability the visual-direction gate cannot pass |
| `content_only` | Strategy, manuscript, page routes and prompt packages, without pretending to deliver visuals or a PPTX |

Swappable adapters: image generation (Codex native images, an OpenAI-compatible API, a custom command), source of truth (studio, Feishu, parent project, local Markdown) and independent review (another agent, a separate API call, a named human reviewer). API keys and tokens are never written into project state, prompt logs or logs. See [`task-modes-and-runtime.md`](skills/qifei-proposal-v2/references/task-modes-and-runtime.md).

## Suite

| Skill | Role | Install |
|---|---|---|
| `qifei-proposal-v2` | Entry point: phases, state, gates, draft studio, memory box | Required |
| `grill-me-lite` | One-question-at-a-time decision interview | Required |
| `proposal-ppt-production` | Page carriers, visual production and assembly | Recommended |
| `ppt-html-calibration-editor` | Fine calibration of 16:9 HTML pages | Optional |

## Delivery and editability

- **Base delivery**: PNG, PDF and image-based PPTX that keep the approved visuals intact.
- **Enhanced delivery**: on request, a semi-editable PPTX with native PowerPoint text, checked line by line against the manuscript.
- **Traceability**: HTML, approved PNGs, content hashes and project state support review and re-export.

Charts, complex SVG and generated images are not promised to be fully native-editable, and rendering in different office suites still needs a human look. Passing scripts is not visual sign-off.

<details>
<summary><strong>Governance rules</strong></summary>

- Accuracy is the boundary; a point of view that moves the decision is the goal. A page that is correct but says nothing goes back.
- On screen: claims, evidence and sources only. Boundaries live in the wording; internal caveats go to speaker notes or the evidence ledger.
- The strategy compiles into chapter interfaces, then into page argument chains; each chapter's output is the next chapter's input.
- Once the page chain is confirmed, a whole chapter is written at once, then reviewed page by page.
- After all content is confirmed there is exactly one full-draft review, which does not re-litigate decisions the Owner has made.
- Formal visuals require real image assets in direction calibration. The default route is a full-page Image2 base with an HTML text layer; every page picks its best carrier and is generated from its master.
- Parallel work happens only in page production; the main agent owns shared files and re-verifies every wave.
- Speaker notes are written once, after all pages and the final order are confirmed.

</details>

<details>
<summary><strong>Company facts and project isolation</strong></summary>

The default `company-facts.json` is an empty template. Before real use, register approved company facts in a private project, each with its source and external-use status.

Client material, brand assets, project `AGENTS.md`, review pages and final deliverables stay in their own project folders; memory lives in `~/.qifei-proposal/memory/`. This repository holds only reusable rules, templates, scripts, tests and an anonymised demo.

</details>

## Repository layout

```text
skills/qifei-proposal-v2/            Main skill: phase packs, references, templates, scripts, tests
  ├─ scripts/draft_studio.py         Draft studio and design review page
  ├─ scripts/memory_box.py           Proposal memory box
  └─ scripts/validate_project.py     Phase gates
skills/grill-me-lite/                Decision interview
skills/proposal-ppt-production/      Page production and assembly
skills/ppt-html-calibration-editor/  HTML calibration editor
demo/visual-sample/                  Anonymised visual demo
scripts/                             Install, bootstrap and release self-test
docs/readme-assets/                  Images for this page
```

Phase details are in [`SKILL.md`](skills/qifei-proposal-v2/SKILL.md); release notes in [`CHANGELOG.md`](CHANGELOG.md).

## Status

v0.3.1 is released on [`codex/qifei-proposal-base`](https://github.com/chenxupeng1990-eng/qifei-proposal-skill/tree/codex/qifei-proposal-base). All 186 Python tests and the release self-test (`python3 scripts/self_test.py`) pass, and the draft studio, design review and memory box have been walked through end to end in a browser on a mock project. Feedback from real projects is welcome.

<a id="license"></a>

## License

This repository is **not unrestricted open source and grants no commercial-use rights**. By default it may be used only for personal learning, research, testing and non-commercial internal evaluation.

It is licensed under [PolyForm Noncommercial 1.0.0](LICENSE); see [`LICENSE`](LICENSE) for the full terms. Commercial projects, paid delivery, commercial services, resale, commercial training, enterprise deployment, redistribution or product integration require prior written permission from the repository Owner. No commercial licence is granted without that written permission.
