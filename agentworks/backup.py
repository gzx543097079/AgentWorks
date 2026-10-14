"""Export project data and restore it into an empty store without overwriting work."""
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .core import WorksError, slug


def restore(store, archive):
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist()) > 1024 * 1024 * 1024:
            raise WorksError("备份解压后超过1GB，请手动检查后迁移。")
        snapshot = json.loads(z.read("snapshot.json"))
        if snapshot.get("format") != 1:
            raise WorksError("不支持的备份格式。")
        project = snapshot["project"]
        name = slug(project["id"])
        with store.lock(name):
            with store.db() as db:
                if db.execute("SELECT 1 FROM projects LIMIT 1").fetchone():
                    raise WorksError("请恢复到空的数据目录；现有项目不会被覆盖。")
                destination = store.home / "projects" / name
                if destination.exists():
                    raise WorksError("已有同名文件，拒绝覆盖。")
                with tempfile.TemporaryDirectory(dir=store.home) as temp:
                    staged = Path(temp)
                    for item in z.infolist():
                        if item.filename == "snapshot.json":
                            continue
                        parts = PurePosixPath(item.filename).parts
                        if not parts or parts[0] != "files" or ".." in parts or "\\" in item.filename:
                            raise WorksError("备份包含非法路径。")
                        if (item.external_attr >> 16) & 0o170000 == 0o120000:
                            raise WorksError("备份包含符号链接。")
                        target = staged.joinpath(*parts[1:])
                        if item.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(item) as source, target.open("wb") as out:
                                shutil.copyfileobj(source, out)
                    brief = staged / ("BRIEF.md" if store.product_root else "workspace/BRIEF.md")
                    if not brief.is_file():
                        raise WorksError("备份缺少项目简报。")
                    db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", tuple(project[k] for k in ("id", "title", "kind", "market", "created")))
                    for entry in snapshot["runs"]:
                        run = entry["run"]
                        if run["project"] != name:
                            raise WorksError("备份包含其他项目状态。")
                        db.execute("INSERT INTO runs(id,project,phase,config,prerequisite,created,abandoned) VALUES(?,?,?,?,?,?,?)",
                                   tuple(run[k] for k in ("id", "project", "phase", "config", "prerequisite", "created", "abandoned")))
                        for task in entry["tasks"]:
                            if task["run"] != run["id"]:
                                raise WorksError("任务所属阶段无效。")
                            status = "failed" if task["status"] == "running" else task["status"]
                            db.execute("INSERT INTO tasks(id,run,code,spec,status,attempts,result,error) VALUES(?,?,?,?,?,?,?,?)",
                                       (task["id"], task["run"], task["code"], json.dumps(task["spec"], ensure_ascii=False), status,
                                        task["attempts"], json.dumps(task["result"], ensure_ascii=False) if task["result"] else None,
                                        "恢复前执行中断，请检查后重试。" if task["status"] == "running" else task["error"]))
                    for event in snapshot["events"]:
                        db.execute("INSERT INTO events(project,at,kind,detail) VALUES(?,?,?,?)",
                                   (name, event["at"], event["kind"], event["detail"]))
                    store.event(db, name, "restored", "从本地备份恢复")
                    # Product files have a separate Git boundary on each machine.
                    # Embedded product code is restored from the host repository's own Git.
                    if not store.product_root:
                        import subprocess
                        subprocess.run(["git", "init", "--quiet", str(staged / "workspace")], check=True, capture_output=True)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staged), str(destination))
    return name


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
            if any(task["status"] == "running" for task in store.tasks(run["id"])):
                raise WorksError("请先结束桌面 Agent 任务再备份，避免备份正在改写的交付。")
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
    return str(destination)
