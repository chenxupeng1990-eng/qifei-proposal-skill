# 提案记忆合同

本文件是三层提案记忆的唯一说明：记什么、存在哪、什么时候加载、谁能写入。记忆跟着 Skill 走，不跟着某个 Agent 走；任何能读文件的 Agent 都用同一套记忆。

## 三层

| 层 | 文件 | 记什么 | 编号 |
|---|---|---|---|
| 项目记忆 | `<项目>/memory/decisions.md` | 本项目确认过的决定、被否掉的方向、客户反馈、表达口径 | `D-0001` |
| Owner 偏好 | `~/.qifei-proposal/memory/owner.md` | Owner 跨项目稳定的判断习惯、审美、禁忌、交付口味 | `O-0001` |
| 方法论 | `~/.qifei-proposal/memory/playbook/*.md` | 跨项目验证过的论证结构、页面载体、反复出现的失败模式 | `PB-0001` |

用户级目录可用环境变量 `QIFEI_MEMORY_HOME` 改到别处。用户级记忆不进任何仓库。

## 条目格式

```markdown
## O-0003｜数据页用判断型标题
- 阶段：strategy, manuscript
- 状态：active
- 日期：2026-10-25
- 来源：某乳品提案逐页确认，Owner 原话"数据页不能写成行业报告"
- 适用：all

数据页标题写判断，不写主题；中立的数据罗列会削弱提案的推动力。
```

- **阶段**：`intake`、`strategy`、`manuscript`、`review`、`visual`、`production`、`export`，或 `all`。
- **状态**：`active`、`retired`，或 `superseded:<新编号>`。被取代的条目保留，用于追溯，但不再加载。
- **来源**：Owner 原话、确认记录编号、评论线程或评审结论。没有来源的条目不能写入。
- **适用**：可选。用品类或场景标签缩小范围，比如 `美妆`、`比稿`。
- **正文**：一到三句，写清怎么做和为什么。

## 加载

每个阶段开始时运行：

```bash
python3 scripts/proposal_memory.py load --project <项目目录> --phase <project-state 的 phase> [--tags 美妆,比稿]
```

- 只加载 `active`、且阶段匹配的条目。顺序是项目记忆、Owner 偏好、方法论，同层内新的在前。
- 默认上限 30 条、8000 字符，超出的会提示条数。不要为了"多带一点"去提高上限，应该整理记忆。
- 记忆用来校准判断，不是事实来源。与本项目已确认的决定、证据台账或 Owner 当下的指示冲突时，以后者为准，并把冲突列为候选更新。

## 写入

- 只有 Owner 确认过的条目才能写入。Agent 只能提出候选，不能自行认定"这是规律"。
- 候选条目要写明：原话或证据、适用范围（只对本项目，还是通用）、建议放进哪一层、是否取代某条旧记忆。
- 事实和数据留在证据台账，记忆只记判断、偏好和打法。
- 新条目和旧条目冲突时，旧条目改为 `superseded:<新编号>`，不要直接删除。
- 写入后运行 `python3 scripts/proposal_memory.py check --project <项目目录>`，结果为 PASS 才算完成。

## 初始化

```bash
python3 scripts/proposal_memory.py init --project <项目目录>
```

这条命令只创建缺失的文件，不覆盖已有记忆。`init_project.py` 新建项目时会自动带上 `memory/decisions.md`。
