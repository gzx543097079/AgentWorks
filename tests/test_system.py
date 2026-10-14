import concurrent.futures
import contextlib
import io
import json
import tempfile
import threading
import unittest
import os
import sys
from unittest.mock import patch
import zipfile
from pathlib import Path

from agentworks.backup import restore
from agentworks.cli import export_project
from agentworks.core import Store, WorksError, load_config, validate_result, write_json
from agentworks.runner import packet, run_tasks, submit, role_for, execute


def result(verdict="not_applicable", status="completed"):
    return {"status": status, "summary": "测试夹具：交付完成", "report": "# 离线测试夹具\n不代表真实研究。",
            "verdict": verdict, "evidence": [{"kind": "simulated", "source": "test", "note": "离线夹具"}],
            "artifacts": [], "next_actions": []}


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "data")
        self.store.create("alpha", "测试项目", brief="只测试系统，不做市场研究")

    def tearDown(self):
        self.temp.cleanup()

    def complete(self, task, value=None):
        path = Path(self.temp.name) / "result.json"
        value = value or result("pass" if task["spec"].get("gate") else "not_applicable")
        prefix = task["spec"].get("artifact_prefix")
        if prefix:
            artifact = self.store.workspace("alpha") / prefix / "fixture.txt"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("Offline fixture, not a product implementation.")
            value["artifacts"] = [str(artifact.relative_to(self.store.workspace("alpha")))]
        write_json(path, value)
        return submit(self.store, "alpha", task["id"], path)

    def finish_phase(self, phase):
        run = self.store.plan("alpha", phase)
        while self.store.ready(run["id"]):
            for task in self.store.ready(run["id"]):
                self.complete(task)
        return run

    def test_restart_preserves_progress_and_project_isolation(self):
        run = self.store.plan("alpha", "discovery")
        task = self.store.ready(run["id"])[0]
        self.complete(task)
        self.store.create("beta", "其他产品")
        fresh = Store(self.store.home)
        self.assertEqual(fresh.tasks(run["id"])[0]["status"], "completed")
        self.assertNotEqual(fresh.workspace("alpha"), fresh.workspace("beta"))
        self.assertEqual(fresh.runs("beta"), [])

    def test_plan_is_idempotent_while_in_progress(self):
        a = self.store.plan("alpha", "discovery")
        b = self.store.plan("alpha", "discovery")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(self.store.tasks(a["id"])), 5)

    def test_dependencies_prevent_premature_completion(self):
        run = self.store.plan("alpha", "discovery")
        tasks = self.store.tasks(run["id"])
        with self.assertRaises(WorksError):
            self.complete(tasks[-1])
        self.complete(tasks[0])
        self.assertEqual([t["code"] for t in self.store.ready(run["id"])], ["tools"])

    def test_revision_gate_blocks_next_stage(self):
        run = self.store.plan("alpha", "discovery")
        while True:
            ready = self.store.ready(run["id"])
            if ready[0]["spec"].get("gate"):
                self.complete(ready[0], result("revise"))
                break
            for task in ready:
                self.complete(task)
        self.assertEqual(self.store.run_status(run), "needs_revision")
        with self.assertRaises(WorksError):
            self.store.plan("alpha", "product")

    def test_unvalidated_gate_cannot_pass(self):
        run = self.store.plan("alpha", "discovery")
        for _ in range(4):
            self.complete(self.store.ready(run["id"])[0])
        gate = self.store.ready(run["id"])[0]
        self.assertEqual(self.complete(gate, result()), "needs_revision")

    def test_failed_attempts_are_bounded(self):
        run = self.store.plan("alpha", "discovery")
        task = self.store.ready(run["id"])[0]
        for index in range(3):
            self.store.claim(task)
            self.store.finish("alpha", task, error="工具不可用")
            if index < 2:
                self.store.retry("alpha", task["id"], "已补充输入")
        with self.assertRaises(WorksError):
            self.store.retry("alpha", task["id"], "再次尝试")

    def test_live_project_lock_prevents_duplicate_work(self):
        with self.store.lock("alpha"):
            with self.assertRaises(WorksError):
                self.store.plan("alpha", "discovery")
            with self.assertRaises(WorksError):
                self.store.recover("alpha")

    def test_recover_does_not_blindly_reexecute(self):
        run = self.store.plan("alpha", "discovery")
        task = self.store.ready(run["id"])[0]
        self.store.claim(task)
        self.assertEqual(self.store.recover("alpha"), 1)
        self.assertEqual(self.store.tasks(run["id"])[0]["status"], "failed")

    def test_orphan_live_worker_blocks_recovery(self):
        run = self.store.plan("alpha", "discovery")
        path = self.store.home / "projects/alpha/runs" / str(run["id"]) / "1-process.json"
        write_json(path, {"pid": os.getpid()})
        with self.assertRaises(WorksError):
            self.store.recover("alpha")

    def test_product_creation_requires_real_artifact(self):
        with self.assertRaises(WorksError):
            validate_result(result(), self.store.workspace("alpha"), {"artifact_prefix": "app/"})

    def test_invalid_artifact_paths_and_missing_files_rejected(self):
        workspace = self.store.workspace("alpha")
        outside = Path(self.temp.name) / "private.txt"
        outside.write_text("private")
        (workspace / "link").symlink_to(outside)
        for path in ("../outside", "missing.png", str(outside), "link"):
            value = result()
            value["artifacts"] = [path]
            with self.assertRaises(WorksError):
                validate_result(value, workspace)

    def test_independent_review_packets_do_not_include_peer_answers(self):
        self.finish_phase("discovery")
        self.finish_phase("product")
        run = self.store.plan("alpha", "design")
        self.complete(self.store.ready(run["id"])[0])
        tasks = self.store.ready(run["id"])
        marker = result()
        marker["report"] = "PRIVATE_PEER_OPINION"
        self.complete(tasks[0], marker)
        other_packet = packet(self.store, "alpha", tasks[1])
        self.assertNotIn("PRIVATE_PEER_OPINION", other_packet)
        self.assertIn("prototype", other_packet)

    def test_call_limit_and_read_only_parallelism(self):
        run = self.store.plan("alpha", "discovery")
        barrier = threading.Barrier(2)

        def fake(store, project, current, task, *args):
            store.claim(task)
            barrier.wait(timeout=3)
            return store.finish(project, task, result=result())

        with contextlib.redirect_stdout(io.StringIO()):
            outcomes = run_tasks(self.store, "alpha", max_tasks=2, workers=2, execute_fn=fake)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual([t["code"] for t in self.store.ready(run["id"])], ["channels"])

    def test_writers_are_exclusive(self):
        run = self.store.plan("alpha", "discovery")
        with self.store.db() as db:
            task = self.store.tasks(run["id"])[0]
            task["spec"]["role"] = "developer"
            db.execute("UPDATE tasks SET spec=? WHERE id=?", (json.dumps(task["spec"]), task["id"]))
        active = []
        guard = threading.Lock()

        def fake(store, project, current, task, *args):
            mode = role_for(current, task)["mode"]
            with guard:
                self.assertFalse(mode == "workspace-write" and active)
                self.assertNotIn("workspace-write", active)
                active.append(mode)
            store.claim(task)
            with guard:
                active.remove(mode)
            return store.finish(project, task, result=result())

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(len(run_tasks(self.store, "alpha", max_tasks=2, workers=2, execute_fn=fake)), 2)

    def test_backup_restore_continues_same_workflow(self):
        run = self.store.plan("alpha", "discovery")
        self.complete(self.store.ready(run["id"])[0])
        archive = Path(self.temp.name) / "backup.zip"
        with contextlib.redirect_stdout(io.StringIO()):
            export_project(self.store, "alpha", archive)
        restored = Store(Path(self.temp.name) / "restored")
        self.assertEqual(restore(restored, archive), "alpha")
        self.assertEqual(restored.tasks(run["id"])[0]["status"], "completed")
        self.assertEqual([t["code"] for t in restored.ready(run["id"])], ["tools"])
        self.assertIn("测试项目", (restored.workspace("alpha") / "BRIEF.md").read_text())
        with self.assertRaises(WorksError):
            restore(restored, archive)

    def test_backup_path_traversal_rejected(self):
        archive = Path(self.temp.name) / "bad.zip"
        snapshot = {"format": 1, "project": self.store.project("alpha"), "runs": [], "events": []}
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("snapshot.json", json.dumps(snapshot))
            z.writestr("files/../../escape", "bad")
        with self.assertRaises(WorksError):
            restore(Store(Path(self.temp.name) / "restore-bad"), archive)
        self.assertFalse((Path(self.temp.name) / "escape").exists())

    def test_new_discovery_invalidates_old_product_lineage(self):
        self.finish_phase("discovery")
        self.finish_phase("product")
        self.finish_phase("discovery")
        with self.assertRaises(WorksError):
            self.store.plan("alpha", "design")

    def test_role_snapshot_survives_template_changes(self):
        run = self.store.plan("alpha", "discovery")
        saved = json.loads(run["config"])
        self.assertEqual(len(saved["team"]["roles"]), len(load_config()[0]["roles"]))
        self.assertTrue(all(r["experience_years"] == 20 for r in saved["team"]["roles"]))

    def test_full_offline_pipeline_has_no_implicit_production_action(self):
        for phase in load_config()[1]:
            run = self.finish_phase(phase)
            self.assertEqual(self.store.run_status(run), "completed")
        self.assertEqual(len(self.store.runs("alpha")), 6)

    def fake_codex(self, body):
        binary = Path(self.temp.name) / "codex-stub"
        binary.write_text("#!" + sys.executable + "\n" + body)
        binary.chmod(0o755)
        return patch("agentworks.runner.shutil.which", return_value=str(binary))

    def test_process_adapter_persists_structured_result(self):
        run = self.store.plan("alpha", "discovery")
        task = self.store.ready(run["id"])[0]
        body = "import sys,json,pathlib\nprompt=sys.stdin.read()\nassert '20年' in prompt\nassert sys.argv[sys.argv.index('--sandbox')+1]=='read-only'\npathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(" + repr(json.dumps(result())) + ")\n"
        with self.fake_codex(body):
            self.assertEqual(execute(self.store, "alpha", run, task, 5), "completed")
        self.assertEqual(self.store.tasks(run["id"])[0]["status"], "completed")
        self.assertEqual(list((self.store.home / "projects/alpha/runs").rglob("*-process.json")), [])

    def test_process_failure_is_visible_and_does_not_advance(self):
        run = self.store.plan("alpha", "discovery")
        task = self.store.ready(run["id"])[0]
        with self.fake_codex("import sys\nsys.exit(7)\n"):
            self.assertEqual(execute(self.store, "alpha", run, task, 5), "failed")
        self.assertEqual(self.store.tasks(run["id"])[0]["status"], "failed")
        self.assertNotIn("channels", [t["code"] for t in self.store.ready(run["id"])])

    def test_process_timeout_stops_worker_and_preserves_failure(self):
        run = self.store.plan("alpha", "discovery")
        task = self.store.ready(run["id"])[0]
        with self.fake_codex("import time\ntime.sleep(30)\n"):
            self.assertEqual(execute(self.store, "alpha", run, task, 1), "failed")
        self.assertIn("超时", self.store.tasks(run["id"])[0]["error"])


if __name__ == "__main__":
    unittest.main()
