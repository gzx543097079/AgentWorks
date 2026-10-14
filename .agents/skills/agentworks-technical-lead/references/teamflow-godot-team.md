# 团队协作

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/Godot/references/TEAM.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

多人同时修改场景、资源、引擎配置或导出设置时使用。通用分支与提交边界见[共用边界](../../agentworks-director/references/teamflow-core-boundaries.md)。

## 引擎版本锁定

同一项目的成员使用同一个 Godot 版本。版本不一致时，编辑器会改写 `.tscn`、`.tres`、`.import` 和 `project.godot`，产生与需求无关的差异与冲突。

在 Git 根的 `.agents/team/toolchain.json` 锁定版本，值取 `godot --version` 中 `.stable` 之前的部分：

```json
{"godot": "4.7.2"}
```

`doctor` 在 Godot 模式核对本机引擎；`verify_godot.py` 未传 `--expect-version` 时沿用锁定值。升级引擎单独建需求卡：一次改锁定值并重新导入，统一提交生成的变更，不和功能改动混在一起。工具不安装或切换引擎。

## 场景拆分与归属

- 一个场景同一时间只由一人负责修改。需要并行时，先把受影响部分拆成独立子场景或 Resource，再各自修改。
- 大场景按区域、UI 面板或可复用角色拆分，用实例组合，不把整个关卡或界面放在一个 `.tscn` 中。
- 共享 Resource（主题、平衡数据、输入映射）需要明确的维护人；改动写入需求卡范围，并在 AC 中写明受影响的场景。
- `project.godot` 的输入映射、Autoload 和渲染设置属于横切配置，改动时在模块索引的 `cross_cutting_paths` 中登记，并告知团队。

## 冲突处理

- `.tscn` 和 `.tres` 是文本，但 `ext_resource` 编号、`uid://` 和节点顺序之间有引用关系。逐行合并后，Godot 可能静默丢失节点或引用。
- 遇到冲突，优先保留一方版本，再在编辑器中手动补上另一方的改动；必须文本合并时，合并后由 Godot 实际加载场景，检查引用、UID 与节点结构，不能只看文本冲突标记已经消除。
- 冲突中的 `.import` 与 `.uid` 不要手动拼接：保留一方，再由编辑器重新导入。不要删除 `.uid` 来“解决”冲突，删除会改变其他场景的引用。
- 解决冲突后运行项目的 Godot 检查 profile；包含视觉变化的场景保留人工 AC。

## 导出配置与凭据

- `export_presets.cfg` 保存导出预设，可以提交，用于团队复现导出。Godot 4.1 起，签名密码、密钥库口令等敏感项保存在 `.godot/export_credentials.cfg`，随 `.godot/` 一起忽略。
- 证书、描述文件、密钥库、API Key 不提交，也不写进需求卡；需要共享时使用团队已有的密钥管理方式。旧版本工程若把凭据写进 `export_presets.cfg`，先移出再提交。
- Godot 模式的 setup 会在 `.gitignore` 加入 `.godot/`；游戏位于子目录、有自己的 `.gitignore` 时同样有效。`doctor` 报告未忽略缓存的游戏根。
