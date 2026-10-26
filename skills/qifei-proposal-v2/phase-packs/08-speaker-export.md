# 阶段包 08｜最终讲稿、QA与拼装

## 当前目标

基于最终批准页面生成逐页讲稿，完成全案QA并一次性拼装交付。

## 必须读取

- [../references/content-and-speaker.md](../references/content-and-speaker.md)
- 导出时读取 [../references/html-editor-and-editable-pptx.md](../references/html-editor-and-editable-pptx.md)。
- 导出或拼装时再读取 [../references/workflow.md](../references/workflow.md) 的页面确认与交付部分。

## 讲稿门禁

- 全部正式页面已确认。
- 最终页序、页数、标题和批准PNG已锁定。
- 一次性按最终顺序生成全案讲稿并写入飞书。
- 每页讲稿对应最终页码、slide_id、标题和画面。
- 页面换序、拆合或核心内容变化使对应讲稿和相邻转场失效。
- 模块任务仅在 `deliverable_level=export` 且Owner明确要求时生成模块讲稿；否则不为满足流程而生成。

## 最终核对（只查低级错误）

内容质量由全稿审查和 Owner 逐页确认负责，视觉质量由逐页生产检查、独立视觉审查和 Owner 页面确认负责，这里不再重做全面的内容 QA 和视觉 QA。讲稿之后只做一次低级错误核对：

1. 运行 `node scripts/check_page_layout.mjs <项目目录> <最终页面HTML>`：孤字尾行、文字越界或被裁切、文字压在纹理上、左缘差几像素没对齐。
2. 通读全部页面查错别字，然后运行 `python3 scripts/final_check.py <项目目录> --proofread "<通读结果>"`：页数与页序、拼装准备库与讲稿页序一致、每页上屏文字与冻结母稿逐行一致（缺字、多字都报错）、版面测量结果。
3. 导出后运行 `python3 scripts/final_check.py <项目目录> --pptx exports/<可编辑PPTX>`，确认 PPTX 原生文字与母稿逐行一致。

核对不通过就回到对应页面修改；`final_check` 不是 Owner 批准，最终拼装仍需 Owner 明确批准。

## 导出

只有Owner明确确认“全部内容确认，开始拼装”后，才一次性输出PNG、PDF和图片型PPTX；增强型可编辑PPTX需额外坐标与渲染QA。

- 基础交付：PNG、PDF、图片型PPTX。
- 增强交付：基础交付加原生文字层的半可编辑PPTX。
- 不承诺：图表、复杂SVG、场景主视觉和Image2图像全部转为PowerPoint原生可编辑对象。

增强交付必须依次完成布局捕获、PPTX编译和PPTX验证；验证报告为 `PASS` 后才可交付。PPTX只作为交付副本，正式改版仍回到HTML生产源。
