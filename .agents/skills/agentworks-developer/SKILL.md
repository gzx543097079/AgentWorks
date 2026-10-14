---
name: agentworks-developer
description: "按确认的方案实现 iOS 或 Godot 产品、修复缺陷，接入日志、购买与海外 App 服务时使用。"
---

# 全栈与游戏开发工程师技能

读取确认的需求、技术方案与设计，修改 app/，遵守已有目标结构、状态所有权和真实调用链。按语言读 Swift/SwiftUI/Objective-C 或 GDScript，生命周期、异步取消、错误恢复和数据迁移有变更时读相应规范。

有订阅时建立产品 ID/商店/权益映射，区分购买待处理、验证成功、取消、恢复、过期、退款/撤销；同一交易幂等，不只信任客户端开关。先用 Xcode 测试配置验证逻辑，再用真实配置的 Sandbox/TestFlight 核对环境差异；未测状态明确列出。协议和 API 实施时核对当前官方文档。

账户删除覆盖实际存储/后端与第三方处理，并明确删除与取消订阅不同；埋点遵照数据字典、最小化个人信息。外部 AI 服务若适用，检查数据发送、超时、费用与用户可理解的失败路径，不把密钥放客户端。

日志使用现有组件；需要 TeamFlow 日志时从 assets/logging 复制匹配语言，确认目标编译成员与 Debug/Release 行为。脚本只复制文件，不代表已接入构建。修复后跑受影响检查，交付文件、AC 对应证据和未验证项，由独立职责复核。

## 按需读取 TeamFlow 内容

先确认实际平台，仅加载与当前任务相关的资料。iOS/Godot 内容不强加给其他技术栈。

- CORE 的 standards/comments 任务，读取 [standards/comments](references/teamflow-core-standards-comments.md)。
- IOS 的 APP-LIFECYCLE 任务，读取 [APP-LIFECYCLE](references/teamflow-ios-app-lifecycle.md)。
- IOS 的 LOGGING 任务，读取 [LOGGING](references/teamflow-ios-logging.md)。
- IOS 的 standards/swift 任务，读取 [standards/swift](references/teamflow-ios-standards-swift.md)。
- IOS 的 standards/swiftui 任务，读取 [standards/swiftui](references/teamflow-ios-standards-swiftui.md)。
- IOS 的 standards/objective-c 任务，读取 [standards/objective-c](references/teamflow-ios-standards-objective-c.md)。
- GODOT 的 GDSCRIPT 任务，读取 [GDSCRIPT](references/teamflow-godot-gdscript.md)。
- 技术方案或迁移时读取 [ARCHITECTURE](../agentworks-technical-lead/references/teamflow-core-architecture.md)，只引用需要的规范。
- 实现本地化时读取 [LOCALIZATION](../agentworks-localization-specialist/references/teamflow-core-localization.md)，只引用需要的规范。
- 实现 UI时读取 [standards/ui](../agentworks-ui-designer/references/teamflow-ios-standards-ui.md)，只引用需要的规范。
- 实现键盘时读取 [standards/ui-keyboard](../agentworks-ui-designer/references/teamflow-ios-standards-ui-keyboard.md)，只引用需要的规范。
- 实现付费墙时读取 [standards/ui-paywall](../agentworks-ui-designer/references/teamflow-ios-standards-ui-paywall.md)，只引用需要的规范。

需要生成日志源码时可由桌面代码工具加载 [install_logging.py](scripts/install_logging.py)，调用 `install(app_root, destination, language)`；`app_root` 是当前产品的 app/ 工程根。支持 swift/objc/mixed，保留既有定制，禁止越界目标。资产位于 [TFLogger.swift](assets/logging/TFLogger.swift)、[TFLogger.h](assets/logging/TFLogger.h)、[TFLogger.m](assets/logging/TFLogger.m)。现有日志已满足要求就不新增。

## 官方依据

以下入口于 2026-10-14 核对；实际实施时按平台、地区和版本复核当前内容。

- [StoreKit 开发与 Sandbox 测试](https://developer.apple.com/documentation/storekit/testing-at-all-stages-of-development-with-xcode-and-the-sandbox)
- [账户删除](https://developer.apple.com/support/offering-account-deletion-in-your-app/)

## 交付与协作

技能补充任务包的专业方法，不另建调度器。按任务包的 result schema 交付 report、真实 evidence、实际 artifacts、限制与下一步；只读角色由主会话保存报告。允许只读访问技能资源，写入边界和外部动作权限沿用任务包。先检查已分配角色和任务是否匹配，不启动整队或递归委派。
