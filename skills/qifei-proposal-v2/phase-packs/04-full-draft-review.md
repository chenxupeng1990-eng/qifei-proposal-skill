# 阶段包 04｜一次性全稿审查与内容冻结

## 当前目标

只执行一次全稿完整性审查，修复结构和表达问题后冻结内容。

`full_deck` 执行一次独立全稿审查；模块模式不执行全稿红队，只检查模块策略接口、确认稿、页序和上下游承接后冻结模块内容。

## 必须读取

- [../references/full-draft-integrity-redteam.md](../references/full-draft-integrity-redteam.md)
- [../references/cross-page-semantic-qa.md](../references/cross-page-semantic-qa.md)

## 审查范围

- 总策略与章节接口。
- 标题链、表达力度与情绪流。
- 页间、章间推导。
- 拆页、合页、信息密度。
- 视觉锤与载体可生成性。

## 禁止动作

- 不重新审判Owner确认的事实、策略和场外决定。
- 不外搜资料。
- 不引入安全、合规、风险或证据审计。
- 不逐章重复红队。

## 放行

完整提案由独立Agent上下文、独立API调用或指定人工评审者完成一次审查；模块由Owner确认模块接口与成稿。随后生成内容冻结ID。
