# AgentWorks 项目规则

本仓库保存供 Codex 和 Claude Code 共用的海外产品团队及可选本地运行器。用户目标是比较游戏和工具、用盈利证据选题、设计、评审、开发和运营。这里是两平台共用规则的唯一入口，不要求另行启动模型 CLI。

## 支持的平台
- 当前维护 Codex 和 Claude Code 两个平台，优先使用当前平台的原生子 Agent。
- Codex 读取本文件，角色来自 `.codex/agents/`；Claude Code 通过 `CLAUDE.md` 导入本文件，角色来自 `.claude/agents/`。
- 两套原生角色由同一个 `config/team.json` 自动生成；禁止分别维护业务规则。切换平台时沿用相同项目和数据目录。
- 技能快捷入口分别为 `$agentworks` 和 `/agentworks`；两者都进入 `docs/团队运行手册.md`，自然语言也可启动。

## 两类任务
- **维护 AgentWorks 本身**：修改系统代码或配置，按普通工程任务处理。不要启动市场调研或创建真实产品。
- **使用团队做产品**：读取 `docs/团队运行手册.md`，按当前项目和用户授权推进。优先使用宿主会话已有工具与子 Agent；主 Agent 负责汇总和落盘。没有子 Agent 时按角色顺序执行并说明不具备独立上下文，不能声称已做独立多 Agent 评审。单角色 worker 不再递归委派。

## 固定约定
- `config/team.json` 是角色唯一来源；全部角色按20年资深标准工作，这是能力框架，不能冒充真实履历。
- `roles/*.md` 是通用角色卡；`.codex/agents/` 和 `.claude/agents/` 是生成的宿主适配。只读当前任务需要的角色。规则、流程和数据不能因切换宿主而重建或分叉。
- AI 用户评审标记模拟；真实用户反馈、真实使用数据和收入分开记录且附来源。
- `config/workflows.json` 定义任务依赖和阶段验收；不得用未完成、失败或待修改结果绕过阶段条件。
- 进度、产物和运行日志在 `.agentworks/`；不要提交它们、密钥或个人数据。
- 读取项目简报、已完成交付和当前状态再续作；不要依赖聊天记忆。
- 对话协作使用 `packet` / `submit` 共用状态；只有选择外部 CLI 执行时才用 `run --execute --backend codex|claude`。缺少 Python 或文件工具时可以交付材料，但要明确尚未保存运行进度，不虚报已创建任务。
- 对外发送、投放和生产发布按用户已给的明确授权执行，未授权时先完成可审阅材料。
- 修改角色后执行 `python3 scripts/sync_agents.py`；修改运行器或流程后执行 `python3 -m unittest discover -s tests -v` 和 `python3 -m agentworks doctor`。
- 确保文档区分本地可复用能力、实际验证结果、未连接的外部工具和未部署的常驻服务。
