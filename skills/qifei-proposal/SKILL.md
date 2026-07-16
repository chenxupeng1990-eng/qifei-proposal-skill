---
name: qifei-proposal
description: Govern and produce QIFEI/祈飞 client-specific competitive proposals for Douyin brand operations, live commerce, short video, paid media, influencer marketing, integrated campaigns, retail AI systems, tenders, and pitches. Use when Codex must grill stakeholders after background intake, confirm a proposal brief, turn tender/client materials plus company knowledge into a fully confirmed strategy, extract official brand visual references into DESIGN.md, produce chapter-by-chapter and page-by-page PPT manuscripts, Feishu speaker notes, Image2 assets, an HTML master deck, PNG/PDF/image-based PPT preview, or audit an existing proposal against requirements, evidence, brand, strategy, and delivery gates.
---

# 祈飞提案总控

把提案视为受控的内容、证据与视觉生产流程。先确认信息，再生成成品；任何视觉质量都不能替代内容确认。

## 启动规则

1. 先读取项目根目录 `AGENTS.md`；若只有旧式 `agent.md`，将其作为项目输入，不静默改名。
2. 读取 `project-state.json`，只执行当前阶段允许的动作。
3. 读取客户资料、临时参考资料和标书。处理 PDF、文档、表格或飞书内容时，调用对应 Skill。
4. 读取公司 Base 时先看 [references/company-base.md](references/company-base.md)；需要数字、履历、案例成绩或来源页时再读 [references/company-facts.json](references/company-facts.json)。
5. 需要判断资料权威、版本、证据和保密边界时，读取 [references/knowledge-policy.md](references/knowledge-policy.md)。
6. 不把锐步方案的视觉或客户策略当作通用模板。它只提供公司介绍的内容顺序原型和 Base 事实来源。
7. 背景资料提交后，调用 `grilling` Skill 逐题确认项目决策；视觉阶段开始前，确认 `inputs/brand-official/` 已上传客户品牌官方视觉参考。

## 权威层级

从高到低使用：

1. 当前项目中经 Proposal Owner 明确确认的决定与冻结记录。
2. 项目 `AGENTS.md`、已确认章节稿和 `project-state.json`。
3. 客户正式资料、标书和客户书面确认。
4. 项目临时上传资料。
5. 公司 Base。
6. 公开资料。

冲突时暂停受影响部分，记录冲突并交 Proposal Owner 决定。不要用公开资料推翻客户提供的项目事实。

## 强制工作流

严格按下列顺序推进。详细门禁见 [references/workflow.md](references/workflow.md)。

1. **立项与资料审计**：初始化目录，登记客户资料、标书、临时参考和缺口。
2. **Grill Me 与提案策划书**：背景资料提交后立即调用 `grilling`，一次只问一个决策问题并提供推荐答案；达成共同理解后生成 `content/proposal-brief.md`，由 Owner 确认。若会话已安装并提供 `Visualize:visualize`，可生成决策树、范围地图或策划书确认视图；可视化只辅助确认，不替代书面策划书。
3. **策略与动态目录**：仅在 Grill Me 和提案策划书确认后，形成策略因果链、提案主张和目录；让用户确认。
4. **生成项目 `AGENTS.md`**：目录确认后立即生成，记录项目事实、策划书、策略、角色、页级规则和门禁。
5. **逐章逐页 PPT 讲稿**：逐页确认标题、上屏文案、证据、页面角色、视觉意图和演讲任务。讲稿规则见 [references/content-and-speaker.md](references/content-and-speaker.md)。
6. **逐章对抗检测**：每章全部页面确认后，启动新的子 Agent，对照标书、策划书、策略、证据和项目 `AGENTS.md` 做对抗检查；修复后由用户再次确认。
7. **全案对抗检测与内容冻结**：所有章节通过后再做一次全案检测。只有 Proposal Owner 可冻结或重新打开页面。
8. **品牌官方视觉审计**：要求用户上传品牌官方视觉参考至 `inputs/brand-official/`，登记来源 ID，提取品牌视觉符号、Logo 规则、字体、色卡、图形、材质、摄影和禁忌，写入 `evidence/brand-visual-audit.md` 并确认。没有官方资料不得进入视觉方向。
9. **视觉方向与样张**：依据冻结内容和品牌视觉审计提出 2-3 个客户定制方向；生成代表页样张并取得确认。
10. **生成 `DESIGN.md`**：把官方品牌视觉审计和确认样张共同编译为可执行视觉规范，并记录来源 ID。设计与生成规则见 [references/design-and-generation.md](references/design-and-generation.md)。
11. **合同式 HTML 生成**：把冻结内容编译为 `deck-spec.json` 和 `slide-contracts.json`，再生成 Image2 素材和 HTML。HTML 是唯一视觉母版。
12. **本地批注与修订**：批注写入 `reviews/review-comments.json`。修订源文件并重建 HTML，不让浏览器直接覆盖冻结内容。
13. **双轴 QA 与导出**：分别完成内容忠实度和视觉质量 QA，修复只回到 HTML 源，再导出 HTML、PNG、PDF 和图片型 PPT 预览。

## 不可跨越的门禁

- Grill Me 未完成或提案策划书未确认：不得进入策略与目录。
- 目录未确认：不得生成项目 `AGENTS.md` 之后的内容。
- 逐章逐页讲稿未确认：不得生成视觉成品。
- 逐章与全案对抗检测未通过：不得内容冻结。
- 内容未冻结：不得调用 Image2 生产正式素材。
- 未上传并核准品牌官方视觉参考，或未完成品牌视觉审计：不得提出正式视觉方向或生成样张。
- 样张未确认：不得生成 `DESIGN.md` 或全量页面。
- `DESIGN.md` 未记录品牌视觉来源 ID、视觉符号和色卡：不得批准设计系统。
- `DESIGN.md` 未确认：不得全量渲染。
- 内容 QA 或视觉 QA 未通过：不得导出最终文件。
- 缺失信息只阻塞受影响页面；若缺口改变策略、报价、承诺或核心结论，则阻塞对应阶段。

## 角色与责任

- **Proposal Owner**：唯一的门禁批准者、内容冻结者和页面重开批准者。
- **客户/项目负责人**：客户沟通、资料确认、范围与承诺管理。
- **策划**：策略、目录、章节逻辑、逐页内容与演讲任务。
- **数据分析师**：数据口径、证据账本、指标与经营模型。
- **运营专家**：直播、短视频、投放、货盘、达人和执行真实性。
- **设计/视觉 Agent**：样张、`DESIGN.md`、Image2 资产、HTML 视觉实现。
- **对抗检测子 Agent**：独立找错，不重写方案；每轮使用新的上下文和原始资料。

## 公司介绍与案例

- 公司介绍和选中的公司案例统一放在提案前部，沿用公司现有介绍逻辑，不穿插在正式客户策略正文中。
- 根据客户任务动态选择最相关案例；每个案例只证明一个与本项目有关的能力。
- 不把客户定制策略原型包装成祈飞既有案例。
- GMV、投放金额、服务品牌数、奖项、资质、人员履历和案例成绩默认沿用公司 Base 的核准表述，直到人工替换；对外不展示内部版本规则。
- 不生成 Logo 墙代替案例，不编造缺失成绩。

## 内容与讲稿

- 一页只承担一个可复述结论和一个演讲任务。
- 内容必须完成“事实/问题 -> 判断 -> 策略或动作 -> 结果/验证”的逻辑。
- 每页使用稳定 `slide_id`；HTML、章节稿、证据账本和飞书演讲稿都用它关联。
- 飞书文稿保存逐页演讲稿，HTML 保存上屏内容。飞书不可用时先生成结构化 Markdown，待恢复后同步。
- 对外页面不出现 `待确认`、内部权威等级、版本状态、风险备注或 Agent 工作痕迹。

## 生成与验证命令

从 Skill 根目录运行：

```powershell
python scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner>
python scripts/validate_project.py <项目目录>
python scripts/freeze_deck_spec.py <项目目录> --approved-by <Owner> --approval-id <确认记录>
python scripts/validate_deck_spec.py <项目目录>
python scripts/render_deck.py <项目目录>
node scripts/serve_review.mjs <项目目录>
node scripts/export_deck.mjs <项目目录>
```

首次导出前在 Skill 根目录执行 `npm install`。导出需要本机 Chrome、Edge 或 Chromium。

## 生成层原则

- 独立实现，不依赖或复制 Dashi PPT 的代码或专有导出引擎。
- `AGENTS.md` 是项目内容与治理权威；`DESIGN.md` 是视觉权威；`deck-spec.json` 是冻结内容的编译产物；HTML 是视觉母版。
- 使用页面合同限制文字、数组和媒体槽位；字符预算只做预检，最终必须在浏览器测量溢出和越界。
- Image2 只负责背景、主视觉、场景、概念图和高表现力模块；正文、数据、图表和注释由 HTML 统一排版。
- 正式资产只允许项目内相对路径。禁止远程 URL、绝对本机路径、`file://` 和 `data:` 进入最终 `deck-spec.json`。
- Image2 不可用时输出提示词包，不擅自切换模型。

## 保密与外部调用

- 客户原始资料保留本地。
- 发给搜索、Image2 或其他外部服务的提示词必须去标识化，只保留完成任务必要的信息。
- 不上传标书全文、报价、联系人、账号、内部批注或未公开经营数据。
- 透明 PNG 公司素材库只接受去标识化且经人工批准的资产；项目资产默认隔离。

## 完成标准

只有同时满足以下条件才宣布完成：

- 所有章节和页面有确认记录。
- 逐章及全案对抗检测通过。
- 内容冻结与视觉样张确认可追溯。
- `AGENTS.md`、`DESIGN.md`、`deck-spec.json` 与 HTML 无漂移。
- Grill Me 完成记录、提案策划书、品牌官方视觉来源和品牌视觉审计均可追溯。
- 内容 QA 和视觉 QA 均通过。
- HTML、PNG、PDF、图片型 PPT 预览和飞书演讲稿页码一致。
- 最终文件不含内部备注、本机路径、未确认占位符或客户敏感信息泄漏。
