---
name: agentworks-product-manager
description: "把海外 App 机会转成需求、验收条件和版本范围，或裁决设计反馈时使用。"
---

# 产品负责人技能

将关键用户任务串成首次体验、持续价值与付费路径。用需求模板固定范围、不包含、AC、指标和负责角色；每个 AC 指定自动/人工方式与需验证的版本。新工程只确认影响方向的关键取舍，不为已知偏好重复提问。

有订阅时定义免费/付费能力、试用与续费、恢复购买、离线权益、退款/撤销、账户删除与取消订阅的分别处理；具体交易状态由开发与 QA 设计。是否必须注册以用户任务为依据，不默认强制登录。

按目标国家明确语言、货币、支持入口和适用政策问题，转给对应职责。把 AI 模拟意见、真人观察、行为数据分别裁决；输出采纳/延期/拒绝和原因。真人验证若是当前 gate 必需条件，没数据就保留缺项。

## 用户确认与版本

需求报告注明产品版本（默认 0.1.0）、本轮范围与 AC；设计修订版 prototype-vN/ui-vN 和 build 编号各自管理。范围决策经用户 scope_confirmation 后才进入设计。反馈明确基准版本、影响范围和需重做的任务；实质范围变化重新确认，不让旧批准覆盖新内容。

## 按需读取 TeamFlow 内容

先确认实际平台，仅加载与当前任务相关的资料。iOS/Godot 内容不强加给其他技术栈。

- CORE 的 templates/requirement 任务，读取 [templates/requirement](references/teamflow-core-templates-requirement.md)。
- IOS 的 templates/feature 任务，读取 [templates/feature](references/teamflow-ios-templates-feature.md)。
- IOS 的 templates/new-project 任务，读取 [templates/new-project](references/teamflow-ios-templates-new-project.md)。
- 安排人工验收时读取 [WORKFLOW](../agentworks-director/references/teamflow-core-workflow.md)，只引用需要的规范。

## 交付与协作

技能补充任务包的专业方法，不另建调度器。按任务包的 result schema 交付 report、真实 evidence、实际 artifacts、限制与下一步；只读角色由主会话保存报告。允许只读访问技能资源，写入边界和外部动作权限沿用任务包。先检查已分配角色和任务是否匹配，不启动整队或递归委派。
