# {{INIT:PROJECT_NAME}}｜提案项目基线

> 本文件是本项目内容、策略和治理的最高优先级项目文件。目录确认后生成；发生新确认时先更新本文件，再修改下游产物。

## 1. 项目信息

- 项目 ID：`{{INIT:PROJECT_ID}}`
- Proposal Owner：{{INIT:OWNER}}
- 创建时间：{{INIT:CREATED_AT}}
- 提案类型：比稿型/现场演讲
- 当前客户：{{REQUIRED_AT_PROJECT_AGENTS:CLIENT_NAME}}
- 评审对象：{{REQUIRED_AT_PROJECT_AGENTS:REVIEW_AUDIENCE}}
- 项目范围：{{REQUIRED_AT_PROJECT_AGENTS:PROJECT_SCOPE}}

## 2. 资料与事实边界

- 客户正式资料：见 `inputs/client/`。
- 项目临时参考：见 `inputs/temporary-references/`。
- 公司 Base：由 `qifei-proposal` Skill 提供。
- 项目证据：见 `evidence/evidence-ledger.json`。
- 客户提供的项目事实可直接使用；不得擅自增加新功效、新成绩或新承诺。
- 已确认提案策划书：见 `content/proposal-brief.md`。
- 品牌官方视觉资料：见 `inputs/brand-official/`；提取结论见 `evidence/brand-visual-audit.md`。

## 3. 已确认策略

策略只能在 Grill Me 与提案策划书均确认后填写。

### 3.1 客户问题

{{REQUIRED_AT_PROJECT_AGENTS:CLIENT_PROBLEM}}

### 3.2 核心策略

{{REQUIRED_AT_PROJECT_AGENTS:CORE_STRATEGY}}

### 3.3 核心主张

{{REQUIRED_AT_PROJECT_AGENTS:CORE_CLAIM}}

### 3.4 因果链

{{REQUIRED_AT_PROJECT_AGENTS:CAUSAL_CHAIN}}

### 3.5 策略立场卡

- 确定性机会：{{REQUIRED_AT_PROJECT_AGENTS:CERTAINTY_OPPORTUNITY}}
- 核心矛盾：{{REQUIRED_AT_PROJECT_AGENTS:CORE_TENSION}}
- 鲜明判断：{{REQUIRED_AT_PROJECT_AGENTS:DECISIVE_JUDGMENT}}
- 品牌当前选择为什么正确：{{REQUIRED_AT_PROJECT_AGENTS:WHY_BRAND_IS_RIGHT}}
- 主动选择的策略路径：{{REQUIRED_AT_PROJECT_AGENTS:CHOSEN_PATH}}
- 明确放弃的平庸路径：{{REQUIRED_AT_PROJECT_AGENTS:REJECTED_GENERIC_PATH}}
- 希望客户最终作出的决策：{{REQUIRED_AT_PROJECT_AGENTS:TARGET_DECISION}}

### 3.6 全案情绪曲线

{{REQUIRED_AT_PROJECT_AGENTS:EMOTIONAL_CURVE}}。至少说明共识建立、矛盾或机会显现、压力与期待上升、策略释放、执行证明和最终行动分别由哪些章节承担。

### 3.7 章节策略接口

| 章节 | strategy_input | chapter_claim | reasoning_step | strategy_output | next_chapter_necessity |
|---|---|---|---|---|---|
| CH01 | {{REQUIRED_AT_PROJECT_AGENTS:CH01_INPUT}} | {{REQUIRED_AT_PROJECT_AGENTS:CH01_CLAIM}} | {{REQUIRED_AT_PROJECT_AGENTS:CH01_REASONING}} | {{REQUIRED_AT_PROJECT_AGENTS:CH01_OUTPUT}} | {{REQUIRED_AT_PROJECT_AGENTS:CH01_NEXT_NECESSITY}} |

上一章 `strategy_output` 必须成为下一章 `strategy_input`。章节独立成立但不推进总策略，不得确认。

### 3.8 标题链

- 章节标题链：{{REQUIRED_AT_PROJECT_AGENTS:CHAPTER_TITLE_CHAIN}}
- 全案页面标题链：{{OPTIONAL:SLIDE_TITLE_CHAIN_UNTIL_MANUSCRIPT}}
- 只读标题能否复述完整策略推导：{{REQUIRED_AT_PROJECT_AGENTS:READ_ONLY_TITLE_TEST}}
- 章节或页面是否可任意换序：必须为否

## 4. 已确认目录

{{REQUIRED_AT_PROJECT_AGENTS:APPROVED_OUTLINE}}。每章说明演讲任务、关键结论和预计页面。

## 5. 页面规则

- 一页一个可复述结论和一个演讲任务。
- 每页记录 `belief_shift`、`emotional_target`、`decisive_judgment`、`visible_proof` 和 `next_tension`。
- 每章记录 `strategy_input`、`chapter_claim`、`reasoning_step`、`strategy_output` 和 `next_chapter_necessity`。
- 每章写稿前先确认页面论证链和标题链；确认后一次性生成整章正文并写入飞书，章节确认前执行连续朗读和只读标题测试。
- 逐页是评论和确认粒度，不是默认生成粒度；除关键创意、完整脚本或争议页外，不逐页串行调用生成。
- 飞书PPT提案成稿是内容阶段的唯一权威母版，本地章节稿只作同步备份；每轮飞书写入或评论修改后必须重新抓取整份文档，保存 `content/feishu/proposal-draft.md`，并在 `project-state.json.proposal_draft` 记录文档、revision、时间、快照哈希和已确认页序。
- 本地 Markdown 草稿、写入接口返回成功或 Owner 的口头“确认”都不能替代飞书整份回读。飞书不可用时状态必须为 `local_fallback_pending_sync`，不得确认章节、进入全稿审查、内容冻结或视觉生产。
- 视觉方向选择必须提交 2-3 套真实 Image2 代表页样张并登记视觉命题、视觉家族、代表页、资产与提示词。纯文字方向说明、Moodboard 或 HTML/CSS 换色不能批准为视觉方向。
- 设计语言校准按正式页数选择 compact/standard/extended 档位，最低分别为6/8/10张；以覆盖本案设计风险为准，不机械生成固定十页。
- 每页按“核心内容、逻辑展开、上屏内容、讲解方向、策略过桥、视觉生成建议、证据来源”组织；讲解方向不扩写为完整讲稿。
- 正确但没有观点的页面退回；有观点但没有证据则补证；有观点、有证据但不能推动客户决策则重写。
- 每页使用稳定 `slide_id`。
- 内容与视觉阶段只记录页面演讲任务，不生成完整讲稿。
- 全部PPT页面、拆页与最终页序确认后，完整讲稿保存到飞书文稿；本项目只存 `speaker_doc_anchor` 或同步 Markdown。
- 本项目讲者身份、专业程度和现场语气：{{REQUIRED_AT_SPEAKER_NOTES:SPEAKER_PROFILE}}。最终讲稿按真实讲者口吻生成，并按最终页码连续朗读确认。
- 方法论、完整样例、工作件和高表现力 Demo 不强行压在同一页。
- 公司介绍和公司案例放在提案前部，不穿插进入正式客户策略。

## 6. 角色

- Proposal Owner：{{INIT:OWNER}}
- 客户/项目负责人：{{OPTIONAL:CLIENT_PROJECT_LEAD}}
- 策划：{{OPTIONAL:PLANNER}}
- 数据分析师：{{OPTIONAL:DATA_ANALYST}}
- 运营专家：{{OPTIONAL:OPERATIONS_EXPERT}}
- 设计/视觉：{{OPTIONAL:DESIGNER}}

## 7. 门禁

- 目录确认后才能生成本文件。
- 背景资料提交后必须先用 `grill-me-lite` 逐题确认提案策划书；未确认不得进入策略与目录。
- 策略立场卡和全案情绪曲线未确认，不得生成正式目录和PPT提案成稿。
- 全部正式PPT页面与最终页序未确认，不得生成完整讲稿。
- PPT页面换序、拆页、合页、标题或核心内容改变时，对应讲稿及前后转场自动过期。
- 章节策略接口未闭合、章节可以任意换序或只读标题无法复述总策略，不得确认目录、章节或内容冻结。
- 全部章节逐页确认后只启动一次新的审查 Agent 做全稿成稿完整性审查，只检查逻辑、表达、衔接、拆页和视觉载体；不得质疑Owner已确认事实、策略和场外决策，不得引入安全、合规、风险或资料审计。
- 不再执行逐章红队或第二轮重复内容红队；全稿审查通过后由 Owner 冻结内容。
- 只有 Proposal Owner 可以冻结或重开页面。
- 内容冻结后才能进入视觉方向与样张。
- 品牌官方视觉资料和视觉审计均核准后，才能进入正式视觉方向。
- 初始方向样张确认后，先完成并逐页确认 `deck/design-calibration.html`：首页、目录页、3 种章节页、低/中/高密度内容页、透明 PNG 叠加页和结尾感谢页。
- 设计语言校准集确认后生成 `DESIGN.md`；正文页冻结品牌语言与组件合同，但保留内容布局弹性。
- `DESIGN.md` 必须引用品牌来源 ID，并融入视觉符号、规范和色卡。
- `DESIGN.md` 确认后逐页确定 HTML 或 Image2直出PNG路线；透明 PNG 只能进入批准槽位并必须含真实 Alpha 通道。
- 评论循环只使用 HTML＋逐页PNG，或直出PNG＋Codex浏览器原生评论，不重复拼装 PPT/PDF。
- 评论解决不等于页面确认；只有 Proposal Owner 明确确认对应页面，才能写入 `deck/assembly-ready/`。
- 全部正式页面进入拼装准备库且 Owner 明确批准最终拼装后，才允许一次性生成 PPT/PDF。
- 内容 QA 和视觉 QA 分别通过后才能导出。

## 8. 已确认页面与重开记录

由 `project-state.json` 记录机器状态；此处只记录影响全案的人工决定。
