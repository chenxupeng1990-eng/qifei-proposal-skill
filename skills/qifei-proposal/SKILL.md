---
name: qifei-proposal
description: Govern and produce company-specific competitive proposals for Douyin brand operations, live commerce, short video, paid media, influencer marketing, integrated campaigns, retail AI systems, tenders, and pitches. Use when Codex must grill stakeholders after background intake, confirm a proposal brief, turn tender/client materials plus company knowledge into a fully confirmed strategy, extract official brand visual references into DESIGN.md, produce chapter-by-chapter and page-by-page PPT manuscripts, Feishu speaker notes, Image2 assets, route-aware HTML or direct-PNG review pages, PNG/PDF/image-based PPT preview, or audit an existing proposal against requirements, evidence, brand, strategy, and delivery gates.
---

# 公司提案总控

把提案视为受控的说服、内容、证据与视觉生产流程。先确认信息与策略立场，再生成成品；任何视觉质量都不能替代内容确认，任何“绝对正确、绝对中立”的表达也不能替代提案应有的观点和决策推动。

## 启动规则

1. 先运行 `scripts/check_suite_dependencies.py`。缺少 `grill-me-lite` 时立即停止，并原样输出脚本给出的完整套件安装命令；不得静默模拟 Grill Me。
2. 再完整读取顶层 [agent.md](agent.md)，以其使命、权责、上下文治理和质量定义约束整个项目。
3. 读取项目根目录 `AGENTS.md`；若只有旧式 `agent.md`，将其作为项目输入，不静默改名。
4. 读取 `project-state.json`，只执行当前阶段允许的动作。
5. 读取客户资料、临时参考资料和标书。处理 PDF、文档、表格或飞书内容时，调用对应 Skill。
6. 读取公司 Base 时先看 [references/company-base.md](references/company-base.md)；需要数字、履历、案例成绩或来源页时再读 [references/company-facts.json](references/company-facts.json)。
7. 需要判断资料权威、版本、证据和保密边界时，读取 [references/knowledge-policy.md](references/knowledge-policy.md)。
8. 不把任何单一历史方案的视觉或客户策略当作通用模板。参考案例只用于提取可复用的分析、叙事或生产规则，不能进入默认公司事实库。
9. 背景资料提交后，调用同套件的 `grill-me-lite` Skill 逐题确认项目决策；视觉阶段开始前，确认 `inputs/brand-official/` 已上传客户品牌官方视觉参考。

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
2. **Grill Me 与提案策划书**：背景资料提交后立即调用 `grill-me-lite`，只追问会改变方向、范围、承诺或交付的关键决定；一次只问一个问题并提供推荐答案。达成共同理解后生成 `content/proposal-brief.md`，由 Owner 确认。若会话已安装并提供 `Visualize:visualize`，可生成决策树、范围地图或策划书确认视图；可视化只辅助确认，不替代书面策划书。
3. **策略立场、连续性与动态目录**：仅在 Grill Me 和提案策划书确认后，先按 [references/proposal-persuasion-gate.md](references/proposal-persuasion-gate.md) 明确机会、矛盾、观点、主动选择、客户目标决策和全案情绪曲线；再按 [references/strategy-continuity-contract.md](references/strategy-continuity-contract.md) 建立总策略因果句、章节策略接口和只读标题链，最后形成动态目录。按 [references/writing-style-and-humanization.md](references/writing-style-and-humanization.md) 清理公式化和空泛表达后，让用户确认。立场、章节接口或标题链未通过时不得用中立目录占位。
4. **生成项目 `AGENTS.md`**：目录确认后立即生成，记录项目事实、策划书、策略、角色、页级规则和门禁。
5. **整章批量生成 PPT 提案成稿、飞书逐页确认**：先为当前章节生成页面论证链和只读标题链，确认其继承上一章输出并产生下一章所需输入；骨架确认后，必须先读取 [references/feishu-proposal-draft-format.md](references/feishu-proposal-draft-format.md)，再一次性生成本章全部页面的核心内容、逻辑展开、上屏内容、讲解方向、策略过桥、视觉生成建议和证据，不得再逐页串行调用生成，也不得提前撰写完整演讲稿。整章初稿必须写入同一份飞书提案文档，以稳定 `slide_id` 作为评论锚点；本地 Markdown 只是同步备份，不能替代飞书母版。每次写入后必须重新读取飞书正文，保存 `content/feishu/proposal-draft.md` 回读快照，并在 `project-state.json.proposal_draft` 记录文档 URL、document_id、revision_id、快照哈希和完整 `slide_id` 顺序。未回读、格式不完整或只存在本地 Markdown 时，状态不得设为 `verified`。团队可在飞书修改页序、拆页、合页、正文和标题，Agent 按评论局部修改并再次回读。每页仍需记录认知变化、目标情绪、鲜明判断、可见证明和下一页张力。整章必须通过连续阅读、说服力门禁、标题链和飞书格式验收。
6. **一次性全稿成稿完整性审查与内容冻结**：所有章节逐页确认完成后，只启动一次新的审查 Agent，按 [references/full-draft-integrity-redteam.md](references/full-draft-integrity-redteam.md) 检查全案策略逻辑、标题与表达、章节接口、情绪流、拆页密度和视觉载体可生成性，并按 [references/cross-page-semantic-qa.md](references/cross-page-semantic-qa.md) 复核页间推导与语义增量。用户确认的事实、策略与场外决策是只读权威；审查不得重新审判内容、外搜资料或引入安全、合规、风险判断。修复必要的结构与表达问题后由 Proposal Owner 确认并冻结内容。
7. **品牌官方视觉审计**：要求用户上传品牌官方视觉参考至 `inputs/brand-official/`，登记来源 ID，并明确其身份是项目正式品牌资料，还是仅用于测试的视觉代理。提取品牌视觉符号、Logo 规则、字体、色卡、图形、材质、摄影和禁忌，写入 `evidence/brand-visual-audit.md` 并确认。审计必须区分“企业品牌识别层”与“产品/品类气质层”，并定义最低充分的品牌锚点与品牌介入强度；品牌校准不得把品牌色或某一种品牌特征机械放大，覆盖已确认的品类气质、内容任务和提案视觉命题。没有官方资料或身份范围未明确，不得进入视觉方向。
8. **视觉方向与初始样张**：依据冻结内容和品牌视觉审计提出 2-3 个客户定制方向。每个方向都必须实际调用 Image2 生成至少一张代表页视觉稿，并登记独立的视觉命题、`visual_family_id`、代表页、生成资产和提示词记录；纯文字方向说明、Moodboard、HTML/CSS 换色或未生成图像的版式草图均不算视觉方向样张。Owner 只能从真实样张中选定方向。
9. **设计语言校准集**：选定方向后生成独立 `deck/design-calibration.html`。按预计正式页数选择自适应校准档位：24页及以下为 `compact`（最低6张），25–60页为 `standard`（最低8张），60页以上为 `extended`（最低10张）。所有档位都必须覆盖首页、目录、至少一种章节页、正文密度压力测试和结尾；档位越高，章节变体和正文密度覆盖越完整。只有本案实际启用透明 PNG 时，才要求真实 Alpha 样本验证边缘、遮挡、锚点、缩放和 HTML 叠加。使用 Codex 浏览器逐页评论、修订并确认；覆盖本案主要设计风险后才批准 `design_calibration`。
10. **生成 `DESIGN.md`**：把官方品牌视觉审计和已确认校准集编译为可执行视觉规范；冻结设计语言、固定页面和正文页弹性合同，并记录来源 ID。设计与生成规则见 [references/design-and-generation.md](references/design-and-generation.md)。
11. **按页面合同选择生产路线**：把冻结内容编译为 `deck-spec.json` 和 `slide-contracts.json`。每页先锁定一个核心思想、一个主要表达对象、一个最佳载体和一个视觉锤，再记录 Image2/HTML 分工；不得为了填写合同增加装饰、卡片或无用字段。每张正式提案页必须使用至少一个已登记的 Image2 资产，HTML 不得独立承担整页审美；资产必须服务本页思想，并匹配当前 `design_version` 的同一 `visual_family_id`，不能用无关装饰图过门禁。精确文字、数据、来源与严密关系由 HTML 保护；图像原生且无需精确文字时，可由 Image2 直出 16:9 PNG。
12. **视觉生成 Loop、评论与确认**：按“提取核心思想 → 选择载体 → 生成 → 单页与整章 montage 检查 → 回到正确权威源修改 → 再生成”的循环推进。使用 Codex 浏览器原生评论功能定位问题；单页问题只重建该页，公共设计语言变化才使相关页面整体过期。评论解决不等于页面确认；只有 Proposal Owner 明确说“确认本页/确认这些页面”时，才把对应页面和版本信息写入 `deck/assembly-ready/manifest.json`。循环中不拼装 PPT/PDF。
13. **最终页序锁定与全案讲稿生成**：全部正式 PPT 页面完成内容、视觉、拆页与页序确认后，锁定最终页面清单。只以最终批准页面为输入，按最终顺序一次性生成全案演讲稿并写入飞书；讲稿必须与最终页码、`slide_id`、标题和画面内容逐页对应。规则见 [references/content-and-speaker.md](references/content-and-speaker.md)。
14. **全案 QA 与一次性拼装**：全部正式页面进入拼装准备库且全案讲稿确认后，以批准 PNG 为视觉基准，完成内容忠实度、视觉质量、页序、讲稿映射和版本 QA。只有 Proposal Owner 明确确认“全部内容确认，开始拼装”，才一次性导出。默认输出最终 PNG、PDF 和图片型 PPT 预览；若用户明确要求可编辑文字层，可在相同批准基准上运行“视觉背景＋HTML 实测文字框”编译桥，并额外完成字段、坐标和渲染对照 QA。

交付级别必须在导出前说清：

- **基础交付**：PNG、PDF、图片型 PPTX。
- **增强交付**：在基础交付上增加原生文字层的半可编辑 PPTX。
- **不承诺**：图表、复杂 SVG、场景主视觉及生成图像完全转为 PowerPoint 原生可编辑对象。

## 可选生产子 Skill

- 内容冻结、页面合同和 `DESIGN.md` 均已确认后，可调用同仓库的 `proposal-ppt-production` 执行页面载体选择、Image2/HTML 分工、评审 PNG 和最终组装。它只负责生产，不得改写证据、批准页面或绕过本 Skill 的门禁。其机械工具只允许校验、资产整理、测量、渲染、对比与打包；缺少结论、载体或文案时必须报错，不得自动填空或套用可用版式。
- HTML 评论与精细校准阶段，可调用 `ppt-html-calibration-editor`。它输出的 JSON 只是校准记录，必须回写 HTML/CSS 并重新渲染；浏览器保存、评论关闭或编辑器状态都不等于页面确认。
- 两个子 Skill 均为可选实现层。不可用时继续使用本 Skill 自带脚本，内容权威、批准状态和一次性拼装规则保持不变。

## 不可跨越的门禁

- Grill Me 未完成或提案策划书未确认：不得进入策略与目录。
- 策略立场未明确、客户目标决策未定义或全案情绪曲线未建立：不得生成正式目录和PPT提案成稿。
- 总策略未编译为章节策略接口、章节可以任意换序或只读标题链无法复述策略推导：不得确认目录或进入PPT提案成稿。
- 目录未确认：不得生成项目 `AGENTS.md` 之后的内容。
- PPT提案成稿未完成、飞书逐页内容未确认，或 `proposal_draft` 缺少真实回读的URL、revision、快照哈希和完整 `slide_id`：不得进入全稿审查、内容冻结或视觉生产。
- 一次性全稿成稿完整性审查未通过：不得内容冻结。
- 内容未冻结：不得调用 Image2 生产正式素材。
- 未上传并核准品牌官方视觉参考，或未完成品牌视觉审计：不得提出正式视觉方向或生成样张。
- 视觉方向没有 2-3 套真实 Image2 样张，任一方向缺少视觉命题、`visual_family_id`、代表页、资产或提示词记录，或只提供文字说明/HTML换色：不得批准 `visual_direction` 或进入 `visual_sample`。
- 初始样张未确认：不得生成设计语言校准集。
- `deck/design-calibration.html` 未达到与正式页数匹配的 `compact`、`standard` 或 `extended` 校准档位，未覆盖该档位要求的首页、目录、章节变体、正文密度压力页和结尾，或未逐页确认：不得生成或批准 `DESIGN.md`。
- `DESIGN.md` 未记录品牌视觉来源 ID、企业品牌层与产品/品类层的色彩职责、最低品牌锚点和品牌介入强度：不得批准设计系统。
- `DESIGN.md` 未定义固定设计语言、内容页弹性合同和章节批量生成规则，或未确认：不得按章节渲染。
- 评论已解决或 Agent 自检通过：不得据此自动确认页面；缺少 Proposal Owner 的明确页面确认命令，不得写入拼装准备库。
- 全部正式PPT页面尚未确认、最终页序未锁定：不得生成完整演讲稿。
- 最终PPT页面发生换序、拆分、合并、标题或核心内容修改：受影响页及其转场讲稿立即过期，必须按最新页序重建。
- 任一正式页面未进入拼装准备库，或内容冻结 ID、设计版本、批准 PNG 与确认记录不一致：不得拼装 PPT/PDF。
- 未收到 Proposal Owner 的“全部内容确认，开始拼装”或同等明确命令：不得执行最终导出。
- 内容 QA 或视觉 QA 未通过：不得导出最终文件。
- 缺失信息只阻塞受影响页面；若缺口改变策略、报价、承诺或核心结论，则阻塞对应阶段。

## 角色与责任

- **Proposal Owner**：唯一的门禁批准者、内容冻结者和页面重开批准者。
- **客户/项目负责人**：客户沟通、资料确认、范围与承诺管理。
- **策划**：策略、目录、章节论证链、整章批量成稿、逐页内容与演讲任务。
- **数据分析师**：数据口径、证据账本、指标与经营模型。
- **运营专家**：直播、短视频、投放、货盘、达人和执行真实性。
- **设计/视觉 Agent**：样张、`DESIGN.md`、Image2 资产、HTML 视觉实现。
- **对抗检测子 Agent**：独立找错，不重写方案；每轮使用新的上下文和原始资料。

## 公司介绍与案例

- 公司介绍和选中的公司案例统一放在提案前部，沿用公司现有介绍逻辑，不穿插在正式客户策略正文中。
- 根据客户任务动态选择最相关案例；每个案例只证明一个与本项目有关的能力。
- 不把客户定制策略原型包装成公司既有案例。
- GMV、投放金额、服务品牌数、奖项、资质、人员履历和案例成绩只能使用当前使用方已经写入公司 Base 的核准表述；默认空模板不得被当作事实来源，对外不展示内部版本规则。
- 不生成 Logo 墙代替案例，不编造缺失成绩。

## PPT内容与最终讲稿

- 一页只承担一个可复述结论和一个演讲任务。
- 内容必须完成“事实/问题 -> 判断 -> 策略或动作 -> 结果/验证”的逻辑。
- 每页必须说明它回答前页的什么问题、创造了什么新理解、为什么需要下一页；全案语义规范见 [references/cross-page-semantic-qa.md](references/cross-page-semantic-qa.md)。
- 每章必须声明 `strategy_input`、`chapter_claim`、`reasoning_step`、`strategy_output` 和 `next_chapter_necessity`；上一章输出必须等于下一章输入。章节独立成立但不推进总策略，同样不得确认。
- 每页使用稳定 `slide_id`；HTML、章节稿、证据账本和飞书演讲稿都用它关联。
- 前期飞书主文档保存PPT提案成稿与页面协作信息，不保存完整演讲稿。完整讲稿在全部PPT页面和最终页序确认后另行生成，可写入同一文档的“最终演讲稿”区域或独立飞书讲稿文档。
- 飞书不可用时，提案成稿先写入结构化 Markdown，并将 `proposal_draft.status` 设为 `local_fallback_pending_sync`、记录 `fallback_reason`；该状态只允许继续本地起草，不能确认章节、进入全稿审查或内容冻结。飞书恢复后必须按稳定 `slide_id` 同步、回读并通过格式校验。最终讲稿的本地回退规则保持在 `content/speaker-notes.md`。
- 对外页面不出现 `待确认`、内部权威等级、版本状态、风险备注或 Agent 工作痕迹。
- 对外提案必须作出有证据的方向选择。正确但没有观点、观点有证据但不能推动客户决策、或删除品牌名后可原样放入任意行业报告的页面，不得确认。

## 生成与验证命令

从 Skill 根目录运行：

```bash
python3 scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner>
python3 scripts/validate_project.py <项目目录>
python3 scripts/freeze_deck_spec.py <项目目录> --approved-by <Owner> --approval-id <确认记录>
python3 scripts/validate_deck_spec.py <项目目录>
python3 scripts/render_deck.py <项目目录> --chapter-id <章节ID>
node scripts/capture_review_pngs.mjs <项目目录> --chapter-id <章节ID>
node scripts/capture_editable_layout.mjs <项目目录>
node scripts/compile_editable_pptx.mjs <项目目录>
node scripts/validate_editable_pptx.mjs <项目目录>
python3 scripts/manage_assembly_ready.py <项目目录> approve --review-manifest <评审清单> --slide-id <页面ID> --approved-by <Owner> --approval-id <确认记录>
python3 scripts/manage_assembly_ready.py <项目目录> approve --direct-png <deck/review/下的PNG> --slide-id <页面ID> --approved-by <Owner> --approval-id <确认记录>
python3 scripts/manage_assembly_ready.py <项目目录> reopen --slide-id <页面ID> --approved-by <Owner> --reason <重开原因>
python3 scripts/validate_assembly_ready.py <项目目录>
python3 scripts/manage_assembly_ready.py <项目目录> finalize --approved-by <Owner> --approval-id <全案确认记录>
python3 scripts/validate_assembly_ready.py <项目目录> --require-final
python3 scripts/render_deck.py <项目目录>
node scripts/export_deck.mjs <项目目录>
```

首次导出前在 Skill 根目录执行 `npm install`。导出需要本机 Chrome、Edge 或 Chromium。

Windows PowerShell 使用同一组命令时，将 `python3` 替换为 `py -3`；如果没有 Python Launcher，则使用 `python`。项目绝对路径必须使用引号包裹，例如 `"D:\\Projects\\品牌提案"`。`deck-spec.json`、状态文件和媒体清单内部仍统一保存项目内 POSIX 风格相对路径（例如 `assets/source/product.png`），不要写入盘符或反斜杠。首次运行先执行 `npm run check:env`。

## 生成层原则

- 独立实现，不依赖或复制外部模板填空系统、主题资产或专有导出引擎。
- 顶层 `agent.md` 是 Skill 级治理契约；项目 `AGENTS.md` 是项目内容与治理权威；`DESIGN.md` 是视觉权威；`deck-spec.json` 是冻结内容的编译产物；HTML 是视觉母版。
- 视觉 Skill 的核心职责只有三项：保持跨页视觉一致性、保持版式语法一致性、让每页核心思想匹配最佳表达形式。校验器只防客观错误，不能代替创意和审美判断。
- 每张正式页必须包含已登记的 Image2 资产，并由统一 `visual_family_id` 约束画面风格。Image2 是视觉底线，不是内容决策者：先完成内容判断与页面路由，再生成语义相关的场景、主视觉、机制、语义图标或透明模块。
- 使用页面合同限制文字、数组和媒体槽位；字符预算只做预检，最终必须在浏览器测量溢出和越界。
- 每页生成前必须写入页面生产路由：服务对象、使用情境、演讲任务、内容关系、最佳载体、唯一主导、视觉论点、Image2/HTML分工与视觉平衡。流程、场景、系统、机制和工作件页面若没有可见主载体，不得通过设计循环。
- 每页只能有一个视觉锤；独立数字、白底说明条、重复口号或装饰元素若不引入、解释或导向该视觉锤，必须删除、并入主载体或转成图形关系。
- 首页、目录页、章节页和结尾感谢页按确认样张收紧自由度；正文页只冻结品牌语言、网格、字体、色彩、组件、密度和边界，允许 Agent 在合同内选择最适合内容的版式。
- 优先按章节生成 HTML 和评审 PNG，避免等待全案一次性渲染；修改循环不重复生成 PPT/PDF。最终全案构建必须从拼装准备清单重新校验页序、内容哈希、设计版本和批准页面一致性。
- 可编辑 PPTX 编译桥只在全案确认后运行。它保留批准视觉为背景图层，将 HTML 中实测的精确文字框编译为 PowerPoint 原生文字层。文字、冻结 ID、批准哈希、讲稿锚点和坐标必须通过机器校验；再通过完整渲染检查换行、字体替代、遮挡和视觉偏差。当前不将图表、复杂 SVG 或模板继承自动转为原生可编辑对象。
- Image2 负责背景、主视觉、场景、概念图、无文字语义图标，以及 HTML 难以完成的透明 PNG 高表现力模块；正文、精确数据、严密逻辑关系、不可核验标签、图表和注释由 HTML 统一排版。语义图标必须表达内容、商品、人群、场景或增长信号等明确节点，服务阅读路径，不能只是装饰或替代精确关系。透明模块只能进入 `DESIGN.md` 和页面合同声明的图层槽位。
- 正式资产只允许项目内相对路径。禁止远程 URL、绝对本机路径、`file://` 和 `data:` 进入最终 `deck-spec.json`。
- Image2 不可用时输出提示词包，不擅自切换模型。

## 保密与外部调用

- 客户原始资料保留本地。
- 发给搜索、Image2 或其他外部服务的提示词必须去标识化，只保留完成任务必要的信息。
- 不上传标书全文、报价、联系人、账号、内部批注或未公开经营数据。
- 透明 PNG 公司素材库只接受去标识化且经人工批准的资产；项目资产默认隔离。

## 完成标准

只有同时满足以下条件才宣布完成：

- 所有章节和页面有确认记录；评论关闭不得替代 Proposal Owner 的明确页面确认。
- 一次性全稿成稿完整性审查通过。
- 内容冻结与视觉样张确认可追溯。
- 设计语言校准集包含全部规定页面类型，且逐页确认记录可追溯。
- `AGENTS.md`、`DESIGN.md`、`deck-spec.json` 与 HTML 无漂移。
- Grill Me 完成记录、提案策划书、品牌官方视觉来源和品牌视觉审计均可追溯。
- 内容 QA 和视觉 QA 均通过。
- 全部正式页面进入同一内容冻结 ID 与设计版本的拼装准备库，并有全案拼装批准记录。
- HTML、批准 PNG、PDF、图片型 PPT 预览和飞书演讲稿的最终页码、页序与 `slide_id` 一致；PPT/PDF 只在全案确认后拼装。
- 最终文件不含策略推理、风险、Agent 过程等内部备注，不含本机路径、未确认占位符或客户敏感信息泄漏。可编辑交付允许仅在备注中保留 `slide_id`、内容冻结 ID、批准哈希和讲稿锚点等回查元数据。
