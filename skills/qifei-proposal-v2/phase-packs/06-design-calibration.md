# 阶段包 06｜设计语言校准与DESIGN.md

## 当前目标

用最少样张覆盖本案主要设计风险，并把确认结果编译为可执行设计合同。

完整提案使用自适应校准档位；继承模块不重做校准；独立模块只校准实际出现的页面类型，不强制套用完整提案最低样张数。

## 必须读取

- [../references/design-and-generation.md](../references/design-and-generation.md)：跨阶段视觉不变量。
- [../references/design-calibration-contract.md](../references/design-calibration-contract.md)
- [../references/design-system-contract.md](../references/design-system-contract.md)
- 所需视觉能力不可用时读取 [../references/environment-degradation.md](../references/environment-degradation.md)。

## 自适应档位

`compact`、`standard`、`extended` 的页数边界、最低样张数与风险覆盖要求，以 `design-calibration-contract.md` 为唯一权威定义。本阶段包不重复数字。

## 必须产出

- `deck/design-calibration.html`。
- 浏览器逐页评论与修订结果。
- `DESIGN.md`。
- `deck/design-tokens.json`。

## 固定与弹性

- 固定品牌锚点、字体、颜色职责、材质、网格、安全区、组件语法和密度边界。
- 正文页允许按内容改变列数、媒体比例、模块组合和留白。
- 不用重复同一版式伪造一致性。
- 每张校准页都是“整页设计底图＋HTML 文字层”。评审时把文字层关掉看一次：底图本身必须是完整的设计画面，并且能看出这一页在讲什么。
- 校准页同样先按本页内容选最佳载体（数据、流程、故事板、产品分工、空间体验等），不同类型的校准页不能只是同一机位的氛围图换文字。
- 确认后的校准页就是对应页面类型的**母版**；`DESIGN.md` 写明每类页面用哪张母版，正式生产时按母版生图。
- `DESIGN.md` 只规定底图的构图、留白和文字区规则，不能给任何页面类型开“纯 HTML”或“配图框”例外。

## 放行

当前档位全部设计风险已覆盖，Owner逐类确认，批准记录匹配。
