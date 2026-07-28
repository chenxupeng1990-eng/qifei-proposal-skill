---
name: qifei-proposal-v2
description: Progressive-disclosure version of the company proposal workflow. Use for company-specific competitive proposals when Codex should load only the rules for the current project phase while preserving Feishu, strategy, Image2, design-calibration, review, speaker-note, and export gates.
---

# 公司提案总控 V2

V2 与 `$qifei-proposal` 并行，不替换 V1。它使用相同项目结构和机器校验器，但把执行规则拆成阶段包，避免无关规则同时占用上下文。

## 永久规则

1. 完整读取本文件与 [agent.md](agent.md)。
2. 运行 `python3 scripts/check_suite_dependencies.py`；依赖缺失时停止。
3. 读取项目 `AGENTS.md` 与 `project-state.json`，以 `phase` 选择且只选择一个当前阶段包。
4. 完整读取当前阶段包；只读取该阶段包明确列出的 reference，不预读未来阶段。
5. 当前阶段产物必须通过 `python3 scripts/validate_project.py <项目目录>`；机器通过不等于 Owner 批准。
6. Proposal Owner 是唯一阶段批准者。口头确认、评论关闭、写入成功或 Agent 自检不能替代客观门禁。
7. 用户已确认的项目事实、策略与场外决定是只读权威；不得在后续审查中重新审判。
8. 对外提案必须有立场、观点和决策推动；中立、保守或只做风险判断不能替代提案策划。
9. 飞书提案文档是内容确认阶段的唯一权威母版；本地 Markdown 只作回读快照或待同步草稿。
10. 内容冻结前不得生产正式视觉；全部正式页面与最终页序确认前不得生成完整讲稿。
11. 视觉方向必须提交 2–3 套真实 Image2 代表页；纯方向说明和 HTML/CSS 换色不能通过。
12. 每张正式页先确定核心思想和最佳载体，再分配 Image2 与 HTML；Image2 是视觉底线，不是内容决策者。
13. 设计校准按页数采用 `compact`、`standard` 或 `extended`，用最少样张覆盖真实设计风险。
14. 不跨阶段执行，不因任务简单、用户连续说“确认”或已有文件而补记批准。

## 阶段路由

| `project-state.json.phase` | 必须读取的阶段包 |
|---|---|
| `intake`, `requirements` | [phase-packs/01-intake-brief.md](phase-packs/01-intake-brief.md) |
| `strategy`, `project_agents` | [phase-packs/02-strategy-outline.md](phase-packs/02-strategy-outline.md) |
| `manuscript` | [phase-packs/03-manuscript-feishu.md](phase-packs/03-manuscript-feishu.md) |
| `full_redteam`, `content_frozen` | [phase-packs/04-full-draft-review.md](phase-packs/04-full-draft-review.md) |
| `visual_direction`, `visual_sample` | [phase-packs/05-visual-direction.md](phase-packs/05-visual-direction.md) |
| `design_calibration`, `design_system` | [phase-packs/06-design-calibration.md](phase-packs/06-design-calibration.md) |
| `generation`, `review` | [phase-packs/07-page-production-review.md](phase-packs/07-page-production-review.md) |
| `speaker_notes`, `qa`, `export` | [phase-packs/08-speaker-export.md](phase-packs/08-speaker-export.md) |

未知 phase 立即停止，不猜测阶段。

## 通用命令

```bash
python3 scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner>
python3 scripts/validate_project.py <项目目录>
```

其余命令仅在对应阶段包要求时使用。

