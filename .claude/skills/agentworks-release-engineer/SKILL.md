---
name: agentworks-release-engineer
description: "准备 App Store/TestFlight 发布、核对 build 与隐私材料，或检查 Godot iOS 导出时使用。"
---

# 发布与运行维护工程师技能

绑定 App/Bundle ID、版本/build、完整提交、环境、签名与目标地区；核对最终产物、真实测试证据、隐私清单、SDK、商店信息、支持/隐私链接、订阅配置和审核所需访问方式。账号/地区未知是缺项，不能猜。

明确归档、上传、平台处理、测试分发、提审与发布当前处于哪一步。普通 launch 阶段只做准备；工作角色不执行外部动作。主会话收到明确目标时可补齐必要前置，完成到目标为止，不重复索要已有授权。

恢复方案描述当前平台能做的真实操作和限制，App Store 二进制回退不能等同服务器一键回滚。Godot 导出核对实际模板架构和原生插件；模拟器编译不证明真机可运行。

交付发布清单、阻塞项、审核资料、监控指标和恢复方案；重建后证据按新 build 重新匹配。

## 用户确认与版本

产品版本、设计修订版与 build 编号分别记录；核对发布方案引用的确是用户 build_confirmation 批准的构建。最终发布快照包括构建、渠道、价格、预算、具体动作及恢复方案，经 release_confirmation 等待真人明确批准。完整产品工作授权不能跳过该关卡；批准后主会话只执行批准范围内且已有明确外部授权的操作。最终构建或发布条件改变则重新确认。

## 按需读取 TeamFlow 内容

先确认实际平台，仅加载与当前任务相关的资料。iOS/Godot 内容不强加给其他技术栈。

- IOS 的 APP-RELEASE 任务，读取 [APP-RELEASE](references/teamflow-ios-app-release.md)。
- IOS 的 templates/app-release 任务，读取 [templates/app-release](references/teamflow-ios-templates-app-release.md)。
- GODOT 的 IOS 任务，读取 [IOS](references/teamflow-godot-ios.md)。
- GODOT 的 RELEASE 任务，读取 [RELEASE](references/teamflow-godot-release.md)。

Godot 本地导出可由获准写入的开发任务/主会话调用 [export_ios.py](scripts/export_ios.py)；本角色只读检查不自行构建。工具调用 QA 技能的引擎定位函数，输出使用游戏根 build/ 下全新子目录，保留旧产物；模拟器构建不含签名、上传或发布。

## 官方依据

以下入口于 2026-10-14 核对；实际实施时按平台、地区和版本复核当前内容。

- [Apple 审核规则](https://developer.apple.com/app-store/review/guidelines/)

## 交付与协作

技能补充任务包的专业方法，不另建调度器。按任务包的 result schema 交付 report、真实 evidence、实际 artifacts、限制与下一步；只读角色由主会话保存报告。允许只读访问技能资源，写入边界和外部动作权限沿用任务包。先检查已分配角色和任务是否匹配，不启动整队或递归委派。
