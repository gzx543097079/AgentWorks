# Objective-C 代码规范

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/standards/objective-c.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

适用 `.h/.m/.mm`；UI 同时执行 UI 规范。以已有工程约定优先，新增无约定代码采用以下团队默认。参考 [Apple Objective-C 编程指南](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/ProgrammingWithObjectiveC/Introduction/Introduction.html) 与 [NYTimes 风格指南](https://github.com/NYTimes/objective-c-style-guide)；后者已归档，仅借鉴稳定风格。

- 类型用团队前缀和 UpperCamelCase，方法/变量 lowerCamelCase；方法片段表达参数含义。4 空格缩进，花括号不省略，指针靠变量，避免无关格式改动。
- 头文件只公开必要接口；使用 forward declaration 降低依赖。私有属性放 class extension；枚举用 NS_ENUM / NS_OPTIONS，常量优先有类型的 static const 或 FOUNDATION_EXPORT。
- ARC 为默认。对象属性明确 nonatomic 和 strong/copy/weak；NSString、可变来源集合的不可变快照及 block 按语义用 copy，delegate 通常 weak。不能机械地把所有引用改成 weak。
- 公开接口在适合时使用 NS_ASSUME_NONNULL_BEGIN/END，并显式标注真实 nullable；集合使用轻量泛型，跨 Swift 桥接核对空值和名称。禁止用错误非空标注掩盖实际 nil。
- weakSelf / strongSelf 根据 block 生命周期和所有权决定。排查 owner→block→owner、NSTimer、CADisplayLink、通知 block token、KVO、代理和异步回调；解绑应在实际生命周期结束时完成，不能只依赖可能永远不执行的 dealloc。
- UIKit 更新在主线程；I/O、解码和重计算离开主线程。共享可变状态明确同步策略，nonatomic 不提供线程安全。
- 错误通过现有 NSError/回调约定传递；不要吞错或用 NSException 处理常规业务错误。判断集合边界、对象类型、nil、重复回调和取消。
- Core Foundation 创建/复制对象确认释放；桥接明确 __bridge / __bridge_transfer 等所有权，不混用 ARC 与 CF 管理。
- `.mm` 的 C++ 对象释放、RAII、异常边界沿用已有 C++ 规范；OC 规则不能替代 C++ 审查。
- App 用户可见文本通过 `NSLocalizedString` 或项目现有封装读取，并按 [多语言文本生成规则](../../agentworks-localization-specialist/references/teamflow-ios-localization.md) 使用层级可伸缩的点分键；不在 `.h/.m/.mm` 中直接写最终展示文案。
- 变更验证：使用工程现有 clang-format 配置检查改动文件；运行相关构建和测试，涉及所有权时用 Xcode Analyze、Memory Graph / Instruments 补证据。没有工具记录未验证，不声称零泄漏。

- 新生成和本次修改的代码按 [中文注释规范](teamflow-core-standards-comments.md) 补充职责、接口契约与关键逻辑说明。

- 新工程自动接入 [分级日志](teamflow-ios-logging.md)，Debug 默认全量、Release 关闭；新增日志使用对应原生入口，消息不得含敏感数据或业务必需副作用。
