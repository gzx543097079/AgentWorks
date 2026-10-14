# Godot 与 iOS

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/Godot/references/IOS.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

本文件补充引擎与平台交界；签名、隐私和外部动作使用[App 发布规则](teamflow-ios-app-release.md)，不另写授权表。

## 导出输入与产物

先确认项目实际 Godot 版本、匹配的导出模板、渲染器、iOS 最低版本、Xcode、插件和导出预设。GDScript 为本扩展验证范围；C#、自编译模板或 GDExtension 不沿用未经实际验证的结论。

在 macOS + Xcode 上由 Godot 导出，再由 Xcode 构建和部署。导出需要有效 Team ID 与 Bundle ID；账号、证书和真实目标沿用既有配置，不能猜测。工具链升级时重新核实对应版本的官方限制。

游戏源码、导出预设、原生插件和必要导出处理脚本是权威输入。生成的 Xcode 工程与 App 是产物；需长期保留的修复放到可重复生成的源配置／插件／导出处理，禁止只改生成工程后声称已永久修复。已有受维护的 Xcode 宿主工程或官方开发期资源链接方案沿用实际结构，不自动删除或重建。

### 导出与模拟器构建

[export_ios.py](../scripts/export_ios.py) 先核对已知前置条件，再无界面导出 Xcode 工程并用 xcodebuild 做关闭签名的模拟器 Debug 构建；可作为 iOS profile 的检查项，以 `extends` 包含游戏检查：

```sh
python3 <发布技能目录>/scripts/export_ios.py --project game --output build/ios
```

- Godot 无界面导出遇到配置问题时只报 “configuration errors”，不给原因。常见缺项：项目图标（`config/icon`）、`textures/vram_compression/import_etc2_astc=true`、Team ID、Bundle ID；脚本一次列出全部缺项。
- 预设须开启 `application/export_project_only`，构建交给 xcodebuild。只做模拟器构建时 Team ID 可用占位值，真机与发布使用真实身份。
- 模拟器架构以导出的 `libgodot.a` 实际架构为准（目录名不可信）。官方 4.7.2 模板的模拟器切片只有 x86_64：Apple 芯片上 iOS 26 模拟器无法安装运行，脚本仍按 x86_64 核对构建并给出提示；运行与视觉验收须用真机或含 arm64 模拟器切片的模板，否则保持未验证。
- 导出目录 `build/` 是产物，加入忽略规则，不提交。

需求证据绑定引擎输入及原生源码；平台动作记录最终 build、完整 commit 和可定位结果。重新导出或重建后，核对旧安装／测试结论是否仍适用。

## 原生桥接

支付、广告、Game Center、权限或原生 UI 涉及时核对项目真实插件版本与兼容性。接口明确请求参数、成功／失败／取消、回调线程、重复请求、场景切换和节点释放；不能把 iOS 模拟成功当作真机原生能力成功。

原生 UI／Swift／OC 代码使用相应原生规范，Godot 场景保持引擎职责。Godot 游戏不强制新增 SceneDelegate 或 SwiftUI App 入口；iOS 生命周期能力由实际引擎模板和插件承担，必要修改按所选引擎版本实现。

## iOS 验收

按本次影响核对冷启动、后台／前台、系统中断、暂停恢复、音频、方向／Safe Area、触控、存档和原生回调。首次建立 iOS 支持或改变导出／插件链路时，检查最终 App 的有效 plist、权限、隐私清单与签名，并在目标设备运行。

无界面测试无法验证渲染、声音和设备交互。当前 stable 文档说明 iOS 模拟器只支持 Compatibility 渲染器，其他渲染路径应以适用设备验证；桌面顺畅也不能证明手机性能合格。

未拿到导出、Xcode 构建、安装或真机结果时逐项保留未验证。上传成功、平台处理完成、可分发和审核通过仍分别记录，不用 GitHub Release 替代 App Store 交付。

依据：[iOS 导出](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_ios.html)、[iOS 插件](https://docs.godotengine.org/en/stable/tutorials/platform/ios/ios_plugin.html)。
