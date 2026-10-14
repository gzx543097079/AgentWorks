# 显式 App 外部动作

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/APP-RELEASE.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

本专题只在用户明确提出准备或执行某个 App 外部目标动作时加载。普通开发、需求完成、commit、push 或 GitHub Release 都不会触发本专题。目标动作依赖缺失的 Archive 或上传时可自动补齐最小必要前置，但不会继续执行目标之后的动作。

## 动作边界

| 用户表达 | 允许范围 |
| --- | --- |
| 检查/准备 TestFlight 或提审 | 只读核对并列出缺项，不 Archive、不上传、不提交 |
| Archive / 归档指定版本 | 生成并验证指定 Archive，不上传 |
| 上传 TestFlight | 上传指定 build，不自动分发测试员，也不启用 TestFlight Internal Only |
| 上传 TestFlight 并明确要求 Internal Only / 仅内部测试 | 上传指定 build，并将 `testFlightInternalTestingOnly` 设为 `true` |
| 分发 TestFlight | 将指定 build 分发到明确测试组 |
| 提交 Beta App Review | 只提交外部 TestFlight 测试审核 |
| 提交 App Store 审核 | 只提交指定版本和 build，不自动发布 |
| 发布 | 发布已审核的指定版本 |
| 开启或暂停分阶段发布 | 只执行明确的分阶段动作 |
| 下架 | 只处理明确 App 和地区的下架 |

用户可一次明确多个目标，例如“归档 build 123、上传 TestFlight 并分发给内部测试员”。如果只要求后面的目标，也可自动补齐确实缺失的必要前置；执行到目标即停止，不扩张到 Beta Review、App Store 审核或发布。前置所需目标 App、版本、build、账号或环境无法确定时先询问，不猜测。

`TestFlight Internal Only` 是可选上传参数，不是任何目标的必要前置，也不等于“分发给内部测试员”。启用后，该 build 不能用于外部 TestFlight 或 App Store。即使上传是目标或必要前置，只要没有另外明确要求 Internal Only，就必须省略 `testFlightInternalTestingOnly`，不能写成 `true`。

## 准备与记录

准备时直接读取实际工程、签名配置与平台状态，列出已核对事实和缺项，无需运行边界回显命令。TestFlight Internal Only 参数按上表处理。

### 隐私与广告检查

检查对象是本次目标 build 的有效配置和最终产物，不只看仓库里是否存在同名文件。记录检查结论与可定位依据；适用项未确认时列为缺项，不宣称发布准备完成。

1. **隐私清单**：检查 App 与所集成第三方 SDK 在最终产物中的 `PrivacyInfo.xcprivacy` 是否存在于适用位置、格式有效，数据收集、跟踪及必需原因 API 声明是否符合实际行为；核对 Xcode 汇总隐私报告及 App Store Connect 的 App 隐私信息。没有适用声明时说明判断依据，不为凑清单添加虚假条目。
2. **广告配置**：先确认是否展示广告、广告网络与归因方案。有使用 SKAdNetwork 归因的广告时，核对有效 `Info.plist` 中的 `SKAdNetworkItems`，其每项 `SKAdNetworkIdentifier` 与实际广告网络提供的 ID 一致；使用 AdMob 时另核对 `GADApplicationIdentifier` 为本 App 的 AdMob App ID。若请求 ATT 授权或访问 IDFA，再核对 `NSUserTrackingUsageDescription`、授权请求时机及用户拒绝后的行为。不要把 ATT 文案当作所有广告 App 的必填项。
3. **欧洲地区同意机制**：目标分发/服务地区包含欧洲经济区（EEA）或英国时，按实际数据处理和广告用途确认适用的 GDPR/英国 GDPR 告知与同意机制已接入；核对用户可拒绝、撤回或重新选择，且同意状态在相关 SDK 初始化、数据处理和广告请求前得到正确应用。使用 AdMob 在 EEA、英国或瑞士投放广告时，另核对符合 Google 要求的认证 CMP 与 TCF 接入及当地实际流程。仅有“GDPR 弹窗”或 SDK 依赖并不能证明流程生效；地区、账号配置和真实设备行为须分别核对。

依据：[Apple 隐私清单](https://developer.apple.com/documentation/bundleresources/adding-a-privacy-manifest-to-your-app-or-third-party-sdk)、[Apple SKAdNetworkItems](https://developer.apple.com/documentation/bundleresources/information-property-list/skadnetworkitems)、[Apple ATT 文案](https://developer.apple.com/documentation/bundleresources/information-property-list/nsusertrackingusagedescription)、[Google Mobile Ads iOS 配置](https://developers.google.com/admob/ios/quick-start)、[Google 欧洲地区 CMP 要求](https://support.google.com/admob/answer/13554020)。

实际动作使用项目既有 Xcode、CI 或发布工具。先核对目标 App、Bundle ID、版本、build、commit、环境、签名和账号；不得猜测目标。完成或失败后，在当前需求卡“决策与异常”追加一条含时区记录：动作、App/环境/版本/build、完整 commit、结果（失败、平台处理中、已完成）和可定位的平台或 CI 链接。处理中不能记为可分发；平台处理完成后再追加真实结果。只保存关键结果，不抄写长输出，也不预生成流水线。

重新构建会产生新的 build；旧 build 的安装、测试或审核结论不能自动沿用。审核通过不等于发布，上传成功不等于平台处理完成，GitHub Release 不等于 App Store 上线。
