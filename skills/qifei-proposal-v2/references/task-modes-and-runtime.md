# 任务模式与运行能力

本文件是任务规模、Agent环境、适配器和功能边界的唯一说明。不得按“是否订阅Codex”判断能力；必须检测实际能力。

## 1. 任务模式

| 模式 | 适用任务 | 保留门禁 | 省略或继承 |
|---|---|---|---|
| `full_deck` | 0–1完整长提案或完整演示 | 完整策略、全稿审查、内容冻结、视觉方向、校准、讲稿与导出 | 无 |
| `inherited_module` | 向已有受控PPT增加或替换模块 | 模块目标、上下游策略接口、确认稿、页面路由、视觉QA | 继承父项目冻结内容与设计；不重做全稿红队和视觉方向 |
| `standalone_module` | 独立的单页或2–8页内容模块 | 轻量简报、模块判断、页面链、视觉基线、页面QA | 不要求完整目录、全稿红队或全案讲稿 |

模块在内容冻结前必须填写 `strategy_input`、`module_claim`、`strategy_output`，并登记稳定 `slide_id`。模块模式不是跳过内容判断。

### 1.1 任务性质：说服型与视觉表现型

任务模式管规模，任务性质管“这份东西靠什么打动人”。两者独立，在任务一开始就定（`init_project.py --task-nature`，写入 `project-state.json.task_nature`），中途不改。

**开项目时必须问用户，不由 Agent 默认决定。** 先根据用户的需求给出建议和理由，再请用户选择。问法：

> 这份 PPT 主要靠什么打动人？
>
> A. **强逻辑叙述**：每页有论点和证据，一步步推出结论。适合提案、比稿、方案汇报、招商。文字和数据精确，导出的 PPTX 文字可编辑。
>
> B. **视觉表现力**：文字少，靠画面传达品牌气质。适合品牌手册、品牌画册、形象展示、发布会视觉。整页直接生图，画面张力更强；导出的 PPTX 以整页图片为主，文字基本不能再改。
>
> 我的建议：B，因为你要做的是品牌手册，没有需要说服评审的论证链，重点是品牌的视觉和气质。

- 建议要结合具体需求说理由，不要只报选项。拿不准时说明两种各自的取舍，请用户定。
- 用户的选择写进策划书（或模块简报）的“表达方式”一行，例如“表达方式：视觉表现力（Owner 选定，品牌手册）”。`validate_project.py` 会核对它和 `task_nature` 一致。
- 混合需求（比如提案里有几页品牌形象展示）选强逻辑叙述，那几页按页面路线例外处理。

| 性质 | 适用任务 | 默认页面路线 | 门禁差异 |
|---|---|---|---|
| `persuasive`（默认） | 提案、比稿、营销方案 | `image_plus_html`：整页生图底图＋HTML 文字层 | 全部现有门禁 |
| `visual_showcase` | 品牌手册、品牌视觉画册、产品视觉集 | `image_full`：整页直接生图，上屏文字和设计要求一起交给生图模型 | 章节不要求“本章回答 / 逻辑路径 / 情绪方向”；全稿审查看品牌表达是否准确、一致，不审说服链 |

`visual_showcase` 的要点：

- 文字少、看重视觉张力，所以文字由生图模型一并画出，不再用 HTML 文字层“修正”画面。
- 内容冻结、设计校准、母版和 Owner 逐页确认照常执行；冻结的是上屏文字和视觉要求。
- 生成后逐页核对图上的文字（见 [page-production-loop.md](page-production-loop.md) 的“整页生图页面”）。出错的字，框出区域局部重生成，不改走 HTML 文字层。这需要生图工具支持带蒙版的局部编辑，doctor 会把它列为 `image_edit` 缺口。
- 导出的可编辑 PPTX 以整页图片为主，文字不可编辑；这是选择这条路线时就接受的取舍，导出时向 Owner 说明。
- 个别页面文字多或有数据（色值表、规格表等），在该页登记 `render_route: image_plus_html`，照提案页的方式做。
- `persuasive` 任务里个别页面想整页生图，按页面路线例外处理：登记 `route_exception` 并附 Owner 批准记录。

## 2. 运行档位

运行 `python3 scripts/doctor.py --task-mode <模式> --project <项目目录> --json`；有项目时，结果里的 `proposal_memory.text` 就是本阶段要用的提案记忆。如当前Agent能力不能由本机命令发现，提供不含密钥的 capability JSON。

| 档位 | 能力边界 |
|---|---|
| `codex_full` | Codex工具、图像生成、视觉识别与本地运行时齐全 |
| `api_full` | 其他Agent具备文件、命令、图像API、视觉识别和本地运行时；可完成正式生产 |
| `local_production` | 可渲染、评审和导出，但缺少正式图像生成；不能通过正式视觉门禁 |
| `content_only` | 只保证策略、成稿、页面路由和提示词包；不承诺正式视觉或PPTX |

## 3. 适配器

### 由 Agent 声明自己的能力

`doctor.py` 是 Python 脚本，看不到调用它的 Agent 有哪些工具。图像生成、看图和 Codex 原生浏览器评论要由 Agent 自己声明：

```bash
python3 scripts/doctor.py --project <项目目录> \
  --image-provider codex_builtin \
  --visual-understanding \
  --native-comments
```

- `--image-provider`：本 Agent 能调用的生图方式，如 `codex_builtin`、`magpie-image`、`openai_api`。
- `--visual-understanding`：本 Agent 能读图并判断画面。
- `--native-comments`：本 Agent 有 Codex 原生浏览器评论。
- `--remember`：把这次声明保存到 `~/.qifei-proposal/runtime.json`，之后在这台电脑上不传参数也有效；`--forget` 清除。保存的声明对这台电脑上的所有 Agent 生效，只保存每个 Agent 都具备的能力；某个 Agent 独有的能力，每次运行时声明。
- 环境变量 `PROPOSAL_IMAGE_PROVIDER`、`PROPOSAL_VISUAL_UNDERSTANDING=1`、`PROPOSAL_CODEX_NATIVE_COMMENTS=1` 仍然有效，优先级在本次声明之后、已保存的声明之前。
- 只声明真实可用的能力。声明只决定开工时的能力判断，不放松任何门禁：正式出图仍要登记提供方、模型、提示词、参考图和文件哈希；独立视觉审查仍要另一个 Agent 出具绑定截图哈希的报告；没有原生评论时，评审用绑定 PNG 哈希的评审记录，不能把本地检查说成原生评论确认。
- `doctor` 会自动识别 Agent 宿主（Claude Code、Codex），也可以用 `--agent-host` 指定。
- 声明之后仍缺的能力，doctor 列为 `GAP`，先问用户能否补齐，不默认降级；流程见 [environment-degradation.md](environment-degradation.md)「先问能否补齐，再降级」。

### 可替换的适配器

- 图像：Codex内置图像生成、OpenAI兼容API或项目登记的自定义命令均可。不得把模型名称当门禁；必须登记提供方、模型、提示词、参考图、尺寸、文件哈希和 `visual_family_id`。
- 内容权威：完整提案默认工作台（`studio`，本地即可运行，见 [draft-studio.md](draft-studio.md)）；飞书是可选的协作适配器；继承模块沿用父项目；独立模块可选择工作台、飞书或本地Markdown。
- 评审：Codex原生评论、本地Review Bundle或外部评论记录均可。Owner批准必须绑定对应PNG哈希。
- 独立审查：可由独立Agent上下文、独立API调用或指定人工评审者完成；不得复用主生产上下文冒充独立审查。
- 页面生产：设计与内容门禁通过后，可使用 `parallel_after_gates` 计划按波次并行；默认3个、硬上限6个 Agent，主 Agent负责集成和复验。没有原生并行编排时按同一计划顺序执行，并明确标记为降级。

## 4. 不可替代边界

- 没有图像生成能力时，不批准正式视觉方向和正式页面。
- 没有视觉识别或人工视觉复核时，不能完成独立视觉审查。
- 没有Node、浏览器或等价导出服务时，不承诺本地PNG/PDF/PPTX。
- 没有飞书能力时，不提供飞书revision、回读和协作证明；用工作台的修订日志、登记和章节确认记录作为凭证。
- 不同图像模型不保证产生完全相同的审美结果。
- API Key、访问令牌和中转密钥不得写入项目状态、提示词记录或日志。
