# 提案母稿工作台合同

母稿工作台把提案母稿渲染成适合阅读的富格式页面，导出干净的 Markdown；运行本地服务时，可以在页面上直接编辑，保存即写盘，所有打开的页面实时刷新。评论在后续版本（M3）加入；工作台成为正式权威源、接入阶段门禁，在 M4 完成。

## 权威源不变

- 权威源仍是项目登记的母稿：`project-state.json.proposal_draft.verified_snapshot_path`。没有登记时，依次查找 `content/draft/proposal-draft.md` 和 `content/feishu/proposal-draft.md`。
- 阅读页和导出的 Markdown 都是派生物。不能把它们登记为确认凭证，也不能反向覆盖母稿。
- 页面状态读取自 `project-state.json`：章节 `manuscript_confirmed` 显示为"已确认"，在 `verified_slide_ids` 中的页面显示为"已回读"，其余显示为"待确认"。

## 命令

在 `skills/qifei-proposal-v2/` 目录下运行：

```bash
python3 scripts/draft_studio.py render <项目目录> [--draft <母稿路径>] [--out deck/review/draft-studio.html]
python3 scripts/draft_studio.py export-md <项目目录> [--profile full|brief] [--out <文件>]
python3 scripts/draft_studio.py serve <项目目录> [--draft <母稿路径>] [--port 8765] [--open]
node scripts/check_draft_studio.mjs <阅读页.html>
```

- `render`：生成单个 HTML 文件，可以离线打开。用 `--draft` 可以只渲染某一章的章节文件。
- `export-md --profile full`：导出全部字段。
- `export-md --profile brief`：只保留核心内容、逻辑展开、上屏内容、讲解方向和证据，适合转发和归档。
- `serve`：启动本地工作台（默认只监听 127.0.0.1），在终端打印访问地址。见下文"在线编辑与实时同步"。
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

## 在线编辑与实时同步（serve）

- **就地编辑**：鼠标移到字段上会出现"编辑"按钮。编辑框里是这段内容的 Markdown 源文；⌘/Ctrl+Enter 保存，Esc 取消。页面标题、章节说明也可以编辑。章节文件这类用"- 字段：值"写的页面，按整页源文编辑。
- **保存即写盘**：
  - 每次保存只替换这一段对应的源文行，原子写入母稿。
  - revision 加 1，重新计算 SHA256，把整份快照写入 `<母稿所在目录>/revisions/rev-NNNNNN.md`。
  - 在 `revisions/log.jsonl` 记录一条日志：版本、哈希、时间、修改者、涉及的页面。
  - 工作台第一次打开时，以当前文件写一条 baseline 记录，起始版本号沿用 `proposal_draft.revision_id`。
- **冲突**：保存时会核对编辑开始时的哈希。母稿已经被别处改过时返回冲突，你的文字留在编辑框里，可以选择保存到最新版本。
- **结构保护**：编辑内容不能新增、删除或重排页面；页面结构的变更走 `page-change-proposals.md` 流程。
- **外部修改**：Agent 或其他程序直接写母稿文件时，工作台在约 0.5 秒内识别到变化，记为修改者 `external` 的新版本，并推送给所有打开的页面：涉及的页面会高亮，同时提示"母稿文件被外部修改 · rev N · 页码"。所以 Agent 直接改 Markdown 即可，不需要调用接口。
- **状态**：已确认或已回读的页面一旦被编辑，状态显示为"已修改·待重新确认"。编辑前会提醒这一点。
- **安全**：
  - 服务默认只监听本机。
  - 页面内嵌一次性令牌，所有接口都要校验令牌和 Host，防止其他网页借浏览器改母稿。
- **边界**：工作台的版本日志是本地记录。在 M4 之前，飞书仍是 `full_deck` 的正式权威源。所以 Owner 在工作台里的修改要回写飞书、重新回读后，才能登记确认。

