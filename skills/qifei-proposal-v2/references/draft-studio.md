# 提案母稿工作台合同

母稿工作台把提案母稿渲染成适合阅读的富格式页面，并导出干净的 Markdown。当前版本（M1）只读：编辑、评论和实时同步在后续版本加入。

## 权威源不变

- 权威源仍是项目登记的母稿：`project-state.json.proposal_draft.verified_snapshot_path`。没有登记时，依次查找 `content/draft/proposal-draft.md` 和 `content/feishu/proposal-draft.md`。
- 阅读页和导出的 Markdown 都是派生物。不能把它们登记为确认凭证，也不能反向覆盖母稿。
- 页面状态读取自 `project-state.json`：章节 `manuscript_confirmed` 显示为"已确认"，在 `verified_slide_ids` 中的页面显示为"已回读"，其余显示为"待确认"。

## 命令

在 `skills/qifei-proposal-v2/` 目录下运行：

```bash
python3 scripts/draft_studio.py render <项目目录> [--draft <母稿路径>] [--out deck/review/draft-studio.html]
python3 scripts/draft_studio.py export-md <项目目录> [--profile full|brief] [--out <文件>]
node scripts/check_draft_studio.mjs <阅读页.html>
```

- `render`：生成单个 HTML 文件，可以离线打开。用 `--draft` 可以只渲染某一章的章节文件。
- `export-md --profile full`：导出全部字段。
- `export-md --profile brief`：只保留核心内容、逻辑展开、上屏内容、讲解方向和证据，适合转发和归档。
- `check_draft_studio.mjs`：在无头浏览器里检查页面能否正常渲染、三种视图是否生效，并报告脚本错误。

## 能识别的母稿写法

- 飞书回读快照：`# 章节`、`## P01｜标题`、`### 核心内容` 等字段小节，以及飞书的 `<title>`、`<callout>` 标记。
- 章节文件：`# CH02｜章节`、`## 章节说明小节`、`### [P08] 标题`，页面字段写成 `- 字段：值`。
- 富格式块：`:::callout 标题`、`:::flow`、`:::compare`（两栏之间用 `---` 分隔）、`:::data`（每行写 `- 数字｜说明`），每个块以 `:::` 结束。导出 Markdown 时会转成普通引用。

## 阅读页

- 左侧是章节和页面目录，带状态；每章顶部有标题链，用来检查论证有没有断开。
- 每页按字段分区：
  - 上屏内容画成 16:9 画面示意
  - 含 `→` 的逻辑展开画成流程
  - 视觉建议画成网格
  - 策略与过桥、证据与来源默认折叠，标为"内部"
- 三种视图：
  - **完整**
  - **客户视图**：隐藏视觉、过桥和证据
  - **标题链**：只看每页标题和核心判断
- 支持搜索、下载完整或简洁 Markdown、打印。
- 需要登录才能访问的飞书图片无法加载时，显示图片说明文字代替。
