# 工程与玩法

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/Godot/references/ENGINE.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

先核对实际 Godot 版本、GDScript／其他语言、2D／3D、渲染器、目标设备、入口场景、插件与项目根。新游戏只询问影响实现且尚无法推断的玩法、方向或目标设备，不为普通功能重写完整策划案。普通功能直接续接需求卡。

## 职责与资源

- 沿用现有场景组织。场景负责局部节点生命周期和输入／展示，玩法规则及存档状态有明确所有者。Node、Resource、RefCounted 按生命周期选择，不强制 MVVM。
- 跨场景通过明确接口、信号或数据协作，避免深层节点路径和相互修改内部状态。Autoload 只承担实际需要跨场景存续的能力，不把所有功能集中到 GameManager。
- Resource 若被多个场景共享，先确认是否允许共同修改；独立实例状态应显式复制或另设所有者，避免编辑一个角色影响全部角色。
- 修改 `.tscn`、`.tres`、脚本或资源路径时核对真实引用、UID、导入结果及加载；文本引用无命中不能单独证明资源无人使用。优先利用项目已有编辑器工具，文本修改后必须由 Godot 实际加载。
- 源资源、导入配置和引擎生成的持久 UID 按所选版本纳入版本控制；Godot 4.1+ 的 `.godot/` 缓存不提交。不要统一忽略 `.uid`、`.import` 或整个 `addons/`。大资源是否使用 LFS 按已有约定处理，不自动迁移 Git 历史。

通用职责、依赖和复用原则遵循[共用架构规则](../../agentworks-technical-lead/references/teamflow-core-architecture.md)。Godot 的具体场景、节点和资源职责按本文件处理。

## 游戏 UI 与行为

Control／Container 管理游戏界面；按实际方向、窗口尺寸和设备核对布局、字体、触控区域、Safe Area 与遮挡。Godot 的场景树 Scene 与 iOS UIWindowScene 不是同一概念。

本次涉及玩法时把适用条件写入 AC：输入动作、多点触控、暂停与恢复、胜负／重开、场景切换、重复操作、存档升级和加载失败。帧循环和物理循环按引擎职责区分，时间相关逻辑使用实际 delta；动画结束、延迟调用和异步结果不得修改已释放节点。

本地化共用[文案原则](../../agentworks-localization-specialist/references/teamflow-core-localization.md)，实际使用 Godot 的翻译资源与 API，不生成原生 String Catalog 代替游戏翻译。Godot 日志使用项目既有输出方式，原生插件沿用原生日志；共用脱敏要求，不将 TFLogger 直接写入 GDScript。

涉及持久化数据变化时使用[共用迁移原则](../../agentworks-technical-lead/references/teamflow-core-architecture.md#数据迁移与恢复)，以旧版存档的真实或项目内合成样本验证，不以重装清空存档证明升级成功。

依据：[Godot 场景组织](https://docs.godotengine.org/en/stable/tutorials/best_practices/scene_organization.html)、[版本控制](https://docs.godotengine.org/en/stable/tutorials/best_practices/version_control_systems.html)。实施时查询与锁定引擎版本相符的文档。
