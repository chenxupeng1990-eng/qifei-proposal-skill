# 阶段包 07｜逐页路由、视觉生产与评审Loop

## 当前目标

在统一设计语言下，为每页选择最佳表达载体，生成可评论的HTML/PNG并完成视觉确认。

## 必须读取

- [../references/page-production-loop.md](../references/page-production-loop.md)
- Image2或浏览器评论不可用时读取 [../references/environment-degradation.md](../references/environment-degradation.md)。
- 已安装时可调用 `$proposal-ppt-production` 执行页面载体、Image2/HTML、评审PNG与组装准备；它不能改写内容权威或批准状态。
- HTML评论与精细校准可调用 `$ppt-html-calibration-editor`；编辑器状态和评论关闭不等于页面确认。
- 辅助 Skill 的输入输出统一按 [../references/integration-contracts.json](../references/integration-contracts.json) 归一化，不直接依赖其内部文件结构。

## 每页生产路由

- 服务对象与演讲任务。
- 核心思想和内容关系。
- 最佳载体与唯一主导类型。
- 视觉论点与视觉锤。
- Image2语义角色、资产和视觉家族。
- HTML保护的精确文字、数据和关系。

## Loop

核心思想 → 载体 → Image2资产 → HTML实现 → 1920×1080单页检查 → 整章montage → 浏览器评论 → 回到权威源修改 → 重建。

## 硬规则

- 每张正式页至少使用一个服务核心思想的Image2资产。
- HTML不能独立承担整页审美。
- 不用无关装饰图过门禁。
- 评论关闭和QA通过都不等于页面确认。
- 只有Owner明确确认的版本才能进入拼装准备库。
- 发给Image2或其他外部服务的提示词必须去标识化，不上传标书全文、报价、联系人、账号、内部批注或未公开经营数据。
