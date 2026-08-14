# HTML校稿与可编辑PPTX交付合同

本文件是V2中浏览器校稿、源文件回写和半可编辑PPTX导出的唯一权威合同。它把已经存在的HTML编辑器与PPTX编译器接入正式生产链，不新增第二套页面真相。

## 生产链

> Image2资产 → HTML组版 → 浏览器校稿 → 回写HTML/CSS → 固定画布QA → 页面确认 → 捕获可编辑布局 → 编译PPTX → 验证PPTX

HTML始终是视觉生产源。浏览器暂存、校稿JSON、评审PNG和PPTX都是派生产物，不能反向覆盖飞书内容权威或已批准页面。

## 浏览器校稿

正式章节HTML应接入 `$ppt-html-calibration-editor`，只开放需要人工校准的文字和图片：

- 单页编辑：`?edit=1&capture=<slide-id>`；
- 全案文字校稿：`?edit=all`；
- 干净截图：`?capture=<slide-id>`，不得出现编辑器DOM；
- 编辑状态导出为JSON后，由Agent回写HTML/CSS和正式图片文件，再重新渲染。

浏览器本地保存只用于修改循环，不是生产源，也不等于页面确认。页面进入拼装准备库前，必须以回写后的HTML重新通过1920×1080检查。

## 两种PPTX交付

### 图片型预览PPTX

每页使用批准PNG，视觉最稳定，适合预览、归档和不需要现场改字的交付。

### 增强型可编辑PPTX

增强型输出采用“视觉底图＋原生文字层”：

- Image2主视觉、复杂CSS、装饰、图表和场景合并在视觉底图；
- 标题、正文、指标、卡片文字、页脚来源等支持范围内的内容重建为PowerPoint原生文字层；
- 不承诺复杂图表、SVG、Image2场景和所有装饰对象原生可编辑；
- PPTX是交付副本，后续正式改版仍回到HTML生产源。

## 必跑命令

在 `skills/qifei-proposal-v2/` 目录运行：

```bash
npm run editable:capture -- <项目目录>
npm run editable:compile -- <项目目录>
npm run editable:validate -- <项目目录>
```

默认产物：

- `deck/editable-layout/editable-layout-manifest.json`
- `deck/editable-layout/backgrounds/*.png`
- `exports/proposal-editable.pptx`
- `exports/proposal-editable.report.json`
- `exports/proposal-editable.validation.json`

只有 `proposal-editable.validation.json` 为 `PASS` 时，增强型PPTX才能交付。源HTML、`deck-spec.json`、内容冻结ID、设计版本或背景哈希发生变化后，必须重新捕获、编译和验证。

## 当前原生文字范围

布局捕获器默认识别：页眉标签、主副标题、正文、项目符号、卡片、指标、步骤、引语和页脚来源。新增HTML组件如需在PPTX中可编辑，必须先扩展捕获选择器并补测试；未进入选择器的视觉内容保留在底图中。

## 交付QA

- 页数、顺序、`slide_id`、内容冻结ID和设计版本一致；
- 原生文字无缺失或篡改；
- 原生文字框与HTML测量坐标最大偏差不超过校验器阈值；
- PPTX备注包含页面锚点和冻结信息；
- 包内不泄露本地绝对路径；
- 在PowerPoint或WPS中抽查首页、章节页、密集内容页和结尾页的字体替代、换行与视觉对齐。
