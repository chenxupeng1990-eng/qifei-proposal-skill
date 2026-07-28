# 阶段包 08｜最终讲稿、QA与拼装

## 当前目标

基于最终批准页面生成逐页讲稿，完成全案QA并一次性拼装交付。

## 必须读取

- [../references/content-and-speaker.md](../references/content-and-speaker.md)
- 导出或拼装时再读取 [../references/workflow.md](../references/workflow.md) 的页面确认与交付部分。

## 讲稿门禁

- 全部正式页面已确认。
- 最终页序、页数、标题和批准PNG已锁定。
- 一次性按最终顺序生成全案讲稿并写入飞书。
- 每页讲稿对应最终页码、slide_id、标题和画面。
- 页面换序、拆合或核心内容变化使对应讲稿和相邻转场失效。

## QA

- 内容忠实度。
- 视觉质量与跨页一致性。
- 页序和讲稿映射。
- 批准PNG、内容哈希、设计版本和确认记录一致。

## 导出

只有Owner明确确认“全部内容确认，开始拼装”后，才一次性输出PNG、PDF和图片型PPTX；增强型可编辑PPTX需额外坐标与渲染QA。

- 基础交付：PNG、PDF、图片型PPTX。
- 增强交付：基础交付加原生文字层的半可编辑PPTX。
- 不承诺：图表、复杂SVG、场景主视觉和Image2图像全部转为PowerPoint原生可编辑对象。
