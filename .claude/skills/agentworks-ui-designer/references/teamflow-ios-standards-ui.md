# iOS UI 规范（中文）

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/standards/ui.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

适用于 UIKit（OC / Swift）和 SwiftUI。
本规范是基于 Apple 官方资料编写的团队落地标准，不是 Apple 认证文件。区分“审核要求”“Apple 设计建议”“团队默认”；上线前再次核对目标地区、系统版本及最新官方规则。

新增或修改输入框、搜索、表单或输入栏时另读[键盘与输入](teamflow-ios-standards-ui-keyboard.md)；购买、订阅或付费墙页面另读[付费 UI](teamflow-ios-standards-ui-paywall.md)。其他 UI 改动只读本文件。

## 1. 设计基线

- 【Apple 设计建议】优先系统导航、列表、表单、弹窗、菜单、分享和购买组件，遵循所在系统的交互及外观；尊重安全区域、键盘、手势返回和辅助功能。
- 【团队默认】先明确页面目标、主要动作和导航路径，再设计视觉。每页提供内容、加载、空、失败、权限不足等实际适用状态；失败提供重试或恢复入口。
- 【团队默认】先采用系统语义颜色、文字样式和组件默认尺寸。自定义间距可从 4/8/12/16/24/32 pt 取值，但这是项目约定，不是 Apple 强制栅格。设计变量集中管理，避免散落魔法数字。
- 【团队默认】不强制特定 iOS 最低版本；先读取工程部署目标。新系统材质（包括 Liquid Glass）优先用系统组件，使用新 API 时核对可用性并提供必要回退，不把新系统外观强加给旧系统。

## 2. 排版、颜色和适配

- 【Apple 设计建议】使用 Dynamic Type，优先 `.body`、`.headline` 等语义样式；UIKit 用 preferredFont 并启用字体缩放。重要信息在大字号下可换行、滚动，不能截掉价格、购买条件或主操作。
- 【Apple 设计建议】iOS 自定义文字参考默认 17 pt、最小 11 pt；它们不是所有标签必须使用的固定字号。团队避免用最小字号承载购买条件等关键信息。
- 【团队默认】正常正文采用至少 4.5:1 对比度，大字至少 3:1；以 Apple Accessibility 当前尺寸/字重分类及 Accessibility Inspector 实测为准。同时检查深色、浅色、增强对比度和透明背景。
- 【Apple 设计建议】状态同时用文字、图形或形状表达，不只用红绿区分；图片配适当替代说明，纯装饰图不制造朗读噪音。
- 【团队默认】触控热区至少 44×44 pt，图标可小于热区。Apple 当前可访问性文档区分 iOS 默认 44×44 pt 和最小 28×28 pt；本团队采用更宽松易点的 44 pt，不宣称它是所有场景的审核硬门槛。相邻热区避免重叠。
- 支持横竖屏和 iPad 的范围以需求确认结果为准；所支持设备必须验证安全区域、窗口尺寸变化、长文案、RTL 和键盘遮挡。不要用屏幕宽度推算所有布局。

## 3. 操作与无障碍

- 所有用户可见文本和无障碍文本遵守 [多语言文本生成规则](../../agentworks-localization-specialist/references/teamflow-core-localization.md)与 [iOS 本地化](../../agentworks-localization-specialist/references/teamflow-ios-localization.md)，通过按场景确定层级的点分键从本地化资源读取；布局验证覆盖非开发语言和长文案。
- 按钮说明实际动作，破坏性操作说明后果；有可恢复设计时优先提供撤销。不要阻断系统返回手势或隐藏必要退出路径。
- VoiceOver 验证名称、值、特征、顺序和焦点；滑动等手势有可发现的等效控件。自定义组件支持辅助功能动作。
- 尊重减少动态效果、降低透明度和增强对比度；不要只用声音传达结果。加载期间避免重复提交，加载与失败必须可区分。
- 输入框提供标签、正确键盘类型、焦点切换、校验时机、错误原因；不以 placeholder 代替永久标签。

## 4. UI 验收记录

对本次涉及页面核对设备/系统、语言、字号、主题、操作及结果；省略不涉及的维度。下面的表仅作检查提示，不要求另填一份；实际结论与证据统一在需求卡引用。

【团队默认截图范围】视觉检查仅截取本次改动涉及的关键页面和必要状态：优先覆盖直接修改的页面、核心操作结果，以及受影响的错误、空态或键盘遮挡状态。共享组件选择具有代表性的使用页面，不逐页重复截图；页面及状态未变化时复用已有有效截图。设备、语言、主题等仅在本次改动影响或已确认验收要求涉及时增加截图，不默认展开全量组合。

截图作为视觉证据，交互、焦点、提交和恢复行为仍通过实际操作或测试确认；不为每个操作步骤单独截图。只有实际发现问题、影响范围扩大或用户明确要求时扩大截图范围。

【团队默认测试范围】无明确要求时不验证超大字号（辅助功能的更大字体档位）。只有用户明确要求或已确认需求/验收标准列入时才测试；普通字号与常规字号适配仍按本次改动验证。未要求的超大字号无需填写记录。本约定不改变 Dynamic Type 与现有字号适配的实现建议。

涉及输入时另按[键盘与输入](teamflow-ios-standards-ui-keyboard.md#输入验收)核对。

| 检查项 | 通过 / 失败 / 未验证 / 不适用 | 证据 |
| --- | --- | --- |
| 主路径及加载、空、错误状态 | | |
| 普通字号与常规字号适配 | | |
| 超大字号（仅明确要求时） | | |
| 深浅色 / 对比度 | | |
| VoiceOver / 热区 / 减少动态效果 | | |
| 小屏 / 支持的 iPad / 键盘 / 长文案 | | |
| 付费页（仅涉及时，见[付费 UI](teamflow-ios-standards-ui-paywall.md)） | | |

## 官方来源

- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines)
- [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- [Typography](https://developer.apple.com/design/human-interface-guidelines/typography)

HIG 页面若仅显示 JavaScript 提示，可读取 Apple 自有 DocC 数据路径 `https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<主题>.json`。
