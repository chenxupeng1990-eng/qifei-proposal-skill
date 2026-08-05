# 项目占位符契约

项目模板只使用三类机器可识别占位符：

| 标记 | 含义 | 阻断规则 |
|---|---|---|
| `{{INIT:FIELD}}` | 初始化项目时由 `init_project.py` 自动替换 | 初始化后不得残留 |
| `{{REQUIRED_AT_PHASE:FIELD}}` | 必须在指定阶段开始前由项目真实信息替换 | 到达该阶段仍残留时，`validate_project.py` 阻断 |
| `{{OPTIONAL:FIELD}}` | 可选信息或后续补充项 | 不阻断阶段推进 |

规则：

1. 不再用“待填写”“待确认”表达 `AGENTS.md` 的结构性占位。
2. `PHASE` 必须来自 `validate_project.py` 的 `PLACEHOLDER_PHASES`。
3. 新增必填占位符时，必须同时增加阶段映射和行为测试。
4. 自然语言模板中的“待确认”可保留为内容工作状态，但不得混入项目治理占位符。
