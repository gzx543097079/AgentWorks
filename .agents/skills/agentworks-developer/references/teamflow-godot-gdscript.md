# GDScript 实施

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/Godot/references/GDSCRIPT.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

沿用工程已有约定。新的脚本按职责命名，关键输入、返回值和成员状态使用明确类型；不为满足形式增加空抽象。中文注释解释状态约束、算法取舍与平台边界，不复述赋值和分支。

- 核对 Node 的 `_ready`、`_process`、`_physics_process` 与释放时机；离树、重入和场景切换不重复订阅信号或留下任务。
- 通过实际 Input Map 动作处理玩法输入，界面事件区分已消费输入；触控、键盘、手柄按本次目标核对，不把桌面鼠标测试当作 iOS 触控证据。
- 信号和公开方法表达明确意图；避免遍历场景树搜索全局状态、硬编码深层路径或用 Autoload 隐藏模块依赖。
- 解析与资源加载失败显式返回错误或按约定降级；不将空值、缺资源或解析错误静默变成成功。
- 验证脚本必须在失败时返回非零退出码；不要依赖 `assert` 在所有构建中均有效。检查场景应能独立加载和退出，不启动真实支付、广告请求或生产服务。

语法和 API 以实际引擎版本为准：[GDScript 官方参考](https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html)。
