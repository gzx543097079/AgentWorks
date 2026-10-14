@AGENTS.md

## Claude Code 入口

使用上面导入的通用规则，不维护另一套团队流程。
本仓库技能为 `/agentworks`，固定子 Agent 在 `.claude/agents/agentworks-*.md`。
优先使用当前会话的原生子 Agent 和工具，通过任务包及结构化交付保存进度。
不要为了使用团队在 Claude Code 内再嵌套启动 Claude CLI；外部运行器是从终端独立启动的可选方式。
如果技能或固定角色未加载，直接读 `docs/团队运行手册.md` 和需要的 `roles/*.md`。
