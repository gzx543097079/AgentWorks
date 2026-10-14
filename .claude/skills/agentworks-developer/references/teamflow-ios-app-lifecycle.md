# 新项目的 Scene 生命周期

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/APP-LIFECYCLE.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

适用于新建 iOS/iPadOS 主 App，以及明确涉及启动生命周期的修改。普通页面需求不触发全项目迁移；扩展 Target 按扩展自身入口处理，不套用主 App 的 Scene 配置。

## 生成要求

| 工程入口 | 必须生成和核对的内容 |
| --- | --- |
| UIKit（Swift / Objective-C，包括 UIKit 内嵌 SwiftUI 页面） | iOS 13 及以上使用 Scene 生命周期；有效 Info.plist 启用 `UIApplicationSceneManifest`，配置能解析到实际编译的场景代理，窗口关联连接中的 `UIWindowScene` |
| SwiftUI App 生命周期 | 使用 `App` 与适合产品的 `Scene`（通常为 `WindowGroup`），由 SwiftUI 管理窗口；不额外强加 UIKit SceneDelegate 或覆盖框架生成的 Scene 配置 |

UIKit 窗口、根导航及窗口级主题绑定放在 Scene 连接阶段；Swift 使用 `UIWindow(windowScene:)`，Objective-C 使用 `initWithWindowScene:`。AppDelegate 只承担进程级初始化，不再用全局屏幕尺寸创建无场景的主窗口。初始主题在窗口显示前应用；前后台切换不应无故重建根页面或丢失当前导航。

静态 Scene 配置或 AppDelegate 动态返回 `UISceneConfiguration` 均可，选择与工程实际需要一致。手工 plist、Xcode 自动生成、XcodeGen 等生成式配置都要检查**构建产物中最终生效的 plist**；不能只添加一个未参与构建的 SceneDelegate 文件，或只在目录示例中列出它。配置的代理类名、模块名和 Target 成员关系须匹配。

窗口数量遵循已确认 PRD；普通单窗口项目保持单窗口，不因采用 Scene 自动增加多窗口功能。仅当明确要求支持 iOS 13 以下时，按系统可用性保留旧系统启动分支；较新系统仍使用 Scene。既有 App 不因无关需求被强制迁移。

## 工程生成后的验收

在项目的 `.agents/project-checks.json` 纳入实际构建/启动验证，验证范围包含入口源码、工程生成配置、plist、相关资源及测试。可以复用同一次 `xcodebuild test` 的构建和启动，不机械增加重复构建。

| 检查 | 所需证据 |
| --- | --- |
| 配置和目标有效 | Debug、Release 的成品 App 配置；UIKit 的有效 Scene Manifest、静态或动态代理配置与实际 Target 一致；SwiftUI 不以缺少手写 SceneDelegate 判失败 |
| 真实窗口归属 | 实际启动后的窗口关联 `UIWindowScene`，根界面可见可操作；UIKit 核对真实场景代理，SwiftUI 核对 Scene 内容正常显示 |
| 生命周期回归 | 冷启动、后台→前台、退出后重启；已有语言/主题等偏好按产品约定恢复，导航与窗口没有重复创建 |
| 原警告消失 | 读取 Debug 和 Release **实际启动日志**，没有 `UIScene lifecycle will soon be required` 等未采用 Scene 的警告；不能仅凭编译成功、空日志或过滤警告判通过 |

冷启动和窗口归属优先用能在实际 App 测试宿主运行的集成测试、UI 测试或等效可核验运行证据；字符串匹配 SceneDelegate 文件名不能证明运行时正确。没有可用设备/模拟器或未拿到启动日志时标记未验证，列明缺项，不伪填通过。

结果与启动证据写入需求卡 AC；普通业务改动复用未变的有效启动验证，不重复整套迁移验收。

参考：[Apple：迁移到 UIKit Scene 生命周期](https://developer.apple.com/documentation/uikit/transitioning-to-the-uikit-scene-based-life-cycle)。规则针对当前项目实际框架和部署目标，不以此文件代替未来 SDK 的可用性核对。
