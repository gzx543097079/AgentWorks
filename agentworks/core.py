"""Project state and dependency scheduling, using only the Python standard library."""
import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# An installed copy lives at <product>/.agentworks/engine and marks itself with install.json.
EMBEDDED = (ROOT / "install.json").is_file()
PRODUCT_ROOT = ROOT.parents[1] if EMBEDDED else None
SKILLS_ROOT = PRODUCT_ROOT or ROOT


class WorksError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def slug(value):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value):
        raise WorksError("项目编号使用小写字母开头，最多48个字母、数字或连字符。")
    return value


def within(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if path == root or root not in path.parents:
        raise WorksError("文件必须位于当前产品工作区内：" + str(name))
    return path


def load_config():
    from .skills import role_skills
    team = read_json(ROOT / "config/team.json")
    flows = read_json(ROOT / "config/workflows.json")
    roles = {r["id"]: r for r in team["roles"]}
    if len(roles) != len(team["roles"]):
        raise WorksError("角色编号重复。")
    for role in roles.values():
        if role["experience_years"] != 20 or role["mode"] not in ("read-only", "workspace-write"):
            raise WorksError("角色经验或权限配置无效。")
        try:
            if not role_skills(SKILLS_ROOT, role):
                raise ValueError("当前团队的角色必须绑定技能：" + role["id"])
        except ValueError as exc:
            raise WorksError(str(exc)) from exc
    for phase, flow in flows.items():
        seen = set()
        for task in flow["tasks"]:
            if task["id"] in seen or task["role"] not in roles or not set(task["depends"]) <= seen:
                raise WorksError("工作流角色、任务顺序或依赖无效：" + phase)
            seen.add(task["id"])
        if not flow["tasks"][-1].get("gate"):
            raise WorksError("工作流必须以独立验收任务结束：" + phase)
        if flow["requires"] is not None and flow["requires"] not in flows:
            raise WorksError("前置阶段不存在。")
    return team, flows


class Store:
    def __init__(self, data_dir=None, product_root=None):
        if data_dir is None and product_root is None and EMBEDDED:
            data_dir, product_root = ROOT.parent, PRODUCT_ROOT
        self.home = Path(data_dir or ROOT / ".agentworks").resolve()
        # Embedded mode: the host repository is the single product workspace.
        self.product_root = Path(product_root).resolve() if product_root else None
        self.home.mkdir(parents=True, exist_ok=True)
        self.dbpath = self.home / "state.sqlite3"
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                  id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
                  market TEXT NOT NULL, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL,
                  phase TEXT NOT NULL, config TEXT NOT NULL, prerequisite INTEGER,
                  created TEXT NOT NULL, abandoned INTEGER NOT NULL DEFAULT 0,
                  FOREIGN KEY(project) REFERENCES projects(id));
                CREATE TABLE IF NOT EXISTS tasks (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, run INTEGER NOT NULL,
                  code TEXT NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                  attempts INTEGER NOT NULL DEFAULT 0, result TEXT, error TEXT,
                  UNIQUE(run, code), FOREIGN KEY(run) REFERENCES runs(id));
                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL,
                  at TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
            """)

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(str(self.dbpath), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def event(self, db, project, kind, detail):
        db.execute("INSERT INTO events(project,at,kind,detail) VALUES(?,?,?,?)", (project, now(), kind, detail))

    def project(self, project):
        slug(project)
        with self.db() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project,)).fetchone()
        if row is None:
            raise WorksError("找不到项目：" + project)
        return dict(row)

    def workspace(self, project):
        self.project(project)
        return self.product_root or self.home / "projects" / project / "workspace"

    def meta(self, project):
        """Folder holding BRIEF.md, MEMORY.md and input/."""
        self.project(project)
        return self.home / "projects" / project if self.product_root else self.workspace(project)

    @contextlib.contextmanager
    def lock(self, project):
        slug(project)
        directory = self.home / "locks"
        directory.mkdir(exist_ok=True)
        with (directory / (project + ".lock")).open("a+") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise WorksError("此项目正在运行，请等待当前任务结束。")
            try:
                runs = self.home / "projects" / project / "runs"
                for marker in runs.glob("*/*-process.json"):
                    pid = read_json(marker)["pid"]
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        marker.unlink()
                    except PermissionError:
                        raise WorksError("此前的后台任务仍可能运行，请先检查进程 " + str(pid))
                    else:
                        raise WorksError("此前的后台任务仍在运行，请等待进程结束：" + str(pid))
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def create(self, project, title, kind="compare", market="待选择", brief=""):
        slug(project)
        if kind not in ("compare", "game", "tool"):
            raise WorksError("产品类型无效。")
        with self.lock(project):
            with self.db() as db:
                if db.execute("SELECT 1 FROM projects WHERE id=?", (project,)).fetchone():
                    raise WorksError("项目已存在；请读取已保存的进度继续。")
                if self.product_root:
                    existing = db.execute("SELECT id FROM projects LIMIT 1").fetchone()
                    if existing:
                        raise WorksError("本仓库已绑定项目 " + existing["id"] + "；一个产品仓库只对应一个项目。")
                    workspace = self.home / "projects" / project
                    if workspace.exists():
                        raise WorksError("已有同名项目资料，请保留内容后使用不同项目编号。")
                    workspace.mkdir(parents=True)
                    if not (self.product_root / ".git").exists():
                        subprocess.run(["git", "init", "--quiet", str(self.product_root)], check=True, capture_output=True)
                else:
                    workspace = self.home / "projects" / project / "workspace"
                    if workspace.exists():
                        raise WorksError("已有同名工作区，请保留内容后使用不同项目编号。")
                    workspace.mkdir(parents=True)
                    # Keep product files inside their own Git workspace boundary.
                    subprocess.run(["git", "init", "--quiet", str(workspace)], check=True, capture_output=True)
                (workspace / "input").mkdir()
                (workspace / "BRIEF.md").write_text(
                    "# " + title + "\n\n项目类型：" + kind + "\n目标市场：" + market +
                    "\n\n## 用户提供的目标与约束\n" + (brief or "尚未补充具体预算、选题或时间约束；研究时保留未知。") +
                    "\n\n## 已选择的方向\n待研究后记录。\n\n## 授权范围\n研究、设计和本地开发；对外操作按用户后续明确授权。\n", encoding="utf-8")
                (workspace / "MEMORY.md").write_text("# 项目长期记忆\n\n只记录已确认的偏好、决策及理由，并注明日期和来源。\n", encoding="utf-8")
                (workspace / "input/README.md").write_text("# 输入资料\n\n放入真实用户反馈、竞品资料或经营数据，并附来源、日期和字段说明。AI模拟结果不得标作真实数据。\n", encoding="utf-8")
                db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (project, title, kind, market, now()))
                self.event(db, project, "created", title)
        return self.project(project)

    def runs(self, project):
        self.project(project)
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM runs WHERE project=? ORDER BY id", (project,))]

    def latest(self, project, phase=None):
        runs = [r for r in self.runs(project) if not r["abandoned"] and (phase is None or r["phase"] == phase)]
        if not runs:
            raise WorksError("尚无对应工作流，请先 plan。")
        return runs[-1]

    def tasks(self, run):
        with self.db() as db:
            rows = db.execute("SELECT * FROM tasks WHERE run=? ORDER BY id", (run,)).fetchall()
        result = []
        for row in rows:
            task = dict(row)
            task["spec"] = json.loads(task["spec"])
            task["result"] = json.loads(task["result"]) if task["result"] else None
            result.append(task)
        return result

    def run_status(self, run):
        if run["abandoned"]:
            return "abandoned"
        statuses = {t["status"] for t in self.tasks(run["id"])}
        for status in ("running", "failed", "blocked", "needs_revision", "pending"):
            if status in statuses:
                return status
        return "completed"

    def plan(self, project, phase):
        self.project(project)
        team, flows = load_config()
        if phase not in flows:
            raise WorksError("未知工作流：" + phase)
        with self.lock(project):
            active = [r for r in self.runs(project) if not r["abandoned"] and self.run_status(r) != "completed"]
            if active:
                if len(active) == 1 and active[0]["phase"] == phase:
                    return active[0]
                raise WorksError("请先完成当前阶段；需要改做其他阶段时使用 abandon 并记录原因。")
            required = flows[phase]["requires"]
            prerequisite = None
            if required:
                previous = self.latest(project, required)
                if self.run_status(previous) != "completed":
                    raise WorksError("前置阶段未通过：" + required)
                lineage = previous
                by_id = {r["id"]: r for r in self.runs(project)}
                while lineage["prerequisite"] is not None:
                    parent = by_id[lineage["prerequisite"]]
                    if self.latest(project, parent["phase"])["id"] != parent["id"] or parent["abandoned"]:
                        raise WorksError("前置交付已过期，请从 " + required + " 阶段重新评估。")
                    lineage = parent
                prerequisite = previous["id"]
            snapshot = {"team": team, "flow": flows[phase]}
            with self.db() as db:
                run = db.execute("INSERT INTO runs(project,phase,config,prerequisite,created) VALUES(?,?,?,?,?)",
                                 (project, phase, json.dumps(snapshot, ensure_ascii=False), prerequisite, now())).lastrowid
                for task in flows[phase]["tasks"]:
                    db.execute("INSERT INTO tasks(run,code,spec) VALUES(?,?,?)", (run, task["id"], json.dumps(task, ensure_ascii=False)))
                self.event(db, project, "planned", phase + " #" + str(run))
        return self.latest(project)

    def ready(self, run):
        tasks = self.tasks(run)
        done = {t["code"] for t in tasks if t["status"] == "completed"}
        return [t for t in tasks if t["status"] == "pending" and set(t["spec"]["depends"]) <= done]

    def claim(self, task):
        with self.db() as db:
            changed = db.execute("UPDATE tasks SET status='running', attempts=attempts+1, error=NULL WHERE id=? AND status='pending' AND attempts<3", (task["id"],)).rowcount
        if not changed:
            raise WorksError("任务已被处理或达到3次尝试上限。")

    def finish(self, project, task, result=None, error=None):
        status = "failed" if error else "completed"
        if result:
            if result["status"] == "blocked" or result["verdict"] == "blocked":
                status = "blocked"
            elif task["spec"].get("gate") and result["verdict"] != "pass":
                status = "needs_revision"
        with self.db() as db:
            changed = db.execute("UPDATE tasks SET status=?,result=?,error=? WHERE id=? AND status='running'",
                                 (status, json.dumps(result, ensure_ascii=False) if result else None, error, task["id"])).rowcount
            if not changed:
                raise WorksError("任务并非运行状态，拒绝覆盖结果。")
            self.event(db, project, status, str(task["id"]) + ": " + (error or result["summary"]))
        return status

    def retry(self, project, task_id, reason):
        if not reason.strip():
            raise WorksError("需要说明修复了什么或补充了什么输入。")
        with self.lock(project):
            run = self.latest(project)
            task = next((t for t in self.tasks(run["id"]) if t["id"] == task_id), None)
            if not task or task["status"] not in ("failed", "blocked", "needs_revision"):
                raise WorksError("只允许重试当前阶段失败、阻塞或待修改的任务。")
            if task["attempts"] >= 3:
                raise WorksError("已达到3次尝试上限，请评估原因并明确开启新一轮流程。")
            with self.db() as db:
                db.execute("UPDATE tasks SET status='pending',error=?,result=NULL WHERE id=?", ("重试说明：" + reason, task_id))
                self.event(db, project, "retry", str(task_id) + ": " + reason)

    def recover(self, project):
        with self.lock(project):
            self.project(project)
            with self.db() as db:
                rows = db.execute("SELECT tasks.id FROM tasks JOIN runs ON tasks.run=runs.id WHERE runs.project=? AND tasks.status='running'", (project,)).fetchall()
                for row in rows:
                    db.execute("UPDATE tasks SET status='failed',error='上次执行中断；检查产物后使用 retry。' WHERE id=?", (row["id"],))
                self.event(db, project, "recover", "恢复中断任务数：" + str(len(rows)))
        return len(rows)

    def abandon(self, project, reason):
        if not reason.strip():
            raise WorksError("请提供终止原因。")
        with self.lock(project):
            run = self.latest(project)
            if any(t["status"] == "running" for t in self.tasks(run["id"])):
                raise WorksError("仍有任务执行中；先停止并恢复中断状态，再终止本阶段。")
            with self.db() as db:
                db.execute("UPDATE runs SET abandoned=1 WHERE id=?", (run["id"],))
                self.event(db, project, "abandoned", str(run["id"]) + ": " + reason)

    def history(self, project):
        self.project(project)
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM events WHERE project=? ORDER BY id", (project,))]


def validate_result(result, workspace, spec=None):
    required = {"status", "summary", "report", "verdict", "evidence", "artifacts", "next_actions"}
    if not isinstance(result, dict) or set(result) != required:
        raise WorksError("结果字段不符合交付格式。")
    if result["status"] not in ("completed", "blocked") or result["verdict"] not in ("pass", "revise", "blocked", "not_applicable"):
        raise WorksError("结果状态无效。")
    if any(not isinstance(result[k], str) or not result[k].strip() for k in ("summary", "report")):
        raise WorksError("摘要和报告不能为空。")
    for key in ("evidence", "artifacts", "next_actions"):
        if not isinstance(result[key], list):
            raise WorksError("结果列表无效：" + key)
    for item in result["evidence"]:
        if not isinstance(item, dict) or set(item) != {"kind", "source", "note"}:
            raise WorksError("证据格式无效。")
        if item["kind"] not in ("source", "observation", "hypothesis", "simulated", "unknown") or not all(isinstance(v, str) for v in item.values()):
            raise WorksError("证据类型无效。")
    if any(not isinstance(x, str) for x in result["next_actions"] + result["artifacts"]):
        raise WorksError("产物和下一步必须是字符串。")
    for name in result["artifacts"]:
        if Path(name).is_absolute() or not within(workspace, name).is_file():
            raise WorksError("交付文件不存在或越过项目边界：" + name)
    prefix = (spec or {}).get("artifact_prefix")
    if result["status"] == "completed" and prefix:
        folder = within(workspace, prefix)
        if not any(folder in within(workspace, name).parents for name in result["artifacts"]):
            raise WorksError("此任务必须交付 " + prefix + " 内的实际产品文件。")
    return result
