"""Chinese-first local entry point for AgentWorks."""
import argparse
import datetime as dt
import json
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .core import ROOT, Store, WorksError, load_config, read_json, write_json
from .runner import packet, run_tasks, submit
from .backup import restore
from .backends import BACKENDS


def doctor():
    team, flows = load_config()
    print("AgentWorks 配置正常：%s 个资深角色，%s 个工作流。" % (len(team["roles"]), len(flows)))
    sync = subprocess.run([sys.executable, str(ROOT / "scripts/sync_agents.py"), "--check"], capture_output=True, text=True)
    print(sync.stdout.strip())
    for backend in BACKENDS:
        binary = shutil.which(backend)
        if not binary:
            print(backend + " CLI：未检测到（不影响当前对话通过 packet / submit 使用团队）。")
            continue
        try:
            version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=15)
            print(backend + "：" + (version.stdout.strip() if version.returncode == 0 else "版本检查失败"))
            if backend == "codex":
                auth = subprocess.run([binary, "login", "status"], capture_output=True, text=True, timeout=15)
                print("Codex 登录：" + ("已登录" if auth.returncode == 0 else "尚未登录；可运行 codex login"))
            else:
                print("Claude 登录和模型连通性尚未验证；版本检查不会调用模型。")
        except (OSError, subprocess.SubprocessError) as exc:
            print(backend + " 检查失败：" + str(exc))
    print("支持平台：Codex（AGENTS.md）和 Claude Code（CLAUDE.md 导入共用规则）。")
    print("两平台共用 config/team.json 和项目状态；原生角色配置由同步脚本自动生成。")
    print("运行数据默认保存在 .agentworks/，不会进入 Git。当前系统未安装常驻服务。")
    return sync.returncode


def status(store, project=None):
    if not project:
        with store.db() as db:
            projects = [dict(p) for p in db.execute("SELECT * FROM projects ORDER BY created")]
        if not projects:
            print("还没有项目。使用 create 新建项目。")
        for item in projects:
            print(item["id"] + " | " + item["title"] + " | " + item["kind"])
        return
    item = store.project(project)
    print(item["title"] + " [" + project + "]")
    print("工作区：" + str(store.workspace(project)))
    runs = store.runs(project)
    for run in runs:
        print("\n阶段 #%s %s [%s]" % (run["id"], run["phase"], store.run_status(run)))
        ready = {t["id"] for t in store.ready(run["id"])}
        for task in store.tasks(run["id"]):
            label = "ready" if task["id"] in ready and not run["abandoned"] else task["status"]
            print("  %s %-15s %s (%s/3)" % (task["id"], label, task["spec"]["title"], task["attempts"]))
            if task["error"]:
                print("    " + task["error"])


def export_project(store, project, output):
    destination = Path(output).expanduser().resolve()
    source = store.home / "projects" / project
    if destination == source or source in destination.parents:
        raise WorksError("备份文件应放在项目工作区外。")
    if destination.exists():
        raise WorksError("目标文件已存在，拒绝覆盖。")
    with store.lock(project):
        snapshot = {"format": 1, "project": store.project(project), "runs": [], "events": store.history(project)}
        for run in store.runs(project):
            snapshot["runs"].append({"run": run, "tasks": store.tasks(run["id"])})
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "backup.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
                for path in source.rglob("*"):
                    if path.is_symlink():
                        continue
                    if path.is_file() and ".git" not in path.relative_to(source).parts and not path.name.endswith("-process.json"):
                        z.write(path, "files/" + str(path.relative_to(source)))
            shutil.copyfile(archive, destination)
    print("已导出项目状态、决策、报告与产物：" + str(destination))


def parser():
    p = argparse.ArgumentParser(description="AgentWorks · 可复用的海外产品团队")
    p.add_argument("--data-dir", type=Path, help="自定义持久存储目录")
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="检查配置和本机能力")
    commands.add_parser("roles", help="列出固定角色")
    commands.add_parser("workflows", help="列出协作流程")
    create = commands.add_parser("create", help="创建独立项目")
    create.add_argument("project")
    create.add_argument("--title", required=True)
    create.add_argument("--kind", choices=["compare", "game", "tool"], default="compare")
    create.add_argument("--market", default="待选择")
    create.add_argument("--brief", default="", help="用户目标、预算和约束")
    s = commands.add_parser("status", help="查看项目和进度")
    s.add_argument("project", nargs="?")
    plan = commands.add_parser("plan", help="创建工作流任务；重复调用复用未完成阶段")
    plan.add_argument("project")
    plan.add_argument("phase", choices=list(load_config()[1]))
    for name in ("run", "continue"):
        run = commands.add_parser(name, help="执行当前阶段的就绪任务；默认只预览")
        run.add_argument("project")
        run.add_argument("--execute", action="store_true", help="调用所选 CLI，实际使用该账号模型额度")
        run.add_argument("--backend", choices=["auto", *BACKENDS], default="auto",
                         help="auto 仅在恰好安装一个 CLI 时自动选择；可指定 codex 或 claude")
        run.add_argument("--max-tasks", type=int, default=1)
        run.add_argument("--workers", type=int, default=2)
        run.add_argument("--timeout", type=int, default=900)
        run.add_argument("--model", help="显式选择模型；默认继承本机设置")
        run.add_argument("--no-search", action="store_true")
    pack = commands.add_parser("packet", help="导出单角色任务包，供对话中的 agent 执行")
    pack.add_argument("project")
    pack.add_argument("task", type=int)
    pack.add_argument("--output", type=Path)
    complete = commands.add_parser("submit", help="导入 agent 的结构化交付并校验")
    complete.add_argument("project")
    complete.add_argument("task", type=int)
    complete.add_argument("result", type=Path)
    retry = commands.add_parser("retry", help="补充输入或修复后重试任务，最多3次")
    retry.add_argument("project")
    retry.add_argument("task", type=int)
    retry.add_argument("--reason", required=True)
    recover = commands.add_parser("recover", help="把意外中断的状态标为失败，供检查后重试")
    recover.add_argument("project")
    abandon = commands.add_parser("abandon", help="保留历史并终止当前阶段")
    abandon.add_argument("project")
    abandon.add_argument("--reason", required=True)
    history = commands.add_parser("history", help="查看项目事件记录")
    history.add_argument("project")
    note = commands.add_parser("note", help="保存跨会话的项目决策或偏好")
    note.add_argument("project")
    note.add_argument("text")
    exp = commands.add_parser("export", help="备份一个项目的状态与文件")
    exp.add_argument("project")
    exp.add_argument("output", type=Path)
    rest = commands.add_parser("restore", help="将备份恢复到空的数据目录")
    rest.add_argument("archive", type=Path)
    return p


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == "doctor":
            return doctor()
        if args.command == "roles":
            for role in load_config()[0]["roles"]:
                print(role["id"] + " | " + role["name"] + " | 20年资深标准 | " + role["description"])
            return 0
        if args.command == "workflows":
            for key, flow in load_config()[1].items():
                print(key + " | " + flow["name"] + " | 前置：" + str(flow["requires"] or "无"))
            return 0
        store = Store(args.data_dir)
        if args.command == "create":
            store.create(args.project, args.title, args.kind, args.market, args.brief)
            print("已创建：" + str(store.workspace(args.project)))
        elif args.command == "status":
            status(store, args.project)
        elif args.command == "plan":
            run = store.plan(args.project, args.phase)
            print("工作流已准备：#" + str(run["id"]) + " " + run["phase"])
            status(store, args.project)
        elif args.command in ("run", "continue"):
            if args.execute:
                def interrupted(signum, frame):
                    raise KeyboardInterrupt()
                previous_handler = signal.signal(signal.SIGTERM, interrupted)
                try:
                    results = run_tasks(store, args.project, args.max_tasks, args.workers, args.timeout, args.model, not args.no_search, backend=args.backend)
                finally:
                    signal.signal(signal.SIGTERM, previous_handler)
                status(store, args.project)
                return 0 if all(s == "completed" for _, s in results) and store.run_status(store.latest(args.project)) in ("pending", "completed") else 1
            run = store.latest(args.project)
            print("预览：本次没有调用模型。加 --execute 执行，--max-tasks 控制调用数量。")
            for task in store.ready(run["id"]):
                print(str(task["id"]) + " " + task["spec"]["title"] + " → " + task["spec"]["role"])
        elif args.command == "packet":
            run = store.latest(args.project)
            task = next((t for t in store.ready(run["id"]) if t["id"] == args.task), None)
            if task is None:
                raise WorksError("任务未就绪；请检查依赖及当前状态。")
            content = packet(store, args.project, task)
            if args.output:
                if args.output.exists():
                    raise WorksError("任务包目标已存在，拒绝覆盖。")
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(content, encoding="utf-8")
                print(str(args.output.resolve()))
            else:
                print(content)
        elif args.command == "submit":
            print(submit(store, args.project, args.task, args.result))
        elif args.command == "retry":
            store.retry(args.project, args.task, args.reason)
            print("已恢复为待处理任务。")
        elif args.command == "recover":
            print("已恢复中断状态：" + str(store.recover(args.project)))
        elif args.command == "abandon":
            store.abandon(args.project, args.reason)
            print("当前阶段已终止，历史保留。")
        elif args.command == "history":
            for event in store.history(args.project):
                print(event["at"] + " " + event["kind"] + " " + event["detail"])
        elif args.command == "note":
            with store.lock(args.project):
                path = store.workspace(args.project) / "MEMORY.md"
                with path.open("a", encoding="utf-8") as handle:
                    handle.write("\n- " + dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds") + " " + args.text + "\n")
                with store.db() as db:
                    store.event(db, args.project, "note", args.text)
            print("已保存项目记忆。")
        elif args.command == "export":
            export_project(store, args.project, args.output)
        elif args.command == "restore":
            print("已恢复项目：" + restore(store, args.archive))
        return 0
    except KeyboardInterrupt:
        print("执行已中断，已保存的交付保留。请查看 status 后继续。", file=sys.stderr)
        return 130
    except (WorksError, OSError, ValueError, sqlite3.Error, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print("错误：" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
