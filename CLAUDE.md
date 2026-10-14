@AGENTS.md

## Claude 桌面端 Code 模式

在 Claude 桌面端选择 Code 模式及本地仓库，使用上面导入的共用规则。
本仓库技能为 `/agentworks`，原生子 Agent 在 `.claude/agents/agentworks-*.md`。
使用当前桌面会话的子 Agent、浏览器、文件和代码工具完成任务；不要另行启动模型命令行。
项目状态由 `agentworks.desktop.Workspace` 保存，调用说明在 `docs/桌面内部接口.md`；用户无需操作终端。
如果技能或固定角色未加载，读取 `docs/团队运行手册.md`，给当前平台的通用子 Agent 传入完整任务包。
