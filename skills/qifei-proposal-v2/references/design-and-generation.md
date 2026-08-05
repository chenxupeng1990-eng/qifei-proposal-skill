# 视觉设计与生成导航

本文件只保留跨阶段不变量。具体规则按当前阶段读取：

- 品牌审计与方向样张：[visual-direction.md](visual-direction.md)
- 设计语言校准：[design-calibration-contract.md](design-calibration-contract.md)
- `DESIGN.md` 与令牌：[design-system-contract.md](design-system-contract.md)
- 页面路由、Image2、HTML与评审Loop：[page-production-loop.md](page-production-loop.md)

## 跨阶段不变量

1. 先确认页面核心思想和最佳载体，再决定 Image2 与 HTML 分工。
2. Image2 是正式页面的视觉底线，不是内容判断者；HTML保护准确文字、数据和严密关系。
3. 品牌官方资料、冻结内容、`design_version` 和批准状态是只读输入。
4. TDD与校验器只检查尺寸、缺图、越界、Alpha、字体、路径、哈希和版本一致性，不替代审美判断。
5. 同一全案使用一个视觉家族；一致性由色彩职责、字体、材质、光向、镜头、产品融合、图形母题和版式语法共同建立。
6. 评论、QA与Owner批准是不同状态；页面批准规则不得被生成成功或评论关闭替代。

## 通用视觉Loop

> 核心思想 → 最佳载体 → 视觉锤 → Image2资产 → HTML精确层 → 1920×1080检查 → 整章montage → 评论修改 → Owner确认

任何阶段不得跳过当前阶段包指定的细分合同。
