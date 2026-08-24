# 环境能力降级

本文件只定义能力缺失时允许继续到哪里，不改变阶段批准权。

## Visualize 不可用

- Grill Me 继续使用文本问答、Markdown决策树或表格。
- 可完成需求简报与策略讨论。
- Visualize 是增强展示，不是需求阶段硬门禁。

## 飞书不可用或未授权

- `full_deck` 可以在本地生成待同步提案稿，并保留稳定 `slide_id`；本地稿标记为 `local_fallback_pending_sync`，不能作为完整提案确认母版。
- `standalone_module` 可在任务启动时明确选择本地Markdown为内容权威；`inherited_module` 沿用父项目权威方式。
- 飞书恢复后同步整份文档、重新抓取快照并核对页序，才能继续内容确认。

## Image2 不可用或其他图像生成适配器不可用

- 可以完成品牌视觉审计、视觉命题、页面路由和去标识化提示词包。
- 不能批准视觉方向、设计校准或正式页面生成。
- 不得用纯 HTML、Moodboard 或文字说明冒充真实 Image2 样张。

## Codex 浏览器评论不可用

- 可以生成固定 16:9 HTML 与逐页 PNG，执行本地尺寸、越界、缺图和字体 QA。
- 使用本地Review Bundle或外部评论记录，以 `slide_id`、PNG哈希、评论、修订结果和Owner决定定位页面。
- 非Codex评审通道不降低质量门禁；Owner明确批准并绑定PNG哈希后，可以记录页面批准。

## 可选辅助 Skill 缺失

- `proposal-ppt-production` 缺失：使用本 Skill 内置页面路由、HTML、PNG和组装脚本继续，但输出依赖警告。
- `ppt-html-calibration-editor` 缺失：使用浏览器原生评论和本地HTML编辑继续。
- 可选辅助 Skill 缺失不得静默改变页面路线、视觉标准或批准状态。
