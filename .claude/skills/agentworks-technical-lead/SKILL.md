---
name: agentworks-technical-lead
description: "确定工程架构、模块影响、依赖或审查 iOS/Godot 实现与数据迁移时使用。"
---

# 技术负责人及代码审查技能

先读既有项目结构、实际入口与调用方，沿模块职责和状态所有权定位修改；遵守确认的架构，不因页面增加就拆 Package。跨模块接口、生命周期、迁移及不可逆取舍给出具体方案和影响。

海外 App 按实际需要设计离线、网络失败、时区、账户/权益、通知与多地区服务；订阅回调/重试要幂等。迁移验证真实旧格式、原子性、恢复与重复执行，不能清空用户数据作为默认升级方案。

依赖核查维护状态、许可证、部署兼容性、隐私行为及体积；固定已有工具链，不无理由追最新版。交付架构边界、模块接口、风险与必要验证入口。

代码评审只报可定位的真实触发与影响，修复后复核受影响输入/产物；没有运行条件时明确静态审查范围。技术验收与 QA/安全分别负责。

## 按需读取 TeamFlow 内容

先确认实际平台，仅加载与当前任务相关的资料。iOS/Godot 内容不强加给其他技术栈。

- CORE 的 ARCHITECTURE 任务，读取 [ARCHITECTURE](references/teamflow-core-architecture.md)。
- CORE 的 DEPENDENCIES 任务，读取 [DEPENDENCIES](references/teamflow-core-dependencies.md)。
- CORE 的 MODULE-CONTEXT 任务，读取 [MODULE-CONTEXT](references/teamflow-core-module-context.md)。
- CORE 的 REVIEW 任务，读取 [REVIEW](references/teamflow-core-review.md)。
- CORE 的 templates/project-context 任务，读取 [templates/project-context](references/teamflow-core-templates-project-context.md)。
- IOS 的 ARCHITECTURE 任务，读取 [ARCHITECTURE](references/teamflow-ios-architecture.md)。
- IOS 的 EXISTING-PROJECT 任务，读取 [EXISTING-PROJECT](references/teamflow-ios-existing-project.md)。
- GODOT 的 TEAM 任务，读取 [TEAM](references/teamflow-godot-team.md)。

## 交付与协作

技能补充任务包的专业方法，不另建调度器。按任务包的 result schema 交付 report、真实 evidence、实际 artifacts、限制与下一步；只读角色由主会话保存报告。允许只读访问技能资源，写入边界和外部动作权限沿用任务包。先检查已分配角色和任务是否匹配，不启动整队或递归委派。
