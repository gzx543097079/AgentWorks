import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentworks.core import Store, WorksError, load_config
from agentworks.desktop import Workspace


def result(verdict="not_applicable"):
    return {"status": "completed", "summary": "桌面交接测试", "report": "本地测试资料，不代表真实产品。",
            "verdict": verdict, "evidence": [], "artifacts": [], "next_actions": []}


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "data"
        self.desktop = Workspace(self.home)
        self.desktop.create("alpha", "桌面验证")
        self.desktop.plan("alpha", "discovery")

    def tearDown(self):
        self.temp.cleanup()

    def test_two_desktop_sessions_share_progress_without_starting_model_processes(self):
        # Project Git initialization is finished before this assertion.
        with patch("subprocess.Popen", side_effect=AssertionError("Unexpected external process")):
            task = self.desktop.begin("alpha", "codex-desktop")[0]
            self.assertIn('"output_schema"', task["prompt"])
            self.assertEqual(self.desktop.complete("alpha", task["ticket"], result()), "completed")
            other = Workspace(self.home)
            task = other.begin("alpha", "claude-code-desktop")[0]
            other.complete("alpha", task["ticket"], result())
            task = other.begin("alpha", "claude-code-desktop")[0]
            self.assertIn("本地测试资料", task["prompt"])
            other.complete("alpha", task["ticket"], result())
            tasks = self.desktop.status("alpha")["stages"][0]["tasks"]
        self.assertEqual([t["attempts"] for t in tasks], [1, 1, 1] + [0] * (len(tasks) - 3))
        self.assertEqual([t["status"] for t in tasks[:3]], ["completed"] * 3)

    def test_read_only_batch_reserves_distinct_tasks(self):
        tasks = self.desktop.begin("alpha", "codex-desktop", max_tasks=3)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(len({t["ticket"]["task"] for t in tasks}), 2)
        for task in tasks:
            self.desktop.complete("alpha", task["ticket"], result())
        following = self.desktop.begin("alpha", "codex-desktop", max_tasks=3)
        self.assertEqual({t["role"] for t in following}, {"growth_operator", "user_researcher"})

    def test_second_parent_cannot_dispatch_while_native_workers_run(self):
        tasks = self.desktop.begin("alpha", "codex-desktop", max_tasks=2)
        other = Workspace(self.home)
        self.desktop.complete("alpha", tasks[0]["ticket"], result())
        with self.assertRaises(WorksError):
            other.begin("alpha", "claude-code-desktop")

    def test_writer_is_reserved_alone(self):
        store = self.desktop.store
        task = store.ready(store.latest("alpha")["id"])[0]
        task["spec"]["role"] = "developer"
        with store.db() as db:
            db.execute("UPDATE tasks SET spec=? WHERE id=?", (json.dumps(task["spec"]), task["id"]))
        batch = self.desktop.begin("alpha", "claude-code-desktop", max_tasks=3)
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0]["role"], "developer")

    def test_asset_writers_are_reserved_alone_across_desktops(self):
        for role in ("art_director", "audio_designer"):
            with self.subTest(role=role):
                desktop = Workspace(self.home / role)
                desktop.create("assets", "资源写入隔离测试")
                desktop.plan("assets", "discovery")
                store = desktop.store
                task = store.ready(store.latest("assets")["id"])[0]
                task["spec"]["role"] = role
                with store.db() as db:
                    db.execute("UPDATE tasks SET spec=? WHERE id=?", (json.dumps(task["spec"]), task["id"]))
                batch = desktop.begin("assets", "codex-desktop", max_tasks=3)
                self.assertEqual([t["role"] for t in batch], [role])
                other = Workspace(desktop.store.home)
                with self.assertRaises(WorksError):
                    other.begin("assets", "claude-code-desktop", max_tasks=3)
                desktop.complete("assets", batch[0]["ticket"], result())
                self.assertEqual(other.begin("assets", "claude-code-desktop")[0]["role"], "market_researcher")

    def test_duplicate_completion_does_not_overwrite_report(self):
        task = self.desktop.begin("alpha", "codex-desktop")[0]
        self.desktop.complete("alpha", task["ticket"], result())
        new = result()
        new["report"] = "must not overwrite"
        with self.assertRaises(WorksError):
            self.desktop.complete("alpha", task["ticket"], new)
        saved = self.desktop.status("alpha")["stages"][0]["tasks"][0]["result"]
        self.assertEqual(saved["report"], result()["report"])

    def test_recovery_requires_stopped_workers_and_rejects_late_old_result(self):
        old = self.desktop.begin("alpha", "codex-desktop")[0]
        with self.assertRaises(WorksError):
            self.desktop.recover("alpha", workers_stopped=False, reason="still running")
        self.assertEqual(self.desktop.recover("alpha", workers_stopped=True, reason="原会话已停止"), 1)
        self.desktop.retry("alpha", old["ticket"]["task"], "原会话结束，改在另一个桌面会话处理")
        new = self.desktop.begin("alpha", "claude-code-desktop")[0]
        with self.assertRaises(WorksError):
            self.desktop.complete("alpha", old["ticket"], result())
        self.assertEqual(self.desktop.complete("alpha", new["ticket"], result()), "completed")

    def test_new_parent_can_read_saved_receipt_after_restart(self):
        old = self.desktop.begin("alpha", "codex-desktop")[0]
        fresh = Workspace(self.home)
        saved = fresh.status("alpha")["stages"][0]["tasks"][0]
        self.assertEqual(saved["execution"]["host"], "codex-desktop")
        self.assertEqual(saved["execution"]["ticket"], old["ticket"])
        self.assertEqual(fresh.complete("alpha", saved["execution"]["ticket"], result()), "completed")

    def test_invalid_result_keeps_reservation_for_correction(self):
        assignment = self.desktop.begin("alpha", "codex-desktop")[0]
        with self.assertRaises(WorksError):
            self.desktop.complete("alpha", assignment["ticket"], {"status": "completed"})
        self.assertEqual(self.desktop.status("alpha")["stages"][0]["tasks"][0]["status"], "running")
        self.desktop.complete("alpha", assignment["ticket"], result())

    def test_failed_preparation_does_not_leave_an_unfinishable_running_task(self):
        with patch("agentworks.desktop.write_json", side_effect=OSError("cannot save receipt")):
            with self.assertRaises(OSError):
                self.desktop.begin("alpha", "codex-desktop", max_tasks=2)
        tasks = self.desktop.status("alpha")["stages"][0]["tasks"]
        self.assertFalse(any(task["status"] == "running" for task in tasks))
        self.assertEqual(tasks[0]["status"], "failed")
        self.desktop.retry("alpha", tasks[0]["id"], "已恢复保存目录")
        retried = self.desktop.begin("alpha", "claude-code-desktop")[0]
        self.assertEqual(self.desktop.complete("alpha", retried["ticket"], result()), "completed")

    def test_native_worker_failure_can_be_retried_without_reusing_old_ticket(self):
        old = self.desktop.begin("alpha", "codex-desktop")[0]
        self.assertEqual(self.desktop.fail("alpha", old["ticket"], "桌面工具暂不可用"), "failed")
        self.desktop.retry("alpha", old["ticket"]["task"], "工具已恢复")
        new = self.desktop.begin("alpha", "codex-desktop")[0]
        with self.assertRaises(WorksError):
            self.desktop.fail("alpha", old["ticket"], "旧会话的迟到失败")
        self.assertEqual(self.desktop.complete("alpha", new["ticket"], result()), "completed")

    def test_live_tasks_cannot_be_abandoned_or_exported(self):
        self.desktop.begin("alpha", "codex-desktop")
        with self.assertRaises(WorksError):
            self.desktop.abandon("alpha", "change direction")
        with self.assertRaises(WorksError):
            self.desktop.export("alpha", Path(self.temp.name) / "backup.zip")

    def test_old_store_can_be_resumed_and_backed_up_without_migration(self):
        legacy = Store(self.home)
        task = legacy.ready(legacy.latest("alpha")["id"])[0]
        legacy.claim(task)
        legacy.finish("alpha", task, result=result())
        fresh = Workspace(self.home)
        self.assertEqual(fresh.status("alpha")["stages"][0]["tasks"][0]["status"], "completed")
        fresh.note("alpha", "用户确认使用桌面端")
        archive = fresh.export("alpha", Path(self.temp.name) / "project.zip")
        restored = Workspace(Path(self.temp.name) / "restored")
        restored.restore(archive)
        next_task = restored.begin("alpha", "claude-code-desktop")[0]
        self.assertIn("用户确认使用桌面端", next_task["prompt"])
        self.assertEqual(next_task["ticket"]["task"], legacy.tasks(legacy.latest("alpha")["id"])[1]["id"])

    def test_full_workflow_can_be_completed_by_native_desktop_handoffs(self):
        assigned_roles = set()
        for phase in ("discovery", "product", "design", "build", "launch", "growth"):
            self.desktop.plan("alpha", phase)
            while True:
                tasks = self.desktop.begin("alpha", "claude-code-desktop", max_tasks=3)
                if not tasks:
                    break
                store = self.desktop.store
                specs = {t["id"]: t["spec"] for t in store.tasks(store.latest("alpha")["id"])}
                for task in tasks:
                    assigned_roles.add(task["role"])
                    spec = specs[task["ticket"]["task"]]
                    value = result("pass" if spec.get("gate") else "not_applicable")
                    if spec.get("artifact_prefix"):
                        path = store.workspace("alpha") / spec["artifact_prefix"] / "fixture.txt"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text("Test fixture, not a real product.")
                        value["artifacts"] = [str(path.relative_to(store.workspace("alpha")))]
                    self.desktop.complete("alpha", task["ticket"], value)
            self.assertEqual(self.desktop.status("alpha")["stages"][-1]["status"], "completed")
        self.assertEqual(assigned_roles, {role["id"] for role in load_config()[0]["roles"]})


if __name__ == "__main__":
    unittest.main()
