"""Embed AgentWorks into a product repository; that repository becomes the product workspace."""
import hashlib
import json
import subprocess
from pathlib import Path

from .core import EMBEDDED, ROOT, WorksError, now

ENGINE = ".agentworks/engine"
MANIFEST = ENGINE + "/install.json"
START, END = "<!-- agentworks:start -->", "<!-- agentworks:end -->"
GITIGNORE = [
    "# agentworks:start",
    ".agentworks/locks/",
    ".agentworks/**/*.tmp",
    ".agentworks/engine/**/__pycache__/",
    "# 真实用户资料默认不提交",
    ".agentworks/projects/*/input/*",
    "!.agentworks/projects/*/input/README.md",
    "!.agentworks/state.sqlite3",
    "# agentworks:end",
]
RULES = """{start}
## AgentWorks 产品团队

本仓库内嵌 AgentWorks（来源提交 {commit}），本仓库就是产品工作区。用户通过聊天运行海外产品团队，使用当前桌面会话的原生子 Agent 和工具，不另行启动模型命令行，不要求用户操作终端。

- 运行团队先读技能 `agentworks`（Codex `$agentworks`，Claude `/agentworks`）和 `.agentworks/engine/docs/团队运行手册.md`。原生角色名称以 `agentworks-` 开头，位于 `.codex/agents/` 与 `.claude/agents/`。
- 手册中的 `config/`、`docs/`、`roles/` 在本仓库位于 `.agentworks/engine/` 下；技能位于 `.agents/skills/`（Claude 为 `.claude/skills/`）。
- 进度接口：在仓库根目录运行 Python，先 `sys.path.insert(0, ".agentworks/engine")`，再 `from agentworks.desktop import Workspace; team = Workspace()`，用法见 `.agentworks/engine/docs/桌面内部接口.md`。本仓库只绑定一个项目，开始前先 `team.status()`。
- 产品文件写在 `design/`、`app/`。简报、记忆、输入资料、任务包、交付报告和状态库都在 `.agentworks/`，随本仓库保存；`input/` 中的真实用户资料默认不提交。
- 全部角色按20年资深从业者标准工作，这是专业判断框架，不能冒充真实履历。AI 用户评审标记模拟；真实用户反馈、使用数据和收入分开记录并附来源。
- 工作流依赖和阶段验收不能绕过。分配前 `begin` 登记，完成后用该次 ticket `complete`；可写任务独占批次，独立只读任务可并行。
- 对外消息、投放、付费和生产发布按用户明确授权执行。
- `.agentworks/engine/`、`agentworks*` 技能与角色文件由安装程序管理，不手改；升级时从 AgentWorks 源仓库重新安装到本仓库。
{end}
"""


def digest(content):
    return hashlib.sha256(content).hexdigest()


def localize(content):
    """Point copied text at the engine folder instead of the source repository root."""
    text = content.decode("utf-8")
    text = text.replace("../../../docs/", "../../../" + ENGINE + "/docs/")
    text = text.replace("config/result.schema.json", ENGINE + "/config/result.schema.json")
    return text.encode("utf-8")


def payload(source):
    from scripts.sync_agents import generated
    files = {}
    for folder, pattern in (("agentworks", "*.py"), ("config", "*.json"), ("docs", "*.md")):
        for path in sorted((source / folder).glob(pattern)):
            files[ENGINE + "/" + folder + "/" + path.name] = path.read_bytes()
    for name, content in generated(source):
        if name.startswith("roles/"):
            files[ENGINE + "/" + name] = content
        elif name.startswith((".codex/agents/", ".claude/agents/", ".claude/skills/")):
            files[name] = localize(content) if name.endswith((".md", ".toml")) else content
    for folder in sorted((source / ".agents/skills").glob("agentworks*")):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                name = ".agents/skills/" + path.relative_to(source / ".agents/skills").as_posix()
                files[name] = localize(path.read_bytes()) if path.suffix == ".md" else path.read_bytes()
    return files


def target(project, name):
    path = project / name
    if any(p.is_symlink() for p in [path, *path.parents] if p == project or project in p.parents):
        raise WorksError("安装目标不能为符号链接：" + name)
    if path.exists() and not path.is_file():
        raise WorksError("安装目标不是普通文件：" + name)
    return path


def block(text, start, end, body):
    """Replace or append a marked block, keeping the user's own content."""
    if start in text and end in text:
        head, rest = text.split(start, 1)
        return head + body.rstrip("\n") + rest.split(end, 1)[1]
    return text + ("\n" if text and not text.endswith("\n") else "") + ("\n" if text else "") + body


def install(project, source=ROOT):
    if EMBEDDED:
        raise WorksError("请从 AgentWorks 源仓库执行安装，内嵌副本不能再安装到其他仓库。")
    project, source = Path(project).expanduser().resolve(), Path(source).resolve()
    if not project.is_dir():
        raise WorksError("产品仓库文件夹不存在：" + str(project))
    if project == source or source in project.parents or project in source.parents:
        raise WorksError("产品仓库不能是 AgentWorks 源仓库本身，也不能与其互相包含。")
    files = payload(source)
    manifest = target(project, MANIFEST)
    previous = json.loads(manifest.read_text(encoding="utf-8"))["files"] if manifest.exists() else {}
    # Check every collision before writing so a refused install leaves no partial copy.
    for name, content in files.items():
        path = target(project, name)
        if path.exists() and name not in previous and path.read_bytes() != content:
            raise WorksError("产品仓库已有同名文件，未安装任何内容：" + name)
    changed = []
    for name, content in files.items():
        path = target(project, name)
        if not path.exists() or path.read_bytes() != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            changed.append(name)
    for name in sorted(set(previous) - set(files)):
        path = target(project, name)
        if path.exists() and digest(path.read_bytes()) == previous[name]:
            path.unlink()
            changed.append(name + "（已移除）")
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    for name, start, end, body in (
        ("AGENTS.md", START, END, RULES.format(start=START, end=END, commit=commit)),
        ("CLAUDE.md", START, END, START + "\n@AGENTS.md\n" + END + "\n"),
        (".gitignore", GITIGNORE[0], GITIGNORE[-1], "\n".join(GITIGNORE) + "\n"),
    ):
        path = target(project, name)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if name == "CLAUDE.md" and "@AGENTS.md" in text and START not in text:
            continue
        updated = block(text, start, end, body)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(name)
    record = {"format": 1, "source_commit": commit, "installed": now(),
              "files": {name: digest(content) for name, content in files.items()}}
    if record["files"] != previous or not manifest.exists():
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"project": str(project), "source_commit": commit, "files": len(files), "changed": changed}


def verify(project):
    """List managed files that are missing or were edited after installation."""
    project = Path(project).resolve()
    manifest = project / MANIFEST
    if not manifest.is_file():
        return [MANIFEST + "（缺失）"]
    drift = []
    for name, expected in json.loads(manifest.read_text(encoding="utf-8"))["files"].items():
        path = project / name
        if not path.is_file():
            drift.append(name + "（缺失）")
        elif digest(path.read_bytes()) != expected:
            drift.append(name + "（已修改）")
    return drift
