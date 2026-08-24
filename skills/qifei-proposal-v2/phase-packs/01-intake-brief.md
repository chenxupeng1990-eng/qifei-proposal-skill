# 阶段包 01｜资料、Grill Me 与提案策划书

## 当前目标

确认资料范围、项目决策和提案策划书，为策略阶段提供稳定输入。

## 必须读取

- [../references/task-modes-and-runtime.md](../references/task-modes-and-runtime.md)：先确认任务是完整提案、继承模块还是独立模块，并向用户声明当前环境的交付边界。
- [../references/knowledge-policy.md](../references/knowledge-policy.md)：资料权威、版本或保密边界发生判断时。
- [../references/company-base.md](../references/company-base.md)：需要公司能力与案例时。
- `references/company-facts.json`：需要数字、履历、案例成绩时。
- 同套件 `$grill-me-lite`。
- 交互结果按 [../references/integration-contracts.json](../references/integration-contracts.json) 的 `grill-me-lite.v1` 归一化；不依赖外部 Skill 的固定文案或文件格式。
- 若当前会话已安装并提供 `Visualize:visualize`，可在 Grill Me 和策划书确认过程中生成决策树、范围地图、选项对比或策划书确认视图，帮助用户快速判断；Visualize只承担展示与交互，不替代逐题确认和书面 `proposal-brief.md`。

## 必须产出

- `task_mode`、`deliverable_level` 与运行能力报告。
- 资料登记与缺口。
- Grill Me 决策记录。
- 按需生成的Visualize确认视图及其对应决策结论。
- `content/proposal-brief.md`。
- 对应批准记录。

## 禁止动作

- 不生成正式策略目录。
- 不写PPT正文。
- 不生产视觉方向。

## 放行

完整提案的策划书或模块简报无占位符，Owner确认，`validate_project.py`通过。
