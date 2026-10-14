# Swift 代码规范

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/standards/swift.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

依据 [Swift API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/)，参考 [Airbnb Swift](https://github.com/airbnb/swift)；以下格式与工具选择是团队约定。

- 优先清晰的调用点语义；类型 UpperCamelCase，函数/属性 lowerCamelCase，Bool 名称表达断言。无既有约定时用 4 空格，保持文件现有风格，不因一个需求全仓格式化。
- 默认 let、最小访问级别；值语义合适时用 struct，引用身份/共享生命周期明确时用 class，可不继承的 class 用 final。不要为了模式而引入庞大架构。
- 用 Optional 表达缺失，用 guard/if let 解包；生产路径避免 `!`、`try!`、`as!`。确有不变量需给理由与可验证约束，不以强解代替错误处理。
- 业务失败用明确 Error；不要空 catch 或用 try? 无声抹掉重要错误。异步 API 明确取消、超时、重试和重复请求语义。
- 并发遵守工程 Swift 语言模式和严格并发配置；UI 状态按实际隔离使用 @MainActor，共享状态用 actor 或适当同步。禁止为消除诊断随意添加 @unchecked Sendable / nonisolated(unsafe)。
- async 不代表自动离开主线程；检查当前工具链隔离行为，CPU 重任务明确执行域。Task.detached 仅在隔离和取消语义清楚时使用，不作为常规线程切换。
- 闭包捕获按照所有权决定 weak/unowned，只有生命周期可证明时使用 unowned。长期 Task/AsyncSequence/Combine 订阅有取消和释放策略；审查跨 await 的强引用是否延长 owner 生命周期。
- 依赖按[依赖与工具链](../../agentworks-technical-lead/references/teamflow-core-dependencies.md)处理；不自行升级工具链、部署目标或重写模块。
- String Catalog / 本地化资源承载用户文案，并按 [多语言文本生成规则](../../agentworks-localization-specialist/references/teamflow-ios-localization.md) 使用层级可伸缩的点分键；价格从 StoreKit 数据格式化；Logger 不记录 token、完整个人数据或支付凭据。
- SwiftLint 检查与 formatter 分工明确，采用现有配置；新增工具固定版本，避免 SwiftFormat 与 swift-format 对同一文件互相改写。只对本次文件执行格式整理。
- 修改逻辑选择相关单元/集成测试；涉及 actor、取消或竞态设计能复现行为的测试，不写只验证实现细节的空泛测试。

- 新生成和本次修改的代码按 [中文注释规范](teamflow-core-standards-comments.md) 补充职责、接口契约与关键逻辑说明。

- 新工程自动接入 [分级日志](teamflow-ios-logging.md)，Debug 默认全量、Release 关闭；新增日志使用对应原生入口，消息不得含敏感数据或业务必需副作用。
