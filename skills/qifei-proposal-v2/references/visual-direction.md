# 品牌视觉审计与方向样张

## 输入

- 冻结的提案内容；
- `inputs/brand-official/` 中的品牌官方视觉资料；
- `project-state.json.brand_visual` 登记的来源和品牌身份范围。

## 品牌审计

在 `evidence/brand-visual-audit.md` 中区分：

- `official_explicit`：品牌资料明确规定；
- `sampled_from_official`：从官方画面采样得到；
- `proposal_choice`：本案设计选择。

至少提取Logo与安全区、色彩职责、字体特征、图形符号、材质、摄影语言、版式节奏和视觉禁忌。不得把采样或提案选择写成官方规范。

## 方向样张

提出2–3个视觉命题不同的方向。每个方向必须：

1. 实际调用Image2生成至少一张代表页；
2. 使用真实冻结内容，不用无意义占位文案比较风格；
3. 登记 `direction_id`、`visual_thesis`、`visual_family_id`、代表页、资产路径和提示词记录；
4. 说明如何承接品牌、产品和全案策略；
5. 说明该方向在正文、数据、案例和场景页中的延展方式。

Moodboard、方向说明、HTML/CSS换色或只有提示词的方案不能批准视觉方向。Image2不可用时遵循 `environment-degradation.md`，阶段保持未通过。

## 放行

Owner必须从真实方向样张中选定一个 `selected_direction_id`。本阶段不生成完整校准集、不生成 `DESIGN.md`、不批量生产正式页面。
