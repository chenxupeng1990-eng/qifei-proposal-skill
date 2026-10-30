# 阶段包 03｜整章或整模块成稿与内容确认

## 当前目标

按已确认骨架一次性生成整章或整模块内容，并在已声明的权威源完成确认。

## 必须读取

- [../references/feishu-proposal-draft-format.md](../references/feishu-proposal-draft-format.md)
- [../references/proposal-persuasion-gate.md](../references/proposal-persuasion-gate.md)：成稿时逐页按说服力合同写，内部审慎语言不上屏。视觉表现型任务（`visual_showcase`）不套说服力合同，章节也不写“本章回答 / 逻辑路径 / 情绪方向”；上屏文字要短，因为它会和设计要求一起交给生图模型画出来。
- [../references/cross-page-semantic-qa.md](../references/cross-page-semantic-qa.md)
- [../references/writing-style-and-humanization.md](../references/writing-style-and-humanization.md)
- 选用飞书但飞书不可用或授权失败时读取 [../references/environment-degradation.md](../references/environment-degradation.md)。
- 已在策略阶段启用数据分析时，读取 [../references/data-to-strategy-evidence-engine.md](../references/data-to-strategy-evidence-engine.md)。

## 必须产出

- 章节论证链与只读标题链。
- 整章全部页面的核心内容、逻辑展开、上屏内容、讲解方向、策略过桥、视觉建议和来源。
- 同一份提案母稿，写在项目登记的权威源里：
  - 工作台（`studio`，完整提案默认）：`content/draft/proposal-draft.md`，附修订日志和章节确认记录。
  - 飞书（`feishu`，可选）：飞书文档，加上 `content/feishu/proposal-draft.md` 整份回读快照。
- 回读凭证：revision、SHA256 与完整 slide 顺序。飞书还要记录 URL 和 document_id。

## 执行纪律

- 整章生成，逐页确认；不得逐页串行生成正文。
- `full_deck` 默认以工作台为唯一确认母版，飞书只在项目启动时明确选择后使用；`inherited_module` 沿用父项目；`standalone_module` 可在启动时选择工作台、飞书或本地 Markdown。
- 工作台流程：
  1. `python3 scripts/draft_studio.py serve <项目目录>` 启动工作台。
  2. Owner 在页面上阅读、评论、改稿；Agent 直接修改母稿文件，并用 `comments`、`reply` 回应评论。
  3. 每章由 Owner 在工作台上点"确认"。确认会记录这一章每一页的内容指纹；之后再改，这一章会自动退回待确认。
  4. 确认后，工作台会自动登记当前版本；有修改时，用页面上的按钮或 `python3 scripts/draft_studio.py register <项目目录>` 重新登记。
- 飞书流程：修改评论后重新抓取整份飞书，并再次校验。
- 给 Owner 阅读整章或整份母稿时，用 `python3 scripts/draft_studio.py render <项目目录>` 生成富格式阅读页（`deck/review/draft-studio.html`），需要 Markdown 时用 `export-md --profile full|brief`；Owner 想直接在页面上改稿时，用 `serve` 启动本地工作台，保存即写盘并记录版本。阅读页和导出的 Markdown 都是派生物，不改变权威源，见 [../references/draft-studio.md](../references/draft-studio.md)。
- 临时插页、拆页和合页先进入变更候选清单；写入权威源，并完成登记（工作台）或整份回读（飞书）之前，不修改正式页序。
- 只写讲解方向，不生成完整演讲稿。
- `PPT上屏内容` 只放观点、证据和来源，不放内部审慎说明（"不等于""不代表""尚未""仅参考""另行商定""以…为准""非…"这类）。边界写进措辞本身：写"Instagram 搜索热度"，不写"搜索热度，不等于销量"；审慎说明放进讲解方向或证据与来源。`check` 会拦截这些用语；确属客户要求的上屏声明，由 Owner 在评论里确认后改写成正面表述。
- 不能使用公司真实数据或案例时，用能力证明代替：拆一个品牌自己的公开内容或竞品案例，展示我们的判断方法、执行工作件和预期产出，不写"示意""非已合作"之类的退缩说明。
- 数据页必须用判断型标题，并完整表达数据事实、比较关系、品牌含义、策略选择和后续接口；不能写成中立行业报告或数据罗列。

## 放行

所有章节已由 Owner 确认，回读凭证完整（工作台：登记的版本就是最新版本，且每章确认后没有再改；飞书：回读快照与 revision 一致），`python3 scripts/draft_studio.py check <项目目录>` 为 PASS，标题链通过。旧写法的母稿先用 `normalize` 转换。
