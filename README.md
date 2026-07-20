# 祈飞提案总控 Skill

`qifei-proposal` 是面向祈飞团队的比稿/标书提案生产系统。它把公司知识、客户资料、策略确认、逐章逐页讲稿、对抗检测、视觉规范和 HTML-first 导出串成一条有门禁、可追溯的工作流。

## 核心原则

- 信息与逐页讲稿完全确认后，才进入正式视觉生成。
- 背景资料提交后先用 Grill Me 逐题确定《提案策划书》；若已安装 Visualize，可用确认视图辅助决策。
- 目录确认后先生成项目 `AGENTS.md`；初始方向确认后必须完成首页、目录页、3 种章节页、低/中/高密度内容页和结尾感谢页组成的设计语言校准集，再生成 `DESIGN.md`。
- 正式视觉阶段必须上传品牌官方视觉参考，并把视觉符号、规范和色卡连同来源 ID 写入 `DESIGN.md`。
- HTML 是唯一视觉母版；Image2 负责背景、主视觉、场景、概念图和透明视觉模块。
- 正文页采用“HTML 内容模板 + 透明 PNG 表现层”，固定设计语言和组件合同，但保留内容布局弹性；设计冻结后优先按章节生成与评审。
- 最终交付 HTML、PNG、PDF 和图片型 PPT 预览；飞书文稿承载逐页演讲稿。
- 公司事实、数字、履历和案例均保留来源与核准表述，内部治理信息不对外展示。

## 目录

- `skills/qifei-proposal/`：可安装的 Skill 本体。
- `skills/proposal-ppt-production/`：内容与设计冻结后的通用页面生产、视觉载体选择与最终组装子 Skill。
- `skills/ppt-html-calibration-editor/`：评审阶段可选的本地 HTML 精细校准编辑器；JSON 仅用于回写源 HTML。
- `skills/qifei-proposal/references/`：工作流、知识治理和公司 Base。
- `skills/qifei-proposal/assets/`：项目模板和 HTML 运行时。
- `skills/qifei-proposal/scripts/`：初始化、冻结、校验、渲染与导出工具。
- `demo/visual-sample/`：不含任何真实客户资料的脱敏隔离视觉样例；状态停留在视觉生成阶段，不模拟Owner最终批准或对外交付。

## 本地使用

在 `skills/qifei-proposal` 下运行：

```bash
npm install
python3 scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner>
python3 scripts/validate_project.py <项目目录>
```

后续阶段与导出命令见 [`SKILL.md`](skills/qifei-proposal/SKILL.md)。首次使用时，应把整个 `skills/qifei-proposal` 目录安装到团队约定的 Codex Skills 目录，再以 `$qifei-proposal` 调用。

## 已验证范围

- Skill 结构与元数据校验。
- 项目门禁、内容冻结与 Deck 合同校验。
- CJK 字符预算、媒体路径、内容哈希和双 QA 自动测试。
- Edge/Chromium HTML 渲染、浏览器越界检测；评审使用 Codex 浏览器原生评论。
- 16:9 PNG、PDF 与图片型 PPT 预览导出。

生成物默认位于各项目的 `exports/`，不纳入本仓库版本控制。

## 项目解耦

- Skill 仓库只保存公司级通用规则、模板、脚本、测试和脱敏 Demo。
- 真实客户资料、项目 `AGENTS.md`、品牌资产、评审 HTML/PNG 与最终交付物保存在各自项目仓库。
- 已交付项目可以作为外部案例归档，但不得把客户名称、产品口径、页面 ID、飞书文档 ID 或本机绝对路径写回 Skill 本体。
- `tmp/` 仅用于一次性本地测试，不作为 Skill 能力、示例或发布内容。
