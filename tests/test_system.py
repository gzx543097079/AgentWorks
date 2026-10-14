import contextlib
import io
import json
import tempfile
import unittest
import os
import zipfile
from pathlib import Path

from agentworks.backup import restore, export_project
from agentworks.core import Store, WorksError, load_config, validate_result, write_json
from agentworks.handoff import packet, submit
from agentworks.desktop import Workspace


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

    def confirm_ready(self, run):
        tasks = self.store.tasks(run["id"])
        done = {t["code"] for t in tasks if t["status"] == "completed"}
        for task in tasks:
            if task["spec"].get("user_confirmation") and task["status"] == "pending" and set(task["spec"]["depends"]) <= done:
                desktop = Workspace(self.store.home)
                review = desktop.review("alpha", task["id"])
                desktop.confirm("alpha", task["id"], review["digest"], "approve", "离线测试夹具：明确批准此交付版本")
                return True
        return False

    def finish_phase(self, phase):
        run = self.store.plan("alpha", phase)
        while True:
            ready = self.store.ready(run["id"])
            if not ready and not self.confirm_ready(run):
                break
            for task in ready:
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
        self.assertEqual(len(self.store.tasks(a["id"])), len(load_config()[1]["discovery"]["tasks"]))

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
        while not self.store.ready(run["id"])[0]["spec"].get("gate"):
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
        while not any(t["code"] == "expert" for t in self.store.ready(run["id"])):
            ready = self.store.ready(run["id"])
            if ready:
                self.complete(ready[0])
            else:
                self.assertTrue(self.confirm_ready(run))
        tasks = {t["code"]: t for t in self.store.ready(run["id"])}
        marker = result()
        marker["report"] = "PRIVATE_PEER_OPINION"
        self.complete(tasks["expert"], marker)
        other_packet = packet(self.store, "alpha", tasks["newcomer"])
        self.assertNotIn("PRIVATE_PEER_OPINION", other_packet)
        self.assertIn("prototype", other_packet)

    def assert_review_blocks_acceptance(self, gate_code, verdict):
        for phase in ("discovery", "product", "design"):
            self.finish_phase(phase)
        run = self.store.plan("alpha", "build")
        while not any(t["code"] == gate_code for t in self.store.ready(run["id"])):
            for task in self.store.ready(run["id"]):
                self.complete(task)
        tasks = {t["code"]: t for t in self.store.tasks(run["id"])}
        self.complete(tasks[gate_code], result(verdict))
        other_code = "security_gate" if gate_code == "code_gate" else "code_gate"
        self.complete(tasks[other_code])
        self.assertEqual(self.store.ready(run["id"]), [])
        with self.assertRaises(WorksError):
            self.complete(tasks["acceptance"])
        with self.assertRaises(WorksError):
            self.store.plan("alpha", "launch")
        self.store.retry("alpha", tasks[gate_code]["id"], "离线夹具：已补充该检查所需的验证证据")
        self.complete(self.store.ready(run["id"])[0], result("pass"))
        self.assertEqual([t["code"] for t in self.store.ready(run["id"])], ["acceptance"])

    def test_code_review_revision_prevents_final_acceptance(self):
        self.assert_review_blocks_acceptance("code_gate", "revise")

    def test_security_review_block_prevents_final_acceptance(self):
        self.assert_review_blocks_acceptance("security_gate", "blocked")

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



if __name__ == "__main__":
    unittest.main()
