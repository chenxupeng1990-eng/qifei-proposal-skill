# 环境能力降级

本文件只定义能力缺失时允许继续到哪里，不改变阶段批准权。

## 先问能否补齐，再降级

能力缺失时不默认降级。`doctor.py --project <项目目录>` 会把可以补齐的缺口逐项列成 `GAP`，每项带一个问题和几种补齐办法：

| 缺口 | 影响的阶段 | 常见补齐办法 |
|---|---|---|
| `image_generation` | 视觉方向、设计校准、正式页面 | 当前 Agent 能生图就声明 `--image-provider`；配置 OpenAI 兼容图像 API；换能生图的 Agent 做视觉阶段 |
| `visual_understanding` | 独立视觉审查 | 当前 Agent 能看图就声明 `--visual-understanding`；交给能看图的 Agent；指定人工审查者 |
| `local_runtime` | 页面评审、讲稿、QA、导出 | 运行 `python3 scripts/bootstrap.py --suite v2`；安装 Chrome / Edge 或设置 `CHROME_PATH` |

1. Agent 把每个 `GAP` 的问题和办法原样告诉用户，问能否补齐。
2. 补齐后重跑 doctor，缺口消失即可继续。
3. 用户明确选择暂不补齐时，运行 `python3 scripts/doctor.py --project <项目目录> --accept-gap <缺口> --by <Owner> --note "<原因、何时再处理>"`，记入 `project-state.json` 的 `runtime_decisions`。
4. 项目离开需求阶段（进入 `strategy`）时，`validate_project.py` 检查 doctor 记录的每个缺口：要么已经补齐，要么有 Owner 的接受记录；否则不放行。

飞书和 Codex 原生浏览器评论不算缺口：工作台和绑定 PNG 哈希的评审记录是内置的等价方案，doctor 只作为边界提示。

## 最低可用配置

`doctor.py` 的结果是唯一依据；下表只帮助向用户说明能交付到哪一步。

| 可用能力 | 最远可推进到 | 交付物 |
|---|---|---|
| 只有本地文件与 Python | 需求简报、策略骨架、`full_deck` 内容确认与内容冻结（工作台为权威源） | 简报、策略、工作台母稿、修订日志与章节确认记录 |
| + 飞书（可选） | 改用飞书作为协作与权威源 | 飞书提案母稿与回读快照 |
| + Image2（或其他已声明图像适配器） | 视觉方向、设计校准、正式页面生产 | 方向样张、`DESIGN.md`、页面资产 |
| + Node.js / 浏览器渲染 | 页面评审、讲稿、QA 与拼装 | PNG、PDF、图片型 PPTX；坐标与渲染 QA 通过后可出增强 PPTX |

缺少某项能力只阻塞依赖它的阶段，不阻塞前面的阶段。

## Visualize 不可用

- Grill Me 继续使用文本问答、Markdown决策树或表格。
- 可完成需求简报与策略讨论。
- Visualize 是增强展示，不是需求阶段硬门禁。

## 飞书不可用或未授权

- 默认的工作台不依赖飞书，不受影响。
- 项目原本选用飞书时，可以在本地生成待同步提案稿，并保留稳定 `slide_id`；本地稿标记为 `local_fallback_pending_sync`，不能作为完整提案确认母版。也可以由 Owner 决定把权威源改为工作台：先运行 `normalize` 和 `check`，再在工作台上逐章确认、登记。
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
