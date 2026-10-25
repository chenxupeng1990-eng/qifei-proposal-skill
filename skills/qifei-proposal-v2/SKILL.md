---
name: qifei-proposal-v2
description: 公司提案总控：把品牌需求做成有观点、能打动评审、可视觉化交付的竞争性提案或提案模块（比稿、品牌提案、营销方案 PPT、飞书提案母稿、提案视觉与讲稿、导出 PNG/PDF/PPTX）。按项目阶段渐进加载规则，内置策略、内容、视觉、评审与导出门禁，支持 Codex、API Agent 与本地运行环境。用户说“做提案”“比稿”“写方案 PPT”“继续这个提案项目”“做提案里的某个模块”时使用。不用于通用文档排版、单张海报或与提案无关的 PPT 美化。已有确认的页面大纲和视觉方向、只需要出页面时，用 proposal-ppt-production。
---

# 公司提案总控 V2

V1 `$qifei-proposal` 已弃用并从仓库移除，一律使用 V2。V2 沿用 V1 的项目结构和机器校验器，把执行规则拆成阶段包，避免无关规则同时占用上下文。

## 永久规则

1. 完整读取本文件与 [agent.md](agent.md)。
2. 先按 [references/task-modes-and-runtime.md](references/task-modes-and-runtime.md) 确定 `task_mode`，运行 `doctor.py`，向用户声明本次可交付能力和边界（最低可用配置见 [references/environment-degradation.md](references/environment-degradation.md)）；能力缺失只阻塞实际依赖它的阶段。
3. Python可用后运行 `python3 scripts/check_suite_dependencies.py`；完整套件缺失时停止，环境能力缺失按Doctor结果路由。
4. 读取项目 `AGENTS.md` 与 `project-state.json`，以 `phase` 选择且只选择一个当前阶段包。
5. 完整读取当前阶段包；只读取该阶段包明确列出的 reference，不预读未来阶段。随后运行 `python3 scripts/proposal_memory.py load --project <项目目录> --phase <当前阶段>`，按 [references/proposal-memory.md](references/proposal-memory.md) 使用记忆：记忆校准判断，不是事实；候选记忆经 Owner 确认后才写入。
6. 当前阶段产物必须通过 `python3 scripts/validate_project.py <项目目录>`；机器通过不等于 Owner 批准。
7. Proposal Owner 是唯一阶段批准者。口头确认、评论关闭、写入成功或 Agent 自检不能替代客观门禁。
8. 用户已确认的项目事实、策略与场外决定是只读权威；不得在后续审查中重新审判。
9. 对外内容必须有立场、观点和决策推动；中立、保守或只做风险判断不能替代策划。
10. 内容权威由任务模式决定：完整提案默认飞书，继承模块沿用父项目，独立模块可明确选择飞书或本地Markdown。
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
python3 scripts/doctor.py --task-mode <full_deck|inherited_module|standalone_module> --json
python3 scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner> --task-mode <模式>
python3 scripts/validate_project.py <项目目录>
```

其余命令仅在对应阶段包要求时使用。
