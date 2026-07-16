# 设计系统与合同式生成

## DESIGN.md

样张确认后生成 `DESIGN.md`，至少定义：

- 客户品牌与本案视觉命题。
- 画布固定为 1920x1080，16:9。
- 色彩、字体、字号层级、行距和安全区。
- 背景、光影、材质、图形语言和摄影/生成图风格。
- 标题页、章节页、观点页、数据页、框架页、案例页、工作件页、视觉 Demo 页和结尾页的构图规则。
- 图表、表格、数字、来源和页码规范。
- Image2 使用范围、禁用范围和透明 PNG 资产规范。
- 页面密度等级与拆页规则。
- 明确的视觉禁忌和样张版本。

`DESIGN.md` 是视觉权威；`deck/design-tokens.json` 是其机器可读编译产物，不可反向覆盖 `DESIGN.md`。

## deck-spec.json

内容冻结后生成。顶层至少包含：

- `deck_id`、`project_name`
- `content_freeze_id`
- `design_version`
- `source_hashes`
- `slides`

每页至少包含：

- `slide_id`、`chapter`、`role`、`layout`
- `title`、`subtitle`、`kicker`
- `blocks`
- `visual`
- `evidence_ids`
- `speaker_doc_anchor`
- `status: content_frozen`
- `approved_content_hash`

## 页面合同

`slide-contracts.json` 为每种 `layout` 定义：

- 标题、副标题和正文最大视觉字符宽度。
- 列表、卡片、数字和流程步骤最大数量。
- 媒体槽位数量、比例和适配方式。
- 必填字段与允许为空字段。
- 最小字号和建议密度。

字符预算按全角 1、半角 0.5 做预检；最终用浏览器测量 `scrollWidth/clientWidth`、`scrollHeight/clientHeight`、页面边界和元素相交。

## Image2

只用于：

- 背景与主视觉。
- 客户定制场景图。
- 概念图、科技可视化和高表现力视觉模块。
- 经批准的透明 PNG 核心元素。

不用 Image2 生成正文、数据表、图表标签或大段文字。提示词必须去标识化；模型不可用时输出提示词包。

项目生成资产放入 `assets/image2/`，经人工批准后移动到 `assets/approved/`。只有去标识化并获批的资产可提升到公司通用素材库。

## HTML 母版

- 所有正文、数据、图表和图注由 HTML 排版。
- 每页使用 `.slide[data-slide-id]`，尺寸固定 1920x1080。
- HTML 侧栏只写批注，不直接修改冻结内容。
- 修订发生在章节源稿、`deck-spec.json` 或 `DESIGN.md`，之后重建 HTML。
- `build-manifest.json` 记录内容、设计和资产哈希；任一上游变化都使旧导出过期。

## 本地批注

`serve_review.mjs` 只绑定 `127.0.0.1`。批注文件 `reviews/review-comments.json` 保存：

- comment ID
- `slide_id`
- 作者
- 批注正文
- 状态
- 创建和解决时间

写入前验证 JSON，并通过临时文件加 rename 原子替换。

## 双轴 QA

### 内容 QA

- HTML 与冻结内容逐字段一致。
- 标题、数字、证据、讲稿锚点和页序一致。
- 没有新增结论、承诺或未确认文案。
- 没有公司介绍侵入客户策略。
- 没有内部备注、绝对路径、占位符或敏感信息。

### 视觉 QA

- 无溢出、裁切、重叠、黑块、缺图和字体替换。
- 视觉层级、对齐、安全区、字号和来源可读。
- Image2 资产与 HTML 文字风格一致。
- 相邻页面节奏有变化但属于同一设计系统。
- 逐页 PNG 与 HTML 完全一致。

## 导出

只从通过 QA 的 HTML 导出：

- `deck/proposal.html`
- `exports/png/<slide_id>.png`
- `exports/proposal.pdf`
- `exports/proposal-preview.pptx`

PPT 每页只放一张 16:9 全页 PNG，是预览件而非可编辑母版。修订不得发生在 PPT 中。
