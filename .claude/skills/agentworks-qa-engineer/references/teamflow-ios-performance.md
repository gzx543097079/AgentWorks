# iOS 性能与稳定性

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/iOS/references/PERFORMANCE.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

需求 AC 含性能指标，或改动触及启动路径、列表滚动、图片与媒体、大量计算、缓存、后台任务，或修复崩溃、卡死、内存问题时加载。证据机制见[核心验证](teamflow-core-checks.md)。

## 测量方法

- 用 Release 配置在真机测量；模拟器和 Debug 构建的数字不作为性能证据。
- 改动前后在同一设备、系统、数据量和网络条件下各测至少 3 次，取中位数；记录设备、系统版本、构建配置和次数。
- 项目已有基线或 AC 给出目标时按其判断；都没有时把本次结果记为基线，只说明变化量，不宣称“达标”。

| 关注点 | 工具 |
| --- | --- |
| 冷启动到首帧 | Instruments App Launch；XCTest `measure(metrics: [XCTApplicationLaunchMetric()])` |
| 滚动卡顿与掉帧 | Instruments Animation Hitches；`XCTOSSignpostMetric` 滚动指标 |
| 内存占用与泄漏 | Memory Graph、Allocations、Leaks；`XCTMemoryMetric` |
| CPU 与主线程阻塞 | Time Profiler；Thread Performance Checker、Main Thread Checker |
| 线上表现 | 项目已接入的 MetricKit、Xcode Organizer 或崩溃平台数据 |

## 崩溃与稳定性

- 先拿到符号化的崩溃日志（匹配构建的 dSYM），确定异常类型、崩溃线程和调用栈，再定位根因；缺陷卡记录复现条件与日志定位。
- 能复现时先保留失败证据；能写回归测试的补测试。修复后在同样条件下复测，一次没复现不等于已修复。
- 内存与并发问题按需开启 Address Sanitizer、Thread Sanitizer 或 Zombie Objects 复现；这些开关不进入 Release 配置。
- 卡死与主线程阻塞看 Time Profiler 中的主线程调用栈和系统看门狗日志，不以加长超时掩盖。

把测量条件、前后数值和工具来源写入需求 AC 的证据；未在真机测量的保留未验证。
