# 祈飞提案总控 Skill

`qifei-proposal` 是面向祈飞团队的比稿/标书提案生产系统。它把公司知识、客户资料、策略确认、逐章逐页讲稿、对抗检测、视觉规范和 HTML-first 导出串成一条有门禁、可追溯的工作流。

## 核心原则

- 信息与逐页讲稿完全确认后，才进入正式视觉生成。
- 背景资料提交后先用 Grill Me 逐题确定《提案策划书》；若已安装 Visualize，可用确认视图辅助决策。
- 目录确认后先生成项目 `AGENTS.md`；视觉样张确认后生成 `DESIGN.md`。
- 正式视觉阶段必须上传品牌官方视觉参考，并把视觉符号、规范和色卡连同来源 ID 写入 `DESIGN.md`。
- HTML 是唯一视觉母版；Image2 负责背景、主视觉、场景、概念图和透明视觉模块。
- 最终交付 HTML、PNG、PDF 和图片型 PPT 预览；飞书文稿承载逐页演讲稿。
- 公司事实、数字、履历和案例均保留来源与核准表述，内部治理信息不对外展示。

## 目录

- `skills/qifei-proposal/`：可安装的 Skill 本体。
- `skills/qifei-proposal/references/`：工作流、知识治理和公司 Base。
- `skills/qifei-proposal/assets/`：项目模板和 HTML 运行时。
- `skills/qifei-proposal/scripts/`：初始化、冻结、校验、渲染、批注与导出工具。
- `demo/visual-sample/`：不含伊利正式提案内容的隔离视觉样例。

## 本地使用

在 `skills/qifei-proposal` 下运行：

```powershell
npm install
python scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner>
python scripts/validate_project.py <项目目录>
```

后续阶段与导出命令见 [`SKILL.md`](skills/qifei-proposal/SKILL.md)。首次使用时，应把整个 `skills/qifei-proposal` 目录安装到团队约定的 Codex Skills 目录，再以 `$qifei-proposal` 调用。

## 已验证范围

- Skill 结构与元数据校验。
- 项目门禁、内容冻结与 Deck 合同校验。
- CJK 字符预算、媒体路径、内容哈希和双 QA 自动测试。
- Edge/Chromium HTML 渲染、浏览器越界检测、本地批注存储。
- 16:9 PNG、PDF 与图片型 PPT 预览导出。

生成物默认位于各项目的 `exports/`，不纳入本仓库版本控制。
