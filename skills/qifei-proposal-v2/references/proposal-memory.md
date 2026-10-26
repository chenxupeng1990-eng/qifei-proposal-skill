# 提案记忆合同

本文件是三层提案记忆的唯一说明：记什么、存在哪、什么时候加载、谁能写入。记忆跟着 Skill 走，不跟着某个 Agent 走；任何能读文件的 Agent 都用同一套记忆。

## 三层

| 层 | 文件 | 记什么 | 编号 |
|---|---|---|---|
| 项目记忆 | `~/.qifei-proposal/memory/projects/<project_id>/decisions.md` | 本项目确认过的决定、被否掉的方向、客户反馈、表达口径 | `D-0001` |
| Owner 偏好 | `~/.qifei-proposal/memory/owner.md` | Owner 跨项目稳定的判断习惯、审美、禁忌、交付口味 | `O-0001` |
| 方法论 | `~/.qifei-proposal/memory/playbook/*.md` | 跨项目验证过的论证结构、页面载体、反复出现的失败模式 | `PB-0001` |

三层都放在同一个记忆库目录 `~/.qifei-proposal/memory/`（可用环境变量 `QIFEI_MEMORY_HOME` 改到别处），不放进项目文件夹或母稿旁边，也不进任何仓库。
- 项目按 `project-state.json` 的 `project_id` 分目录；没有 `project_id` 时用项目文件夹名。
- 第一次对某个项目运行带 `--project` 的命令（`load`、`signals`、`init` 等）时，会在 `project.json` 里登记项目名称和路径。

## 记忆库（统一查看和管理）

```bash
python3 scripts/memory_box.py [--port 8770] [--open]
```

本地打开一个独立页面，集中查看所有层级的记忆：
- **待审候选**：所有项目里还没处理的候选，有新候选时实时出现。
- **全部生效记忆**：按 Agent 加载的顺序排列。
- **Owner 偏好、方法论、每个项目的项目记忆**：分别列出。
- 可以按阶段筛选、搜索，勾选"含已停用"查看停用和被取代的条目。
- 每条记忆可以编辑结论、正文、阶段和适用范围，或者停用、恢复；日期和来源保持原样。
- 页面只监听本机，接口校验一次性令牌和 Host；所有改动都直接写回 Markdown 文件。

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

- 只加载 `active` 的条目，范围是当前阶段和它之前的各阶段（阶段顺序：intake → strategy → manuscript → review → visual → production → export），后面阶段的条目不提前加载。后期回头改前面的内容时，前面阶段的记忆同样要遵守；这类条目会标注"前序阶段"。
- 顺序是项目记忆、Owner 偏好、方法论；同一层里当前阶段在前，然后是较早的阶段，同阶段内新的在前。

### 关闭记忆（全局）

- `python3 scripts/proposal_memory.py off` 关闭，`on` 重新打开，`status` 查看当前状态；也可以在记忆库顶部勾选"启用记忆"。设置保存在记忆目录的 `settings.json`，对所有项目生效。
- 临时覆盖：环境变量 `QIFEI_MEMORY=off` 或 `on` 优先于保存的设置（记忆库里的开关此时不能切换）。
- 关闭后：`doctor.py` 只提示"提案记忆已关闭"；`load`、`signals`、`advance`、`note` 不读取也不写入；`validate_project.py` 跳过信号门禁和读取检查。Agent 跳过 `note` 和 `advance`，换阶段直接改 `phase`。
- 已有的记忆和候选原样保留，记忆库照常可以查看和整理；重新打开后从当前阶段继续使用。

### 不依赖 Agent 记得去读

读取记忆不只靠第 5 条规则，另外有三道保障：
- **`doctor.py --project <项目目录>`**：开工检查时把本阶段的记忆一起输出（`--json` 时在 `proposal_memory.text` 里）。
- **读取回执**：`load` 和 `doctor` 会在 `projects/<project_id>/receipt.json` 记下读取时的阶段和记忆指纹。
- **`validate_project.py`**：本阶段有适用的记忆、但回执缺失、阶段不符或记忆在读取后有更新时，校验报 `proposal memory:` 错误，并把当前记忆附在输出末尾；读完后再运行一次即可通过。
- 默认上限 30 条、8000 字符，超出的会提示条数。不要为了"多带一点"去提高上限，应该整理记忆。
- 记忆用来校准判断，不是事实来源。与本项目已确认的决定、证据台账或 Owner 当下的指示冲突时，以后者为准，并把冲突列为候选更新。

## 写入

- 只有 Owner 确认过的条目才能写入。Agent 只能提出候选，不能自行认定"这是规律"。
- 候选条目要写明：原话或证据、适用范围（只对本项目，还是通用）、建议放进哪一层、是否取代某条旧记忆。

### 从工作台和对话提炼候选（每个阶段放行时）

- **对话里的更正**：Owner 在对话里给出能复用的更正（例如"不允许白底产品图"），当场运行 `python3 scripts/proposal_memory.py note --project <项目目录> "<Owner 原话>" [--context S05 设计校准]` 记下，编号 `N-0001`。这类更正不在工作台里，不记就会丢。
- **换阶段只用一个命令**：`python3 scripts/proposal_memory.py advance --project <项目目录> --to <新阶段>`。它一次做完三件事：汇总离开阶段的信号（下面第 1 步）、提示写候选（第 2 步）、读取新阶段的记忆并留下回执。写完候选再改 `phase`。下面的分步命令仍然可用，适合单独补跑。
- **门禁**：`signals` 和 `advance` 每次运行都会留下信号回执。进入母稿之后的阶段时，`validate_project.py` 要求回执来自上一阶段或更晚，否则报 `proposal memory:` 错误。

1. `advance` 的第一部分，或单独运行 `python3 scripts/proposal_memory.py signals --project <项目目录>`。它汇总工作台里已决定的评论（`C-0001`）、Owner 的修改及改前改后（`R262`，即修订号）和章节确认记录；已被候选或记忆引用过的信号默认不再显示，`--all` 显示全部。
2. Agent 从中挑出能在后续页面、阶段或其他项目复用的判断，写进 `signals` 输出里给出的项目候选文件（`projects/<project_id>/candidates.md`），每次最多 8 条。一次性的措辞修改、测试评论不写。

```markdown
## MC-0001｜可见证明写证据，不写设计方向
- 建议层级：owner
- 阶段：manuscript
- 状态：candidate
- 日期：2026-10-25
- 来源：C-0001、R262

核心内容里的可见证明要回答"凭什么"，引用证据编号；载体写进视觉生成建议。
```

   - **建议层级**：`owner`、`project` 或 `playbook`。
   - **来源**：必须写信号编号，`check` 会校验。
   - Agent 只写 `candidate`，不改状态。
3. Owner 在记忆库的"待审候选"里，可以先改结论、正文、写入层级和阶段，再逐条"采纳"或"丢弃"。也可以用命令：`proposal_memory.py accept MC-0001 --project <项目目录> [--layer owner] [--title …]` 或 `reject MC-0001`。这两个命令是 Owner 的操作，Agent 不代为执行。
4. 采纳会在对应层级追加一条新编号（`O-`、`D-`、`PB-`）的 `active` 条目，来源记为"候选来源；Owner 采纳 日期（MC-xxxx）"，候选状态改为 `accepted:<新编号>`；丢弃改为 `rejected`。处理过的候选不能再改判。
- 事实和数据留在证据台账，记忆只记判断、偏好和打法。
- 新条目和旧条目冲突时，旧条目改为 `superseded:<新编号>`，不要直接删除。
- 写入后运行 `python3 scripts/proposal_memory.py check --project <项目目录>`，结果为 PASS 才算完成。

## 初始化

```bash
python3 scripts/proposal_memory.py init --project <项目目录>
```

这条命令只创建缺失的文件，不覆盖已有记忆。
