"""Restore a project export into an empty data store without overwriting projects."""
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
                    if not (staged / "workspace/BRIEF.md").is_file():
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
                    import subprocess
                    subprocess.run(["git", "init", "--quiet", str(staged / "workspace")], check=True, capture_output=True)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staged), str(destination))
    return name
