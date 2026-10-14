# SwiftUI 代码规范

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/standards/swiftui.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

SwiftUI 是 Swift UI 框架，执行本文件前先执行 Swift 与 UI 规范。依据 [Apple：管理模型数据](https://developer.apple.com/documentation/swiftui/managing-model-data-in-your-app)。

- `body` 描述 UI，不做网络请求、写存储、创建重复订阅或打业务点。按职责提取视图，尺寸由内容、容器和系统布局决定，不以固定文件行数强制拆分。
- 先确认部署目标。Observation 在支持的系统上使用 @Observable；视图拥有的可观察实例可用 @State，需要双向投影时用 @Bindable。旧 ObservableObject：本视图创建并拥有用 @StateObject，外部注入用 @ObservedObject；不要因 body 重算反复创建状态对象。
- @State 表达本地状态，@Binding 表达外部状态连接，环境用于合适的共享依赖。保持单一事实来源，不复制多份选中订阅/价格状态。
- List/ForEach 使用稳定业务 ID，不在渲染时生成 UUID，不用会随增删变化的索引代表身份；navigation、sheet、alert 用明确状态避免多处竞争。
- `.task(id:)` 适合与视图生命周期绑定的异步工作；处理取消、重复进入和过期结果，不把取消当业务错误提示。非结构化长期 Task 由明确 owner 取消。
- `.onAppear` 可能多次执行，曝光事件按埋点定义去重，购买成功事件在交易验证后产生；不要在 body 中打点。
- 可点击动作优先 Button / NavigationLink，而非只有 onTapGesture 的视觉元素；补齐 VoiceOver 标签、选中状态、热区和字号适配。
- 避免无理由 AnyView、巨大 GeometryReader 和高频全树状态更新；性能问题先用测量定位。动画响应减少动态效果。
- UIViewRepresentable / UIViewControllerRepresentable 明确 Coordinator 所有权、update 幂等性与 dismantle 清理；不在更新回调中制造状态循环。
- Preview、mock 数据放预览或测试范围，检查 Release 的 target membership 和构建条件；不要删掉正常测试，只清除误入生产的调试入口。
- 验证实际交互、导航、列表身份、重新进入、取消、常规动态字号和深浅色。超大字号按 UI 规范的测试范围处理。Preview 可辅助验证，不能代替运行和必要测试。
