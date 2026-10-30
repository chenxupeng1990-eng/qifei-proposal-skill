# 视觉设计与生成导航

本文件只保留跨阶段不变量。具体规则按当前阶段读取：

- 品牌审计与方向样张：[visual-direction.md](visual-direction.md)
- 设计语言校准：[design-calibration-contract.md](design-calibration-contract.md)
- `DESIGN.md` 与令牌：[design-system-contract.md](design-system-contract.md)
- 页面路由、Image2、HTML与评审Loop：[page-production-loop.md](page-production-loop.md)

## 跨阶段不变量

1. 先确认页面核心思想和最佳载体，再决定 Image2 与 HTML 分工。
2. 正式页面默认走“整页 Image2 设计底图＋HTML 文字层”：
   - 每页先按版式生成一张覆盖 1920×1080 的设计底图，构图时就给标题、正文和数据预留位置；产品、光线、空间和材质都在底图里完成。
   - HTML 只叠加准确的文字、数字、图表、标签和关系，不再自己画版面。
   - 把图片放进方框、卡片或缩略图里当配图，不算达到视觉底线。
   - 透明PNG只能作为底图之上的补充。
   - 底图的主体是本页的最佳载体，不是通用氛围图；正式页底图以同类页面的已确认母版为参考图生成。
   - 要走其他路线，必须有 Owner 针对具体页面的批准记录；`DESIGN.md` 不能替页面类型开例外。
   - 例外：`task_nature: visual_showcase`（品牌手册等）默认走 `render_route: image_full`，整页连文字一起生图，见 [task-modes-and-runtime.md](task-modes-and-runtime.md) 1.1 节和 [page-production-loop.md](page-production-loop.md) 的“整页生图页面”。
   Image2 不是内容判断者，HTML 保护准确文字、数据和严密关系。
3. 品牌官方资料、冻结内容、`design_version` 和批准状态是只读输入。
4. TDD与校验器只检查尺寸、缺图、越界、Alpha、字体、路径、哈希和版本一致性，不替代审美判断。
5. 同一全案使用一个视觉家族；一致性由色彩职责、字体、材质、光向、镜头、产品融合、图形母题和版式语法共同建立。
6. 评论、QA与Owner批准是不同状态；页面批准规则不得被生成成功或评论关闭替代。
7. 产品与 Logo（视觉基线、`DESIGN.md` 和提示词都按这句写，不要只写“保留原貌”）：
   > 官方产品图作为参考图进入生图，与场景同光、同透视、有接触阴影；不改包装结构、文字和 Logo；Logo 用官方文件，放在 HTML 文字层或后期贴回。
   - 产品要“长在”画面里，不是浮在场景上的贴图。只把产品图留到后期合成，会丢掉光影和透视，视觉效果明显变差。
   - 生成后对照官方产品图检查包装结构、颜色和文字；包装被改动的，重生成或局部修正，不是改成后期贴图。
   - 校验器会拦“产品图只能后期贴回”“生成图只承担场景”这类写法，以及提到产品图却没写“作为参考图”的规则。

## 通用视觉Loop

> 核心思想 → 最佳载体 → 视觉锤 → Image2资产 → HTML精确层 → 1920×1080检查 → 整章montage → 评论修改 → Owner确认

任何阶段不得跳过当前阶段包指定的细分合同。
