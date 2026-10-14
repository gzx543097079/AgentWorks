# Godot 性能与稳定性

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/Godot/references/PERFORMANCE.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

需求 AC 含帧率、内存或加载时间目标，或改动触及渲染、粒子、物理、大量节点、资源加载、存档读写，或修复崩溃、卡死、泄漏时加载。证据机制见 [Godot 验证](teamflow-godot-checks.md)。

## 测量方法

- 在目标设备上用导出的 Release 构建测量，渲染器与发布一致；编辑器内运行、桌面结果和无界面运行都不能证明手机性能。
- 固定场景、操作脚本、时长和数据量，改动前后各测至少 3 次取中位数；记录设备、系统、引擎版本、渲染器和构建模式。
- 帧时间记录平均值和尖峰（如 95 百分位或最差帧），不只报平均 FPS。项目已有基线或 AC 目标时按其判断；都没有时把本次结果记为基线，只说明变化量。

| 关注点 | 工具 |
| --- | --- |
| 帧时间、脚本与物理耗时 | 编辑器调试器的 Profiler 与 Monitors；`Performance.get_monitor()` 读取 `TIME_PROCESS`、`TIME_PHYSICS_PROCESS` |
| 绘制与显存 | `RENDER_TOTAL_DRAW_CALLS_IN_FRAME`、`RENDER_VIDEO_MEM_USED`；Visual Profiler |
| 内存与泄漏 | `MEMORY_STATIC`、`OBJECT_ORPHAN_NODE_COUNT`；`Node.print_orphan_nodes()` |
| 加载时间 | 在加载前后记录 `Time.get_ticks_msec()`，或使用 `ResourceLoader` 线程加载的进度 |
| iOS 原生层 | 按 iOS 模式的性能专题使用 Instruments |

## 崩溃与稳定性

- GDScript 运行错误、引擎错误输出和断言失败都算失败，即使进程退出码为 0。
- 原生崩溃先取设备日志与符号，区分引擎、插件和原生代码；记录复现条件、引擎版本和导出模板版本。
- 场景切换、重开和长时间运行后检查孤立节点数量不持续增长；信号、计时器和异步任务在节点释放后不再回调。
- 修复后在同样条件下复测，一次没复现不等于已修复。

把测量条件、前后数值和工具来源写入需求 AC 的证据；未在目标设备测量的保留未验证。

依据：[Godot 性能概述](https://docs.godotengine.org/en/stable/tutorials/performance/index.html)、[Performance 单例](https://docs.godotengine.org/en/stable/classes/class_performance.html)。
