# 记忆候选

<!--
Agent 在阶段放行时，根据 `proposal_memory.py signals` 的汇总写候选；Owner 在记忆库（memory_box.py）里逐条采纳或丢弃。
采纳后写进对应层级并改为 accepted:<新编号>，丢弃改为 rejected。Agent 不改状态。
每次最多写 8 条，只写能在后续页面、阶段或其他项目复用的判断。格式：

## MC-0001｜一句话结论
- 建议层级：owner               （owner | project | playbook）
- 阶段：manuscript              （intake/strategy/manuscript/review/visual/production/export/all）
- 状态：candidate               （candidate | accepted:O-0003 | rejected）
- 日期：2026-10-25
- 来源：C-0001、R262            （必须写信号编号）
- 适用：all                     （可选）

怎么做，以及为什么。一到三句。
-->
