# 阶段包 05｜品牌视觉审计与方向样张

## 当前目标

从品牌官方资料和冻结内容中提出2–3套真实、可比较的客户定制视觉方向。

## 必须读取

- [../references/visual-direction.md](../references/visual-direction.md)
- Image2不可用时读取 [../references/environment-degradation.md](../references/environment-degradation.md)。

## 必须产出

- `evidence/brand-visual-audit.md`。
- 2–3套实际调用Image2生成的代表页视觉稿。
- 每套方向的视觉命题、`visual_family_id`、代表页、资产路径和提示词记录。
- `selected_direction_id` 与批准记录。

## 核心门禁

- 品牌身份范围必须是 `official_brand` 或明确的 `visual_proxy`。
- 方向差异必须是视觉命题差异，不是换色。
- 纯方向说明、Moodboard、HTML/CSS版式草图和提示词包不能通过。

## 禁止动作

- 不生成完整校准集。
- 不生成 `DESIGN.md`。
- 不批量生成正式页面。
