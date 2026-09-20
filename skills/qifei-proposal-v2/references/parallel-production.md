# 受控并行生产合同

本合同只适用于页面生产阶段，不把策略、飞书母稿、设计系统或审查工作拆给并行 Agent。

## 入口条件

只有以下条件同时成立，主 Agent 才能把 `production.mode` 设置为
`parallel_after_gates` 并启动波次：

1. 内容冻结已批准，`content_freeze_id` 已写入状态；计划中的 `slide_id` 必须完整且准确覆盖 `deck/deck-spec.json`；
2. 完整提案的飞书母稿已回读确认，`proposal_draft.authority=feishu` 且 `status=verified`；继承模块沿用父项目的冻结稿；独立模块必须有已确认的本地或飞书稿；
3. `design_version` 已确认，且设计系统与 `generation_ready` 门禁已通过；
4. `deck/production/plan.json` 与 `project-state.json` 的冻结 ID、设计版本、稿件 revision 和并行上限一致，并通过 `schemas/production-plan.schema.json`；
5. 生产计划通过 `validate_production_plan.py`。

入口条件没有满足时，使用已有的顺序生产路径；不能为了获得并行速度而绕过门禁。

## 并行边界

- 主 Agent 是唯一的集成负责人，负责读取权威源、创建计划、启动波次、回收结果、重新渲染、复验和更新状态。
- 默认并行上限为 3 个 Agent，硬上限为 6 个 Agent。`max_agents` 表示同一波的并发数，不是可以创建的历史 Agent 总数。
- 每个 Agent 只拥有不重叠的 `slide_id` 集合，并只能写自己声明的页面产物：`deck/chapters/`、`deck/review/`、`deck/production/results/<agent-id>.json` 或 `assets/image2/`。
- Agent 可以读取但不得写入 `project-state.json`、项目 `AGENTS.md`、`DESIGN.md`、飞书快照、策略稿、设计令牌、页面合同、红队报告和 `deck/assembly-ready/`。
- 子 Agent 不得改变策略主轴、章节接口、飞书页序、`design_version`、页面拆分规则、Owner 批准状态或拼装准备状态。
- 资产生成可以并行，公共资产不得由多个 Agent 同时写入；需要共享资产时由主 Agent 先登记并分配唯一写入者。

## 波次协议

1. 主 Agent 从已确认的页面合同生成计划，把页面按章节、镜头或资产依赖拆成互不重叠的任务。
2. 启动一波时，将该波标记为 `in_flight`；每个 Agent 返回自己的页面文件、PNG、资产哈希、渲染日志和未解决问题，不直接改共享状态。
3. 主 Agent 收齐该波结果后，运行尺寸、路径、缺图、字体、页面合同和资产哈希校验，并在真实评审界面查看 montage。
4. 发现一个页面问题时，将原分配标记为 `abandoned`，只回派该页面；发现公共设计、公共组件或设计版本问题时，暂停所有后续波次，回到主 Agent 修改权威源并让受影响页面全部失效。
5. 当前波次通过后，主 Agent 才记录 `verification.status=passed` 或启动下一波。所有波次通过前，不能写入拼装准备库，也不能生成最终讲稿。

`production.status=verified` 只能在所有计划页面都出现在
`verification.verified_slide_ids`、完成最后一次主 Agent 复验并写入
`last_verified_at` 后使用；所有未废弃波次和 Agent 也必须为 `verified`。任何晚于该时间的
`reopen_log` 事件都会使当前生产验证失效。

## 运行适配

- 有原生子 Agent 编排能力时，使用同一份计划并行启动，保持每波不超过 `max_agents`。
- 只有 API Agent 或本地单 Agent 时，可以按同一计划顺序执行；这属于降级执行，不得把顺序执行记录成并行。
- 没有 Node、浏览器、Image2 或视觉复核能力时，按运行 Doctor 的边界停在对应阶段；并行不能替代缺失能力。
- 不使用 Superpower 或无边界的全案 fan-out。并行只加速已经确认的页面生产，不扩大任务范围。
