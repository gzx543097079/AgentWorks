# 依赖与工具链

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/teamflow-core/references/DEPENDENCIES.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

新增、升级或移除第三方库、引擎插件、SDK，或调整 Xcode、Godot 版本时加载。主流程见 [WORKFLOW](../../agentworks-director/references/teamflow-core-workflow.md)。

## 新增与移除

- 先确认已有代码、系统框架或已集成依赖无法满足，再引入新依赖；把选择理由写入需求卡“决策与异常”。
- 核对许可证、维护状态、最低系统版本、包体影响，以及 SDK 的隐私清单、数据收集和网络行为；涉及广告、统计或支付时按当前模式 Skill 的发布专题核对。
- 沿用工程已有的包管理方式（Swift Package Manager、CocoaPods、Carthage 或 Godot `addons/`），不为新增一个依赖迁移包管理器。
- 移除依赖时一并清理引用、资源、构建设置和锁文件条目，并跑覆盖相关功能的检查。

## 锁定与升级

- 锁文件随代码提交：`Package.resolved`、`Podfile.lock`、`Cartfile.resolved`；Godot 插件提交 `addons/` 下的实际源码，在插件目录或需求卡记录来源与版本。
- 版本约束写到能复现的程度（精确版本或明确上限），不使用浮动分支或 `latest`。
- 依赖或工具链升级单独建卡，不与功能改动混在一个提交；卡片写明旧版本、新版本、变更说明中的破坏性项和受影响模块，升级后跑完整的适用 profile。
- 团队在 `.agents/team/toolchain.json` 锁定工具链，值取版本号本身：

```json
{"xcode": "16.4", "godot": "4.7.2"}
```

`doctor` 在相应模式核对本机版本，不一致记为需处理；工具不安装或切换 Xcode、Godot。升级锁定值与重新生成的工程差异放在同一个单独的升级提交中。

## 安全

依赖源只用官方或团队既有私有源；凭据按 [BOUNDARIES](../../agentworks-director/references/teamflow-core-boundaries.md) 处理，不写入 Podfile、Package.swift 或插件配置。安装脚本、构建阶段脚本和插件的导出钩子属于可执行代码，引入或变更时核对其实际行为。
