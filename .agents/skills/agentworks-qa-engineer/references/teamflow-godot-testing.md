# Godot 测试脚本

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/Godot/references/TESTING.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

新建或扩充测试、引入测试框架时加载；检查入口与证据见 [Godot 验证](teamflow-godot-checks.md)。

没有既有测试框架时，先用无依赖的入口脚本，不需要安装插件：

```gdscript
extends SceneTree

var failures := 0

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var main: Node = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	await process_frame
	check(main.score == 0, "开局分数为 0")
	main.queue_free()
	quit(1 if failures > 0 else 0)

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error("失败：" + message)
```

用例加载真实场景、发出输入或信号、等待 `process_frame` 后断言。类型无法推断的变量（如取自无类型节点的属性）显式标注类型，否则整份脚本解析失败。故意触发引擎错误的用例（如损坏存档）按 [Godot 验证](teamflow-godot-checks.md#可复用检查入口) 用 `--allow-error` 放行。

用例增多或需要替身、参数化、报告时再引入框架，沿用项目已有选择：

- GUT：把 `addons/gut` 提交到工程，在游戏根放 `.gutconfig.json`（写明测试目录并启用测试结束后退出），检查入口传 `--test-script addons/gut/gut_cmdln.gd`。
- gdUnit4：使用其自带的命令行运行器，在 profile 中直接配置该命令的 argv。

引入框架属于新增依赖，按[依赖与工具链](../../agentworks-technical-lead/references/teamflow-core-dependencies.md)锁定版本。首次接入时加一个故意失败的用例，确认检查判为失败后再删除，以证明退出码和错误输出能传到 TeamFlow。
