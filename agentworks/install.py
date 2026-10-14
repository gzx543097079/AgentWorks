"""Embed AgentWorks into a product repository; that repository becomes the product workspace."""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from .core import DOCS, EMBEDDED, EMBEDDED_META, LEGACY_META, ROOT, WorksError, now

ENGINE = ".agentworks/engine"
MANIFEST = ENGINE + "/install.json"
START, END = "<!-- agentworks:start -->", "<!-- agentworks:end -->"
GITIGNORE = [
    "# agentworks:start",
    ".agentworks/locks/",
    ".agentworks/**/*.tmp",
    ".agentworks/engine/**/__pycache__/",
    "# 真实用户资料默认不提交",
    DOCS + "/" + EMBEDDED_META["input"] + "/*",
    "!" + DOCS + "/" + EMBEDDED_META["input"] + "/README.md",
    ".agentworks/projects/*/input/*",
    "!.agentworks/state.sqlite3",
    "# agentworks:end",
]
RULES = """{start}
## AgentWorks 产品团队

本仓库内嵌 AgentWorks {version}（来源提交 {commit}），本仓库就是产品工作区。用户通过聊天运行海外产品团队，使用当前桌面会话的原生子 Agent 和工具，不另行启动模型命令行，不要求用户操作终端。

- 与用户的回答、交付报告和项目文档一律使用简体中文；代码标识符、命令、路径和引用原文保持原样，目标市场文案使用当地语言。
- 运行团队先读技能 `agentworks`（Codex `$agentworks`，Claude `/agentworks`）和 `.agentworks/engine/docs/团队运行手册.md`。原生角色名称以 `agentworks-` 开头，位于 `.codex/agents/` 与 `.claude/agents/`。
- 手册中的 `config/`、`docs/`、`roles/` 在本仓库位于 `.agentworks/engine/` 下；技能位于 `.agents/skills/`（Claude 为 `.claude/skills/`）。
- 进度接口：在仓库根目录运行 Python，先 `sys.path.insert(0, ".agentworks/engine")`，再 `from agentworks.desktop import Workspace; team = Workspace()`，用法见 `.agentworks/engine/docs/桌面内部接口.md`。本仓库只绑定一个项目，开始前先 `team.status()`。
- 团队产出都是本项目的文件，按类别放在项目目录并随仓库提交：各阶段报告在 `文档/01-机会研究/` 至 `文档/06-运营迭代/`；项目简报、项目记忆和输入资料在 `文档/`；原型 `design/prototype/`、UI 设计稿 `design/ui/`、美术与动画 `design/art/`、音频 `design/audio/`；源代码 `app/`；发布配置 `release/`；商店文案与截图 `store/`；获客素材 `marketing/`；帮助内容 `support/`。`文档/输入资料/` 中的真实用户资料默认不提交。
- `.agentworks/` 只保存工具内部的状态库、任务包和执行凭据。每个阶段验收通过后提醒用户提交项目，或在用户授权下提交。
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
    files[ENGINE + "/VERSION"] = (source / "VERSION").read_bytes()
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
    state = project / ".agentworks/state.sqlite3"
    if state.is_file():
        db = sqlite3.connect("file:" + str(state) + "?mode=ro", uri=True)
        try:
            running = db.execute("SELECT COUNT(*) FROM tasks WHERE status='running'").fetchone()[0]
        except sqlite3.Error:
            running = 0
        finally:
            db.close()
        if running:
            raise WorksError("该项目有 " + str(running) + " 项任务正在执行，请等当前批次交回并保存后再安装或升级。")
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
    changed += migrate(project)
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    version = (source / "VERSION").read_text(encoding="utf-8").strip()
    for name, start, end, body in (
        ("AGENTS.md", START, END, RULES.format(start=START, end=END, commit=commit, version=version)),
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
    record = {"format": 1, "version": version, "source_commit": commit, "installed": now(),
              "files": {name: digest(content) for name, content in files.items()}}
    if record["files"] != previous or not manifest.exists():
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    changed += publish(project)
    return {"notice": "已打开的总控会话请重新读取 .agentworks/engine/docs/团队运行手册.md，或新开会话后继续。",
            "project": str(project), "version": version, "source_commit": commit, "files": len(files), "changed": changed}


def migrate(project):
    """Move a pre-1.2.0 brief, memory and inputs out of .agentworks/ into the project's documents."""
    moved = []
    docs = project / DOCS
    for folder in sorted((project / ".agentworks/projects").glob("*")):
        for key in ("brief", "memory", "input"):
            old, new = folder / LEGACY_META[key], docs / EMBEDDED_META[key]
            if old.exists() and not old.is_symlink() and not new.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new)
                moved.append(str(new.relative_to(project)) + "（自 " + str(old.relative_to(project)) + " 迁移）")
    return moved


def publish(project):
    """Ask the freshly installed engine to place completed reports into the document folders."""
    if not (project / ".agentworks/state.sqlite3").is_file():
        return []
    code = ("import json, sys; sys.path.insert(0, sys.argv[1]); from agentworks.desktop import Workspace; "
            "t = Workspace(); print(json.dumps([n for p in t.status() for n in t.publish(p['id'])], ensure_ascii=False))")
    out = subprocess.run([sys.executable, "-I", "-c", code, str(project / ENGINE)], cwd=project,
                         capture_output=True, text=True)
    if out.returncode:
        raise WorksError("安装完成，但整理已有报告失败：" + out.stderr.strip()[-300:])
    return [name + "（已有报告）" for name in json.loads(out.stdout or "[]")]


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
