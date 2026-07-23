# 提案生产 Skill 套件

这是一套面向复杂比稿、标书与经营提案的受控生产系统。它把资料审计、关键决策确认、策略与逐页讲稿、视觉校准、HTML／Image2 页面生产、逐页批准和最终 PPT 组装连接成一条可追溯工作流。

> `qifei-proposal` 是为兼容既有项目保留的技术 Skill ID。默认文案、模板和 Demo 均按通用“公司”场景设计，不包含真实客户资料或特定公司的事实库。

## 包含的 Skills

| Skill | 作用 | 是否必装 |
|---|---|---|
| `qifei-proposal` | 顶层提案治理、门禁、内容冻结与交付 | 是 |
| `grill-me-lite` | 资料进入后的轻量关键决策访谈 | 是 |
| `proposal-ppt-production` | 内容冻结后的页面载体选择、视觉生产与组装 | 推荐 |
| `ppt-html-calibration-editor` | HTML 评审阶段的本地精细校准 | 可选 |

## 核心原则

- 先确认提案策划书、策略和逐页内容，再进入正式视觉生成。
- 先用代表页确认视觉方向，再形成完整设计语言校准集和 `DESIGN.md`。
- 每页先判断服务对象、演讲任务和最佳表达载体，再决定使用 HTML、Image2 或混合路线。
- HTML 负责精确文字、数据、表格、严密关系和可编辑层；Image2 负责主视觉、场景、概念图及无文字语义节点。
- 修改循环使用 HTML 与 PNG 评审，不重复拼装 PPT。
- 只有全部页面明确批准后，才一次性导出 PNG、PDF 和 PPTX。
- 公司事实、案例、履历和数字必须由使用方写入自己的公司资料包，不随本仓库分发。

## 环境要求

- Node.js 18 或更高版本；
- Python 3.9 或更高版本；
- Microsoft Edge、Google Chrome 或 Chromium；
- macOS、Windows 或 Linux。

## 干净副本快速验证

macOS／Linux：

```bash
python3 scripts/bootstrap.py
```

Windows PowerShell：

```powershell
py -3 scripts\bootstrap.py
```

该命令会：

1. 检查 Python、Node、npm 和 Chromium 浏览器；
2. 使用锁文件安装两个 Node 运行时依赖；
3. 执行 Skill 结构、Python、浏览器编辑器和页面合同测试；
4. 在临时目录初始化一个全新提案项目并验证项目结构；
5. 检查发布目录是否混入客户名称、本机绝对路径或构建产物。

如已安装依赖，只运行自检：

```bash
python3 scripts/self_test.py
```

## 安装到 Codex

默认安装到当前用户的 `~/.codex/skills`：

```bash
python3 scripts/install_skills.py
```

指定目录：

```bash
python3 scripts/install_skills.py --target "/path/to/codex/skills"
```

Windows PowerShell：

```powershell
py -3 scripts\install_skills.py --target "$HOME\.codex\skills"
```

目标目录已有同名 Skill 时，安装器会停止。确认要替换时显式增加 `--force`。安装完成后重启 Codex，并以 `$qifei-proposal` 调用。

## 创建项目

从已安装的 `qifei-proposal` Skill 根目录运行：

```bash
python3 scripts/init_project.py --project <项目目录> --name <项目名> --owner <Owner>
python3 scripts/validate_project.py <项目目录>
```

Windows 中将 `python3` 替换为 `py -3` 或 `python`。路径包含中文或空格时使用引号。

完整阶段与导出命令见 [`skills/qifei-proposal/SKILL.md`](skills/qifei-proposal/SKILL.md)。

## 公司资料包

默认的 [`company-facts.json`](skills/qifei-proposal/references/company-facts.json) 是空模板。首次用于真实提案前，使用方必须：

1. 登记公司资料来源与版本；
2. 填入经过核准的公司定位、规模、资质、团队和案例事实；
3. 为每条事实保留 `source_id`、来源页、时间范围和对外使用状态；
4. 不把客户项目策略或未验证成绩写入公司资料包。

公司资料可以保存在私有项目中，再在运行时替换或扩展默认资料包；不建议把真实公司履历发布到公共 Skill 仓库。

## 仓库结构

- `skills/qifei-proposal/`：顶层 Skill、项目模板、运行时、脚本和测试。
- `skills/grill-me-lite/`：轻量决策访谈 Skill。
- `skills/proposal-ppt-production/`：页面生产子 Skill。
- `skills/ppt-html-calibration-editor/`：本地 HTML 校准编辑器。
- `demo/visual-sample/`：不含客户资料的隔离视觉 Demo。
- `scripts/`：跨平台安装、发布自检工具。

## 已验证能力

- Skill 元数据与必需文件检查；
- 项目初始化、门禁、内容冻结与 Deck 合同校验；
- CJK 字符预算、媒体路径、内容哈希与双 QA；
- Edge／Chromium HTML 渲染和浏览器越界检测；
- 16:9 PNG、PDF 与图片型 PPTX 导出；
- HTML 实测文字框到 PowerPoint 原生文字层的可编辑编译桥；
- 冻结字段、备注元数据和布局坐标校验。

图表、复杂 SVG、模板继承和不同办公软件中的最终渲染仍需人工视觉复核。机器测试通过不等于视觉验收通过。

## 项目隔离

- 真实客户资料、项目 `AGENTS.md`、品牌资产、评审 HTML／PNG 与最终交付物保存在各自项目目录。
- 本仓库只保存通用规则、模板、脚本、测试和脱敏 Demo。
- `tmp/`、`exports/`、`deck/editable-layout/` 与 `dist/` 都是本机构建产物，不进入版本控制。
- 不允许把客户名称、产品口径、飞书文档 ID、本机绝对路径或未公开经营数据写回 Skill 本体。

## 发布状态

当前版本见 [`VERSION`](VERSION)。该版本定位为跨电脑内部测试候选版。公开发布前，仓库 Owner 仍需决定许可证和公开支持范围。
