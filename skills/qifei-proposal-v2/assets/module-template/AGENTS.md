# {{INIT:PROJECT_NAME}}｜内容模块基线

> 本文件只治理当前模块。父项目已经确认的事实、总策略和设计版本为只读输入。

## 1. 模块信息

- 模块 ID：`{{INIT:PROJECT_ID}}`
- Proposal Owner：{{INIT:OWNER}}
- 任务模式：`{{INIT:TASK_MODE}}`
- 内容权威：`{{INIT:CONTENT_AUTHORITY}}`
- 交付层级：`{{INIT:DELIVERABLE_LEVEL}}`
- 服务对象：{{REQUIRED_AT_PROJECT_AGENTS:MODULE_AUDIENCE}}
- 模块范围：{{REQUIRED_AT_PROJECT_AGENTS:MODULE_SCOPE}}

## 2. 资料与继承边界

- 本次资料：`inputs/client/`。
- 临时参考：`inputs/temporary-references/`。
- 继承模块只使用父项目登记的冻结内容、设计版本和品牌资产；不得静默改写父项目。
- 独立模块使用项目明确声明的本地或飞书内容权威。

## 3. 模块策略接口

- `strategy_input`：{{REQUIRED_AT_PROJECT_AGENTS:MODULE_STRATEGY_INPUT}}
- `module_claim`：{{REQUIRED_AT_PROJECT_AGENTS:MODULE_CLAIM}}
- `strategy_output`：{{REQUIRED_AT_PROJECT_AGENTS:MODULE_STRATEGY_OUTPUT}}
- 页面论证链：{{REQUIRED_AT_PROJECT_AGENTS:MODULE_PAGE_CHAIN}}
- 只读标题测试：{{REQUIRED_AT_PROJECT_AGENTS:READ_ONLY_TITLE_TEST}}

模块每页必须推进同一模块判断。页面可以任意换序、只是在并列罗列信息或无法交给后续内容时，不得冻结。

## 4. 内容与视觉规则

- 按模块一次生成全部正文，再逐页评论与确认。
- 每页一个可复述判断、一个演讲任务和一个主视觉载体。
- `inherited_module` 复用父项目 `DESIGN.md` 和设计令牌。
- `standalone_module` 至少确认一套真实生成的视觉基线；不强制制作完整长提案校准集。
- 评论、QA和生成成功都不等于Owner批准。
- 模块默认不生成全案讲稿；仅在明确要求且最终页序锁定后生成对应模块讲稿。

## 5. 门禁

- 模块简报确认后才能进入模块策略。
- `strategy_input → module_claim → strategy_output` 未闭合不得生成正文。
- 模块确认稿和稳定 `slide_id` 未完成不得冻结内容。
- 没有图像生成能力时不得批准正式视觉。
- 没有视觉识别或人工视觉复核时不得批准视觉QA。
- 只有Owner明确确认的页面才能进入拼装准备库。
