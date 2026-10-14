# OC / Swift 分级日志

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/LOGGING.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

需要此日志组件的新工程按已确认语言选择 Swift、Objective-C 或混编版本。五个等级为 Debug、Info、Warning、Error、Fault，Debug 构建默认全部输出；Release 编译关闭输出，包括 Error/Fault。等级不触发崩溃、持久化或远程上报，也不替代业务错误处理。

## 新工程自动接入

在已授权工程范围内接入，不重复询问已有决定；只维护 AgentWorks 本身时不生成产品或提前复制业务组件。

1. 从当前工程语言选择 swift / objc / mixed，确定真实业务源码目录；由桌面代码工具加载 [install_logging.py](../scripts/install_logging.py)，调用 `install(app_root, destination, language)`，其中 app_root 是当前产品 app/ 下的实际工程，destination 是其中源码相对目录。源码来自 Skill 的 assets/logging，不依赖个人安装。相同内容重复执行不重写；不同内容拒绝覆盖，先比较并合并。
2. 将返回的 .swift/.m 文件自动加入目标的 Compile Sources，.h 加入工程可见文件；使用 XcodeGen 时纳入目标 sources，SwiftPM 放入实际 target 源目录或 sources 列表，直接生成 .xcodeproj 时建立文件引用和 Sources Build Phase。禁止只复制文件就宣布接入完成。多个 Target 按实际调用范围分别加入，不能同时重复编译同一份实现。
3. 配置实际 Debug：Swift Active Compilation Conditions 含 DEBUG，OC Preprocessor Macros 含 DEBUG=1；Release 及用于分发的自定义配置均移除 DEBUG（OC 可设 DEBUG=0），保留其他继承配置。仅设置 -O 优化不会关闭 DEBUG。混编要分别核对两套条件；SwiftPM 用构建系统对应条件，不混用 Xcode 字段。
4. 新生成业务代码使用 TFLog / TFL 宏。至少加入一个有实际意义的 Debug 调用；核对 Debug 和 Release 构建设置，实际构建/运行验证输出与目标成员关系。验证写入项目的检查配置和需求 AC，工具缺失时保留未验证，不用文件存在证明接入。

Swift 项目只需要 [TFLogger.swift](../assets/logging/TFLogger.swift)。OC 项目使用 [TFLogger.h](../assets/logging/TFLogger.h) 与 [TFLogger.m](../assets/logging/TFLogger.m)。混编可同时使用两套原生入口，格式一致，不需要为日志新增桥接头。已有桥接头可导入 OC 头；宏不可从 Swift 调用，Swift 使用 TFLog。

已有工程增量需求不重复安装；相关需求需要日志时，优先核对既有组件是否满足分级、Debug 全量及 Release 关闭要求，再整合或补齐，保护已有定制。不在 unrelated 模块批量替换日志。

## 使用

```swift
TFLog.debug("开始加载列表")
TFLog.info("已加载条目：\(items.count)")
TFLog.warning("缓存已过期")
TFLog.error("加载失败：\(errorCode)")
TFLog.fault("发现无法恢复的本地状态")
TFLog.log(.info, "一次阶段性检查完成")
```

```objc
#import "TFLogger.h"
TFLDebug(@"开始加载列表");
TFLInfo(@"已加载条目：%lu", (unsigned long)items.count);
TFLWarning(@"缓存已过期");
TFLError(@"加载失败：%ld", (long)errorCode);
TFLFault(@"发现无法恢复的本地状态");
TFLLog(TFLogLevelInfo, @"一次阶段性检查完成");
```

输出使用 Foundation NSLog，包含时间/进程信息及 `[TFLog][等级] [文件:行号 函数] 消息`。不设置可变全局开关，Debug 不过滤等级。Swift 的消息参数使用 @autoclosure；OC 通过编译宏整体移除 Release 调用。不要把业务必需的副作用放进日志参数，Release 不会执行它们；提前计算的值不属于日志组件可阻止的求值范围。

仅输出已脱敏信息，不记录 token、完整用户信息、支付凭据或完整服务响应；Debug 全量是等级全量，不代表允许输出全部业务数据。此关闭策略只控制本组件，系统、第三方 SDK、已有 print/NSLog 需在相关范围另行核对。

## 验证与维护

在实际工程使用 macOS/Xcode 编译、运行 OC/Swift 的 Debug 与 Release，验证等级、调用位置、消息求值和目标 SDK。AgentWorks 自动测试只核对复制、幂等、冲突和路径边界，不能替代原生日志验证。

生成业务工程后仍需实际 Target 的 Debug/Release 验证，不把源仓库组件测试当产品构建成功。
