# iOS 订阅与付费 UI

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/standards/ui-paywall.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

购买、订阅、试用或付费墙页面使用；通用 UI 规则见 [UI 规范](teamflow-ios-standards-ui.md)。验收时核对套餐、价格、周期、按钮与实际购买一致。

## 规则

- 【审核要求】购买前清晰说明获得的内容、订阅期限、价格和适用续订条件；试用说明时长和结束后的收费。不得制造虚假免费、倒计时或节省金额。以 App Review Guidelines 3.1.2 和官方订阅页面为依据。
- 【团队默认】购买按钮、选中套餐、产品 ID、周期、权益、展示价格、购买 API 参数必须来自同一个已验证产品模型。StoreKit 2 使用 `Product.displayPrice`；OC/StoreKit 1 使用产品价格及其 priceLocale 格式化。产品未加载成功时不能用占位价格发起购买。
- 年付折算月价只能作辅助说明，同时明确“按年收取的总金额”；币种、地区和舍入规则必须匹配。节省比例基于真实同币种可比价格计算。
- 首购优惠必须校验适用资格；无试用资格时更新 CTA 和说明。恢复购买、管理订阅、服务条款与隐私政策提供可访问入口；恢复中、取消、待批准、交易失败有独立反馈。
- 付款成功后只根据验证后的交易/权益状态解锁；关闭支付面板或点击按钮不等于成功。不能把 Sandbox 数据当线上价格证据。

## 官方来源

- [In-app purchase](https://developer.apple.com/design/human-interface-guidelines/in-app-purchase)
- [自动续期订阅](https://developer.apple.com/app-store/subscriptions/)
- [审核指南 3.1.2](https://developer.apple.com/app-store/review/guidelines/#subscriptions)
- [Product.displayPrice](https://developer.apple.com/documentation/storekit/product/displayprice)
