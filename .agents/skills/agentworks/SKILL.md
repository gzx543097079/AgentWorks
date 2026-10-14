---
name: agentworks
description: 在 Codex 或 Claude Code 中使用 AgentWorks 海外产品团队，比较游戏和工具机会，进行需求、设计评审、开发验收和运营迭代，保存进度并跨会话、跨平台续作。用于实际运行团队，不用于修改 AgentWorks 系统本身。
---

# AgentWorks 团队

先读 [团队运行手册](../../../docs/团队运行手册.md)，以仓库根目录为工作目录。该手册是 Codex 和 Claude Code 共用的流程来源。

读取项目状态、简报与记忆后推进；优先使用当前平台的工具和原生子 Agent，通过 `packet` / `submit` 保存交付。Codex 和 Claude Code 读取同一个 `config/team.json` 及工作流，切换平台时沿用相同项目和数据目录，不默认嵌套启动另一个模型 CLI。

单角色执行者只处理分配任务；总控按依赖调度、汇总并落盘。不支持子 Agent 的环境采用明确标注的顺序角色模式。三个模拟用户的评审不能冒充真人验证。

需要命令详情时读 [使用指南](../../../docs/使用指南.md)，处理产品决策和验收时读 [协作约定](../../../docs/协作约定.md)。
