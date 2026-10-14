# Godot 验证与证据

> 来源：TeamFlow `teamflow-v1.0.0`，提交 `e2088f01b7834ca1cf7217004309fe0cb22ee3bc`，原文件 `.agents/skills/Godot/references/CHECKS.md`。保留专业规范并调整资源链接；文中的 TeamFlow 专属命令/路径仅适用于已安装原工具的业务工程，不能据此声称当前仓库已安装它们。 用户当前目标、平台和既有授权优先；版本号及商店/地区规则在实际执行时重新核对。

沿用[共用验证和证据机制](teamflow-core-checks.md)。profile 名称由项目配置决定；不增加独立状态表。

## 检查选择

| 变化 | 验证 |
| --- | --- |
| 脚本、场景和资源 | 资源导入／加载 + 受影响的逻辑或场景测试 |
| 输入、UI、渲染、动画和声音 | 上述检查 + 有画面的实际运行及受影响操作 |
| 性能或加载 | 按[性能与稳定性](teamflow-godot-performance.md)在目标设备测量并记录前后结果 |
| 导出预设或原生插件 | Godot 检查 + iOS 导出与 Xcode 构建 + 适用真机场景 |
| 发布 | 目标最终产物核对、必要设备验证及明确外部动作 |

`--headless --editor --import` 只证明导入检查，不能当作玩法、视觉或 iOS 验收。测试脚本由项目维护，失败须显式 `quit(1)`；捕获引擎错误，即使进程退出 0 也不能标通过。退出超时按失败处理，不无限等待。

## 可复用检查入口

[verify_godot.py](../scripts/verify_godot.py) 接受实际游戏根与项目测试脚本，执行导入和测试。默认查找 PATH 中 godot／godot4 或 macOS 既有 Godot 安装；可传 `--godot` 指定已有可执行文件。不安装引擎或插件。

```sh
python3 <QA技能目录>/scripts/verify_godot.py \
  --project game --test-script tests/run_tests.gd
```

测试故意触发的引擎错误（如损坏存档的解析错误）用 `--allow-error 正则` 逐条放行，只作用于测试阶段且只匹配该行，其他错误仍判失败。测试脚本相对游戏资源根，必须存在，写法与框架选择见[测试脚本](teamflow-godot-testing.md)；只有明确选择 `--import-only` 才单独检查导入。日志写入游戏根 `.godot/teamflow-checks/`；这类缓存不提交，TeamFlow profile 的完整输出另由核心保存。工具不伪造不存在的项目测试。

默认读取 `project.godot` 的 `config/features` 主次版本：引擎须同主版本且次版本不低于工程，升级引擎不失败。需要固定精确版本时传 `--expect-version`（如 `4.7.2`），或由团队在 `.agents/team/toolchain.json` 锁定（见[团队协作](../../agentworks-technical-lead/references/teamflow-godot-team.md)），不一致即失败；显式参数优先。每个阶段默认最多 120 秒，可用 `--timeout` 按实际项目调整。

[配置示例](https://github.com/gzx543097079/iOS_TeamFlow/blob/e2088f01b7834ca1cf7217004309fe0cb22ee3bc/.agents/skills/Godot/assets/project-checks.example.json) 假定游戏位于 `game/`，并已有 `game/tests/run_tests.gd`。先按实际结构修改，再合并进已有 `.agents/project-checks.json`；不覆盖原 profile。输入必须覆盖脚本、场景、资源、导入配置、导出预设和原生插件的实际源码。将 `.godot/` 加入项目 `.gitignore`，保留持久 UID 与源资源。

iOS 构建 profile 必须运行真实导出和构建脚本，可通过 `extends` 包含游戏检查；尚未配置就记未验证，不能用空命令代替。混合原生／Godot 改动使用覆盖两部分的组合 profile。人工视觉、设备或平台条件保持未勾选，等待真实证据后确认。

依据：[官方命令行参考](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)。
