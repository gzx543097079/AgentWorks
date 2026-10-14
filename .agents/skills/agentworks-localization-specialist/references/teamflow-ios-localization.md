# iOS 本地化实现

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/LOCALIZATION.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

用户可见文本范围、自然表达、语义键、资源同步和验收遵循[共用本地化规则](teamflow-core-localization.md)。

原生资源使用工程已有 String Catalog、`.strings` 或 `.stringsdict`。Swift／SwiftUI／Objective-C 沿用既有 API；没有封装时分别使用 `String(localized:)`、明确本地化后的 SwiftUI 文本或 `NSLocalizedString`，传入语义键而非最终展示文案。变体和复数使用 String Catalog variation 或 `.stringsdict` 规则，不用英文单复数分支代替语言规则。
