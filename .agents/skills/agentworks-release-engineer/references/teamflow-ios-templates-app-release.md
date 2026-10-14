# App 发布动作：版本 / build

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/templates/app-release.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

此文件只在用户明确要求某个 App 外部动作后创建。不要预生成全部阶段或把未授权动作写成待执行计划。

- App / Bundle ID / 环境：待填写
- 版本 / build：待填写
- commit：待填写

准备阶段按 [App 外部动作](teamflow-ios-app-release.md#隐私与广告检查) 核对本次 build 的隐私清单、适用的广告 `Info.plist` 键和欧洲地区同意机制；在实际发布记录中写入已核对结论或缺项。

## 已执行动作

每次只追加用户目标授权范围内且已实际执行的动作：时间、动作、对象、结果（失败／处理中／完成）和证据。目标授权包含确实缺失的必要前置，不包含后续或可选动作；具体边界遵循 [App 外部动作](teamflow-ios-app-release.md)。

TestFlight Internal Only 需要单独明确授权。普通 TestFlight 上传默认省略 `testFlightInternalTestingOnly`；不能根据“内部测试员”或“内部测试组”自行推断启用。

本模板只提示需要核对的事实；动作结果记在当前需求卡“决策与异常”，不另填模板副本。
