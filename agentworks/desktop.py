"""Local bookkeeping API used by agents inside desktop apps, never a model client."""
import secrets

from .backup import export_project, restore
from .core import Store, WorksError, load_config, now, read_json, validate_result, write_json
from .handoff import packet, role_for, run_dir, save_result

HOSTS = ("codex-desktop", "claude-code-desktop")


def receipt_path(store, project, run, task, attempt):
    return run_dir(store, project, run) / (str(task) + "-attempt-" + str(attempt) + "-desktop.json")


class Workspace:
    """The parent desktop agent coordinates; child agents receive only task prompts."""

    def __init__(self, data_dir=None):
        self.store = Store(data_dir)

    def check(self):
        from scripts.sync_agents import synchronize
        team, flows = load_config()
        return {"roles": len(team["roles"]), "workflows": len(flows),
                "configuration_drift": synchronize(check=True), "data_dir": str(self.store.home)}

    def status(self, project=None):
        if project is None:
            with self.store.db() as db:
                return [dict(row) for row in db.execute("SELECT * FROM projects ORDER BY created")]
        stages = []
        for run in self.store.runs(project):
            tasks = self.store.tasks(run["id"])
            for task in tasks:
                path = receipt_path(self.store, project, run["id"], task["id"], task["attempts"])
                if task["status"] == "running" and path.is_file():
                    task["execution"] = read_json(path)
            stages.append({"id": run["id"], "phase": run["phase"], "status": self.store.run_status(run),
                           "ready": [] if run["abandoned"] else [t["id"] for t in self.store.ready(run["id"])],
                           "tasks": tasks})
        return {"project": self.store.project(project), "workspace": str(self.store.workspace(project)),
                "data_dir": str(self.store.home), "stages": stages}

    def create(self, project, title, kind="compare", market="待选择", brief=""):
        self.store.create(project, title, kind, market, brief)
        return self.status(project)

    def plan(self, project, phase):
        self.store.plan(project, phase)
        return self.status(project)

    def begin(self, project, host, max_tasks=1):
        """Reserve a batch before native delegation; writers always run alone."""
        if host not in HOSTS or type(max_tasks) is not int or not 1 <= max_tasks <= 3:
            raise WorksError("请选择桌面平台 codex-desktop 或 claude-code-desktop；每批任务数为1–3。")
        with self.store.lock(project):
            runs = self.store.runs(project)
            if any(t["status"] == "running" for r in runs for t in self.store.tasks(r["id"])):
                raise WorksError("该项目已有桌面任务执行中，请收齐交付；若已中断，先确认子 Agent 停止，再恢复状态。")
            run = self.store.latest(project)
            ready = self.store.ready(run["id"])
            if not ready:
                return []
            batch = [ready[0]] if role_for(run, ready[0])["mode"] == "workspace-write" else [
                t for t in ready if role_for(run, t)["mode"] == "read-only"
            ][:max_tasks]
            # Materialize inputs before claiming, preserving retry context.
            prompts = {t["id"]: packet(self.store, project, t) for t in batch}
            claimed, assignments = [], []
            try:
                for task in batch:
                    self.store.claim(task)
                    claimed.append(task)
                    attempt = task["attempts"] + 1
                    ticket = {"task": task["id"], "run": run["id"], "attempt": attempt,
                              "token": secrets.token_hex(16)}
                    receipt = {"ticket": ticket, "host": host, "started": now()}
                    path = receipt_path(self.store, project, run["id"], task["id"], attempt)
                    write_json(path, receipt)
                    path.with_name(path.name.replace("-desktop.json", "-prompt.txt")).write_text(
                        prompts[task["id"]], encoding="utf-8")
                    assignments.append({"ticket": ticket, "role": task["spec"]["role"],
                                        "prompt": prompts[task["id"]]})
                with self.store.db() as db:
                    self.store.event(db, project, "desktop_started", host + ": " + ",".join(str(t["id"]) for t in batch))
            except Exception:
                for task in claimed:
                    self.store.finish(project, task, error="桌面任务准备失败，检查保存目录后重试。")
                raise
            return assignments

    def _active(self, project, ticket):
        if not isinstance(ticket, dict) or not isinstance(ticket.get("token"), str):
            raise WorksError("缺少有效的桌面任务交接凭据。")
        run = self.store.latest(project)
        task = next((t for t in self.store.tasks(run["id"]) if t["id"] == ticket.get("task")), None)
        if (not task or run["id"] != ticket.get("run") or task["status"] != "running"
                or task["attempts"] != ticket.get("attempt")):
            raise WorksError("交付不属于当前执行中的尝试，拒绝覆盖。")
        path = receipt_path(self.store, project, run["id"], task["id"], task["attempts"])
        if not path.is_file() or read_json(path)["ticket"] != ticket:
            raise WorksError("桌面任务交接凭据不匹配。")
        return task

    def complete(self, project, ticket, result):
        """Validate a native agent's JSON result; never calls a model or spawns a process."""
        with self.store.lock(project):
            task = self._active(project, ticket)
            result = validate_result(result, self.store.workspace(project), task["spec"])
            directory = run_dir(self.store, project, task["run"])
            write_json(directory / (str(task["id"]) + "-attempt-" + str(task["attempts"]) + "-result.json"), result)
            save_result(self.store, project, task, result)
            return self.store.finish(project, task, result=result)

    def fail(self, project, ticket, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise WorksError("请记录本次执行未完成的原因。")
        with self.store.lock(project):
            return self.store.finish(project, self._active(project, ticket), error=reason)

    def retry(self, project, task, reason):
        self.store.retry(project, task, reason)
        return self.status(project)

    def recover(self, project, *, workers_stopped, reason):
        # Native desktop subagents aren't child processes of this library.
        if workers_stopped is not True or not isinstance(reason, str) or not reason.strip():
            raise WorksError("恢复前必须确认旧桌面子 Agent 已停止，并记录原因。")
        count = self.store.recover(project)
        with self.store.db() as db:
            self.store.event(db, project, "desktop_recovered", reason)
        return count

    def abandon(self, project, reason):
        self.store.abandon(project, reason)
        return self.status(project)

    def note(self, project, text):
        if not isinstance(text, str) or not text.strip():
            raise WorksError("项目记忆不能为空。")
        with self.store.lock(project):
            with (self.store.workspace(project) / "MEMORY.md").open("a", encoding="utf-8") as out:
                out.write("\n- " + now() + " " + text + "\n")
            with self.store.db() as db:
                self.store.event(db, project, "note", text)

    def export(self, project, destination):
        return export_project(self.store, project, destination)

    def restore(self, archive):
        return restore(self.store, archive)

    def history(self, project):
        return self.store.history(project)
