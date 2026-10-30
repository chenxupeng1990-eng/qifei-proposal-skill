# 阶段包 05｜品牌视觉审计与方向样张

## 当前目标

从品牌资料和冻结内容中提出真实可比较的视觉方向。完整提案生成2–3套；独立模块至少生成一套视觉基线；继承模块直接复用父项目设计版本。

## 必须读取

- [../references/design-and-generation.md](../references/design-and-generation.md)：跨阶段视觉不变量。
- [../references/visual-direction.md](../references/visual-direction.md)
- Image2不可用时读取 [../references/environment-degradation.md](../references/environment-degradation.md)。

## 必须产出

- `evidence/brand-visual-audit.md`。
- 与任务模式匹配的真实图像生成代表页视觉稿。
- 每套方向的视觉命题、`visual_family_id`、代表页、资产路径和提示词记录。
- `selected_direction_id` 与批准记录。

## 核心门禁

- 品牌身份范围必须是 `official_brand` 或明确的 `visual_proxy`。
- 方向差异必须是视觉命题差异，不是换色。
- 纯方向说明、Moodboard、HTML/CSS版式草图和提示词包不能通过。
- 代表页必须按“整页设计底图＋HTML 文字层”制作：底图覆盖整页并为文字留位，不能是浅色底上放几张配图。三套方向的差异要体现在底图的构图、光线和空间上。

- 视觉基线和品牌视觉审计里的产品规则，按 [design-and-generation.md](../references/design-and-generation.md) 第 7 条的标准写法：官方产品图作为参考图进入生图（包装和包装上的 Logo 保持原样）；页面上单独放的品牌 Logo 不让生图模型画，出图后用官方文件叠上去。方向样张里的产品同样按这个方式生成。

## 禁止动作

- 内容冻结前不生产正式视觉。
- 不生成完整校准集。
- 不生成 `DESIGN.md`。
- 不批量生成正式页面。
