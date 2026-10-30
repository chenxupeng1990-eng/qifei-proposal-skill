---
name: qifei-proposal-v2
description: 公司提案总控：把品牌需求做成有观点、能打动评审、可视觉化交付的竞争性提案或提案模块（比稿、品牌提案、营销方案 PPT、飞书提案母稿、提案视觉与讲稿、导出 PNG/PDF/PPTX）。按项目阶段渐进加载规则，内置策略、内容、视觉、评审与导出门禁，支持 Codex、API Agent 与本地运行环境。也用于品牌手册、品牌视觉画册这类以视觉表现为主的演示文件（视觉表现型路径：整页生图、文字一并画入）。用户说“做提案”“比稿”“写方案 PPT”“继续这个提案项目”“做提案里的某个模块”“做品牌手册”“做品牌画册”时使用。不用于通用文档排版、单张海报或与提案无关的 PPT 美化。已有确认的页面大纲和视觉方向、只需要出页面时，用 proposal-ppt-production。
---

# 公司提案总控 V2

V1 `$qifei-proposal` 已弃用并从仓库移除，一律使用 V2。V2 沿用 V1 的项目结构和机器校验器，把执行规则拆成阶段包，避免无关规则同时占用上下文。

## 永久规则

1. 完整读取本文件与 [agent.md](agent.md)。
2. 先按 [references/task-modes-and-runtime.md](references/task-modes-and-runtime.md) 确定 `task_mode` 和任务性质 `task_nature`：开项目时先问用户这份 PPT 要“强逻辑叙述”（`persuasive`）还是“视觉表现力”（`visual_showcase`），按需求给出建议和理由，由用户选定，写进策划书的“表达方式”并用 `init_project.py --task-nature` 记录（问法见 runtime 说明 1.1 节）；运行 `doctor.py --project <项目目录>`（同时输出本阶段的提案记忆；doctor 看不到 Agent 自己的工具，能生图时加 `--image-provider <名称>`，能看图时加 `--visual-understanding`，有 Codex 原生浏览器评论时加 `--native-comments`，见 runtime 说明第 3 节），向用户说明本次能交付到哪一步。doctor 列出能力缺口（`GAP`）时，不得默认降级：先逐项问用户能否按列出的办法补齐，补齐后重跑 doctor；用户明确选择暂不补齐，才运行 `doctor.py --project <项目目录> --accept-gap <缺口> --by <Owner>` 记录，此后缺失的能力只阻塞依赖它的阶段（见 [references/environment-degradation.md](references/environment-degradation.md)）。doctor 输出 `UPDATE` 行时，用一两句大白话转告用户有新版本、更新了什么、说“更新提案 skill”就能更新；不打断当前任务，不自动更新。用户要更新时运行 `python3 scripts/update_skill.py run`，完成后提醒用户重启 Agent；用户不想再收到提醒时运行 `update_skill.py off`。
3. Python可用后运行 `python3 scripts/check_suite_dependencies.py`；完整套件缺失时停止，环境能力缺失按Doctor结果路由。
4. 读取项目 `AGENTS.md` 与 `project-state.json`，以 `phase` 选择且只选择一个当前阶段包。
5. 完整读取当前阶段包；只读取该阶段包明确列出的 reference，不预读未来阶段。提案记忆按 [references/proposal-memory.md](references/proposal-memory.md) 使用，Agent 只需记住两个命令：Owner 在对话里给出可复用的更正时，当场运行 `proposal_memory.py note`；换阶段时运行 `proposal_memory.py advance --project <项目目录> --to <新阶段>`，按输出写候选、读新阶段记忆，再改 `phase`。记忆校准判断，不是事实；`doctor.py` 和 `validate_project.py` 会带出记忆并检查是否读过。用户要求关闭记忆时运行 `proposal_memory.py off`（全局生效）；`doctor.py` 显示提案记忆已关闭时，跳过 `note` 和 `advance`。
6. 当前阶段产物必须通过 `python3 scripts/validate_project.py <项目目录>`；机器通过不等于 Owner 批准。
7. Proposal Owner 是唯一阶段批准者。口头确认、评论关闭、写入成功或 Agent 自检不能替代客观门禁。
8. 用户已确认的项目事实、策略与场外决定是只读权威；不得在后续审查中重新审判。
9. 对外内容必须有立场、观点和决策推动；中立、保守或只做风险判断不能替代策划。
10. 内容权威由任务模式决定：完整提案默认工作台（可选飞书），继承模块沿用父项目，独立模块可选工作台、飞书或本地Markdown。
11. 不跨阶段执行，不因任务简单、用户连续说“确认”或已有文件而补记批准；视觉、校准、并行生产和讲稿的专门规则只在对应阶段包中生效。

## 阶段路由

| `project-state.json.phase` | 必须读取的阶段包 |
|---|---|
| `intake`, `requirements` | [phase-packs/01-intake-brief.md](phase-packs/01-intake-brief.md) |
| `strategy`, `project_agents` | [phase-packs/02-strategy-outline.md](phase-packs/02-strategy-outline.md) |
| `manuscript` | [phase-packs/03-manuscript-feishu.md](phase-packs/03-manuscript-feishu.md) |
| `full_redteam`, `content_frozen` | [phase-packs/04-full-draft-review.md](phase-packs/04-full-draft-review.md) |
| `visual_direction` | [phase-packs/05-visual-direction.md](phase-packs/05-visual-direction.md) |
| `design_calibration`, `design_system` | [phase-packs/06-design-calibration.md](phase-packs/06-design-calibration.md) |
| `generation`, `review` | [phase-packs/07-page-production-review.md](phase-packs/07-page-production-review.md) |
| `speaker_notes`, `qa`, `export` | [phase-packs/08-speaker-export.md](phase-packs/08-speaker-export.md) |

未知 phase 立即停止，不猜测阶段。

## 通用命令

```bash
python3 scripts/doctor.py --task-mode <full_deck|inherited_module|standalone_module> --project <项目目录> --json
python3 scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner> --task-mode <模式>
python3 scripts/validate_project.py <项目目录>
```

其余命令仅在对应阶段包要求时使用。
