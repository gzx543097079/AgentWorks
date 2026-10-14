"""用户确认和交付版本的离线测试，不代表实际用户审批。"""
import json
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from pathlib import Path

from agentworks.core import WorksError, write_json
from agentworks.desktop import Workspace
from agentworks.handoff import placement, submit


def result(verdict="not_applicable"):
    return {"status": "completed", "summary": "离线确认测试", "report": "测试交付，不代表实际研究。",
            "verdict": verdict, "evidence": [], "artifacts": [], "next_actions": []}


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "data"
        self.desktop = Workspace(self.home)
        self.desktop.create("alpha", "确认关卡测试")

    def tearDown(self):
        self.temp.cleanup()

    def stage(self):
        current = self.desktop.store.latest("alpha")["id"]
        return next(stage for stage in self.desktop.status("alpha")["stages"] if stage["id"] == current)

    def deliver(self, assignments):
        for assignment in assignments:
            task = next(t for t in self.stage()["tasks"] if t["id"] == assignment["ticket"]["task"])
            value = result("pass" if task["spec"].get("gate") else "not_applicable")
            if task["spec"].get("artifact_prefix"):
                path = self.desktop.store.workspace("alpha") / task["spec"]["artifact_prefix"] / "fixture.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("版本测试夹具", encoding="utf-8")
                value["artifacts"] = [str(path.relative_to(self.desktop.store.workspace("alpha")))]
            self.desktop.complete("alpha", assignment["ticket"], value)

    def first_confirmation(self):
        for phase in ("discovery", "product", "design", "build", "launch"):
            self.desktop.plan("alpha", phase)
            for _ in range(100):
                tasks = self.stage()["tasks"]
                done = {t["code"] for t in tasks if t["status"] == "completed"}
                gate = next((t for t in tasks if t["spec"].get("user_confirmation") and set(t["spec"]["depends"]) <= done), None)
                if gate:
                    return gate
                assigned = self.desktop.begin("alpha", "codex-desktop", max_tasks=3)
                if not assigned:
                    break
                self.deliver(assigned)
        self.fail("工作流必须包含用户确认关卡")

    def test_confirmation_cannot_be_dispatched_claimed_or_submitted(self):
        gate = self.first_confirmation()
        store = self.desktop.store
        self.assertNotIn(gate["id"], [t["id"] for t in store.ready(store.latest("alpha")["id"])])
        with self.assertRaises(WorksError):
            store.claim(gate)
        with self.assertRaises(WorksError):
            store.finish("alpha", gate, result=result("pass"))
        path = Path(self.temp.name) / "forged.json"
        path.write_text('{}')
        with self.assertRaises(WorksError):
            submit(store, "alpha", gate["id"], path)
        review = self.desktop.review("alpha", gate["id"])
        self.assertEqual(self.stage()["status"], "awaiting_user_confirmation")
        with self.assertRaises(WorksError):
            self.desktop.plan("alpha", "design")
        self.assertEqual(review["product_version"], "0.1.0")

    def test_review_and_feedback_survive_new_desktop_session(self):
        gate = self.first_confirmation()
        review = self.desktop.review("alpha", gate["id"])
        fresh = Workspace(self.home)
        self.assertEqual(fresh.review("alpha", gate["id"])["digest"], review["digest"])
        for feedback in ("", "   "):
            with self.assertRaises(WorksError):
                fresh.confirm("alpha", gate["id"], review["digest"], "approve", feedback)
        with self.assertRaises(WorksError):
            fresh.confirm("alpha", gate["id"], "old-digest", "approve", "批准旧版")
        fresh.confirm("alpha", gate["id"], review["digest"], "defer", "稍后决定")
        self.assertEqual(self.stage()["status"], "awaiting_user_confirmation")
        fresh.confirm("alpha", gate["id"], review["digest"], "approve", "明确批准当前版本")
        saved = next(t for t in self.stage()["tasks"] if t["id"] == gate["id"])
        self.assertEqual(saved["status"], "completed")

    def test_pending_review_requires_revision_and_reevaluation_after_file_changes(self):
        gate = self.first_confirmation()
        review = self.desktop.review("alpha", gate["id"])
        source = next(t for t in self.stage()["tasks"] if t["code"] == "scope")
        name = placement(self.desktop.store, "alpha", source)["report"]
        path = self.desktop.store.workspace("alpha") / name
        path.write_text(path.read_text(encoding="utf-8") + "\n修订后内容", encoding="utf-8")
        with self.assertRaises(WorksError):
            self.desktop.confirm("alpha", gate["id"], review["digest"], "approve", "不能批准旧预览")
        with self.assertRaises(WorksError):
            self.desktop.review("alpha", gate["id"])
        self.desktop.revise("alpha", source["id"], "修改范围并重新验收")
        self.deliver(self.desktop.begin("alpha", "codex-desktop"))
        refreshed = self.desktop.review("alpha", gate["id"])
        self.assertNotEqual(refreshed["digest"], review["digest"])
        with self.assertRaises(WorksError):
            self.desktop.confirm("alpha", gate["id"], review["digest"], "approve", "旧版本失效")
        self.desktop.confirm("alpha", gate["id"], refreshed["digest"], "approve", "批准新版本")

    def test_changed_approved_delivery_blocks_begin_and_next_stage(self):
        gate = self.first_confirmation()
        review = self.desktop.review("alpha", gate["id"])
        self.desktop.confirm("alpha", gate["id"], review["digest"], "approve", "批准当前快照")
        dependency = next(t for t in self.stage()["tasks"] if t["code"] in gate["spec"]["depends"] and t.get("result"))
        # Published reports are part of the reviewed dependency evidence.
        from agentworks.handoff import placement
        report = self.desktop.store.workspace("alpha") / placement(self.desktop.store, "alpha", dependency)["report"]
        report.write_text("确认后未经复核的修改", encoding="utf-8")
        with self.assertRaises(WorksError):
            self.desktop.begin("alpha", "codex-desktop")
        with self.assertRaises(WorksError):
            self.desktop.plan("alpha", "design")

    def test_revision_resets_downstream_and_keeps_attempt_history(self):
        gate = self.first_confirmation()
        review = self.desktop.review("alpha", gate["id"])
        self.desktop.confirm("alpha", gate["id"], review["digest"], "revise", "需要调整范围")
        self.assertEqual(self.stage()["status"], "needs_revision")
        tasks = self.stage()["tasks"]
        source = next(t for t in tasks if t["code"] in gate["spec"]["depends"] and not t["spec"].get("user_confirmation"))
        snapshot = json.loads(source["snapshot"])
        archive = self.home / "projects/alpha" / snapshot["archive"]
        before = {p: p.read_bytes() for p in archive.rglob("*") if p.is_file()}
        self.assertTrue(before)
        self.desktop.revise("alpha", source["id"], "按用户意见修订")
        saved = {t["id"]: t for t in self.stage()["tasks"]}
        self.assertEqual(saved[source["id"]]["status"], "pending")
        self.assertEqual(saved[source["id"]]["attempts"], source["attempts"])
        self.assertIsNone(saved[source["id"]]["result"])
        self.assertEqual(saved[gate["id"]]["status"], "pending")
        self.assertFalse(saved[gate["id"]].get("review"))
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        with self.assertRaises(WorksError):
            self.desktop.confirm("alpha", gate["id"], review["digest"], "approve", "旧快照不能批准")
        self.deliver(self.desktop.begin("alpha", "codex-desktop"))
        redelivered = next(t for t in self.stage()["tasks"] if t["id"] == source["id"])
        current = json.loads(redelivered["snapshot"])
        self.assertEqual(current["revision"], snapshot["revision"] + 1)
        self.assertNotEqual(current["archive"], snapshot["archive"])
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_revision_numbers_keep_increasing_without_exhausting_failure_retries(self):
        self.desktop.plan("alpha", "discovery")
        assignment = self.desktop.begin("alpha", "codex-desktop")[0]
        source_id = assignment["ticket"]["task"]
        for revision in range(1, 5):
            self.assertEqual(assignment["ticket"]["attempt"], revision)
            self.deliver([assignment])
            self.desktop.revise("alpha", source_id, "离线测试：交付新修订")
            assignment = self.desktop.begin("alpha", "codex-desktop")[0]
        self.desktop.fail("alpha", assignment["ticket"], "离线测试：工具失败")
        self.desktop.retry("alpha", source_id, "工具恢复")
        assignment = self.desktop.begin("alpha", "codex-desktop")[0]
        self.assertEqual(assignment["ticket"]["attempt"], 6)
        self.deliver([assignment])

    def test_product_version_rejects_changes_during_unfinished_stage(self):
        self.desktop.set_version("alpha", "0.2.0")
        self.assertEqual(self.desktop.status("alpha")["project"]["product_version"], "0.2.0")
        with self.assertRaises(WorksError):
            self.desktop.set_version("alpha", "v2")
        self.desktop.plan("alpha", "discovery")
        with self.assertRaises(WorksError):
            self.desktop.set_version("alpha", "0.3.0")
        assigned = self.desktop.begin("alpha", "codex-desktop")
        with self.assertRaises(WorksError):
            self.desktop.set_version("alpha", "0.3.0")
        self.deliver(assigned)
        for _ in range(100):
            assigned = self.desktop.begin("alpha", "codex-desktop", max_tasks=3)
            if not assigned:
                break
            self.deliver(assigned)
        self.assertEqual(self.stage()["status"], "completed")
        self.desktop.set_version("alpha", "0.3.0")
        self.assertEqual(self.desktop.status("alpha")["project"]["product_version"], "0.3.0")

    def approve_scope(self):
        gate = self.first_confirmation()
        review = self.desktop.review("alpha", gate["id"])
        self.desktop.confirm("alpha", gate["id"], review["digest"], "approve", "离线夹具：批准范围")
        return gate, review

    def test_user_revision_cannot_retry_or_revise_only_confirmation(self):
        gate = self.first_confirmation()
        review = self.desktop.review("alpha", gate["id"])
        self.desktop.confirm("alpha", gate["id"], review["digest"], "revise", "请修改实际上游交付")
        for action in (self.desktop.retry, self.desktop.revise):
            with self.subTest(action=action.__name__), self.assertRaises(WorksError):
                action("alpha", gate["id"], "仅重置确认关卡")
        saved = next(t for t in self.stage()["tasks"] if t["id"] == gate["id"])
        self.assertEqual(saved["status"], "needs_revision")
        self.assertEqual(json.loads(saved["review"])["digest"], review["digest"])

    def test_portable_submit_cannot_bypass_changed_approved_inputs(self):
        gate, review = self.approve_scope()
        self.desktop.plan("alpha", "design")
        report = self.desktop.store.workspace("alpha") / next(iter(review["files"]))
        report.write_text("未经批准的范围变更", encoding="utf-8")
        store = self.desktop.store
        task = store.ready(store.latest("alpha")["id"])[0]
        artifact = store.workspace("alpha") / task["spec"]["artifact_prefix"] / "fixture.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("原型测试夹具", encoding="utf-8")
        value = result()
        value["artifacts"] = [str(artifact.relative_to(store.workspace("alpha")))]
        output = Path(self.temp.name) / "result.json"
        write_json(output, value)
        with self.assertRaises(WorksError):
            submit(store, "alpha", task["id"], output)
        self.assertEqual(next(t for t in store.tasks(task["run"]) if t["id"] == task["id"])["status"], "pending")
        self.assertTrue(next(r for r in store.runs("alpha") if r["id"] == task["run"])["abandoned"])

    def test_snapshot_write_failure_allows_same_ticket_correction(self):
        self.desktop.plan("alpha", "discovery")
        assignment = self.desktop.begin("alpha", "codex-desktop")[0]
        ticket = assignment["ticket"]
        archive = self.home / "projects/alpha/runs" / str(ticket["run"]) / (str(ticket["task"]) + "-v1")
        with patch("agentworks.versions.write_json", side_effect=OSError("模拟快照清单保存失败")):
            with self.assertRaises(OSError):
                self.desktop.complete("alpha", ticket, result())
        self.assertFalse(archive.exists())
        self.assertEqual(self.desktop.complete("alpha", ticket, result()), "completed")
        self.assertTrue((archive / "manifest.json").is_file())

    def test_new_file_in_approved_directory_requires_confirmation(self):
        self.approve_scope()
        self.desktop.plan("alpha", "design")
        self.deliver(self.desktop.begin("alpha", "codex-desktop"))
        gate = next(t for t in self.stage()["tasks"] if t["code"] == "prototype_confirmation")
        review = self.desktop.review("alpha", gate["id"])
        self.desktop.confirm("alpha", gate["id"], review["digest"], "approve", "离线夹具：批准原型")
        path = self.desktop.store.workspace("alpha") / "design/wireframe/added.txt"
        path.write_text("新增页面未获确认", encoding="utf-8")
        with self.assertRaises(WorksError):
            self.desktop.begin("alpha", "codex-desktop")

    def test_confirmation_and_snapshots_survive_format_two_backup(self):
        gate = self.first_confirmation()
        review = self.desktop.review("alpha", gate["id"])
        archive = self.desktop.export("alpha", Path(self.temp.name) / "confirmations.zip")
        with zipfile.ZipFile(archive) as backup:
            self.assertEqual(json.loads(backup.read("snapshot.json"))["format"], 2)
        restored = Workspace(Path(self.temp.name) / "restored")
        restored.restore(archive)
        restored_stage = restored.status("alpha")["stages"][-1]
        self.assertEqual(restored_stage["status"], "awaiting_user_confirmation")
        saved = next(t for t in restored_stage["tasks"] if t["id"] == gate["id"])
        self.assertEqual(json.loads(saved["review"])["digest"], review["digest"])
        review_archive = restored.store.home / "projects/alpha" / review["archive"]
        self.assertTrue((review_archive / "manifest.json").is_file())
        for name in review["files"]:
            self.assertEqual((review_archive / "files" / name).read_bytes(), (self.desktop.store.workspace("alpha") / name).read_bytes())
        deliveries = [json.loads(t["snapshot"]) for t in restored_stage["tasks"] if t.get("snapshot")]
        self.assertTrue(deliveries)
        for delivery in deliveries:
            self.assertTrue((restored.store.home / "projects/alpha" / delivery["archive"] / "manifest.json").is_file())
        restored.confirm("alpha", gate["id"], review["digest"], "approve", "恢复后明确批准该版本")
        restored.plan("alpha", "design")

    def test_new_product_version_cannot_use_old_scope_approval(self):
        gate, review = self.approve_scope()
        self.desktop.set_version("alpha", "0.2.0")
        with self.assertRaises(WorksError):
            self.desktop.plan("alpha", "design")
        saved = next(t for t in self.stage()["tasks"] if t["id"] == gate["id"])
        self.assertEqual(json.loads(saved["review"])["product_version"], "0.1.0")
        self.desktop.plan("alpha", "product")
        self.assertEqual(json.loads(self.desktop.store.latest("alpha")["config"])["product_version"], "0.2.0")

    def finish_phase(self, phase):
        self.desktop.plan("alpha", phase)
        for _ in range(150):
            run = self.desktop.store.latest("alpha")
            tasks = self.desktop.store.tasks(run["id"])
            done = {t["code"] for t in tasks if t["status"] == "completed"}
            for gate in tasks:
                if (gate["spec"].get("user_confirmation") and gate["status"] in ("pending", "awaiting_user_confirmation")
                        and set(gate["spec"]["depends"]) <= done):
                    preview = self.desktop.review("alpha", gate["id"])
                    self.desktop.confirm("alpha", gate["id"], preview["digest"], "approve", "离线夹具明确批准")
            assignments = self.desktop.begin("alpha", "codex-desktop", max_tasks=3)
            if assignments:
                self.deliver(assignments)
            elif self.desktop.store.run_status(run) == "completed":
                return run
            else:
                self.fail("离线流程异常阻塞")
        self.fail("离线流程未收敛")

    def test_cross_phase_revision_invalidates_reviews_and_resumes_in_new_session(self):
        for phase in ("discovery", "product", "design", "build", "launch"):
            self.finish_phase(phase)
        store = self.desktop.store
        design = store.latest("alpha", "design")
        before = {t["code"]: t for t in store.tasks(design["id"])}
        old_ui = json.loads(before["ui_confirmation"]["review"])
        self.desktop.revise("alpha", before["revision"]["id"], "批准后调整 UI")
        fresh = Workspace(self.home)
        tasks = {t["code"]: t for t in fresh.store.tasks(design["id"])}
        for code in ("prototype", "expert", "newcomer", "value", "locale", "user_validation", "expert_recheck",
                     "revision_triage", "design_gate", "ui_confirmation"):
            self.assertEqual(tasks[code]["status"], "pending", code)
            self.assertIsNone(tasks[code]["result"], code)
        self.assertEqual(tasks["prototype_confirmation"]["status"], "completed")
        self.assertTrue(all(r["abandoned"] for r in fresh.store.runs("alpha") if r["phase"] in ("build", "launch")))
        with self.assertRaises(WorksError):
            fresh.confirm("alpha", before["ui_confirmation"]["id"], old_ui["digest"], "approve", "旧批准不可复用")
        with self.assertRaises(WorksError):
            fresh.plan("alpha", "build")
        self.desktop = fresh
        self.finish_phase("design")
        current = next(t for t in fresh.store.tasks(design["id"]) if t["code"] == "ui_confirmation")
        self.assertNotEqual(json.loads(current["review"])["digest"], old_ui["digest"])
        self.finish_phase("build")
        self.assertNotEqual(fresh.store.latest("alpha", "build")["id"], next(r["id"] for r in fresh.store.runs("alpha") if r["phase"] == "build"))

    def test_invalidated_approval_cannot_revive_when_files_are_restored(self):
        gate, preview = self.approve_scope()
        path = self.desktop.store.workspace("alpha") / next(iter(preview["files"]))
        content = path.read_bytes()
        path.write_bytes(content + b"changed")
        with self.assertRaises(WorksError):
            self.desktop.begin("alpha", "codex-desktop")
        path.write_bytes(content)
        fresh = Workspace(self.home)
        saved = next(t for t in fresh.store.tasks(fresh.store.latest("alpha")["id"]) if t["id"] == gate["id"])
        self.assertEqual(saved["status"], "needs_revision")
        self.assertEqual(json.loads(saved["review"])["decision"], "invalidated")
        with self.assertRaises(WorksError):
            fresh.plan("alpha", "design")

    def test_new_upstream_round_retires_all_old_downstream_runs(self):
        for phase in ("discovery", "product", "design", "build"):
            self.finish_phase(phase)
        self.desktop.plan("alpha", "product")
        store = self.desktop.store
        self.assertTrue(all(r["abandoned"] for r in store.runs("alpha") if r["phase"] in ("design", "build")))
        self.assertEqual(store.latest("alpha")["phase"], "product")
        with self.assertRaises(WorksError):
            store.latest("alpha", "design")

    def test_review_input_changes_while_worker_runs_reject_delivery(self):
        self.approve_scope()
        self.desktop.plan("alpha", "design")
        self.deliver(self.desktop.begin("alpha", "codex-desktop"))
        gate = next(t for t in self.stage()["tasks"] if t["code"] == "prototype_confirmation")
        preview = self.desktop.review("alpha", gate["id"])
        self.desktop.confirm("alpha", gate["id"], preview["digest"], "approve", "离线批准")
        source = self.desktop.begin("alpha", "codex-desktop")[0]
        path = self.desktop.store.workspace("alpha") / "design/wireframe/fixture.txt"
        path.write_text("任务执行期间变更", encoding="utf-8")
        with self.assertRaises(WorksError):
            self.desktop.complete("alpha", source["ticket"], result())
        fresh = Workspace(self.home)
        self.assertEqual(next(t for t in fresh.store.tasks(fresh.store.latest("alpha")["id"]) if t["id"] == source["ticket"]["task"])["status"], "running")
        fresh.fail("alpha", source["ticket"], "输入已过期，旧结果取消")
        self.assertEqual(fresh.recover("alpha", workers_stopped=True, reason="旧 worker 停止"), 0)

    def test_interrupted_completion_after_snapshot_can_resume_same_ticket(self):
        self.desktop.plan("alpha", "discovery")
        assignment = self.desktop.begin("alpha", "codex-desktop")[0]
        with patch.object(self.desktop.store, "finish", side_effect=OSError("模拟快照之后进程中断")):
            with self.assertRaises(OSError):
                self.desktop.complete("alpha", assignment["ticket"], result())
        fresh = Workspace(self.home)
        self.assertEqual(fresh.complete("alpha", assignment["ticket"], result()), "completed")

    def test_revising_ui_cannot_skip_modified_version_independent_reviews(self):
        for phase in ("discovery", "product", "design"):
            self.finish_phase(phase)
        tasks = {t["code"]: t for t in self.stage()["tasks"]}
        self.desktop.revise("alpha", tasks["revision"]["id"], "修改已经通过的 UI")
        pending = {t["code"]: t for t in self.stage()["tasks"]}
        for code in ("expert", "newcomer", "value", "expert_recheck", "newcomer_recheck", "value_recheck"):
            self.assertEqual(pending[code]["status"], "pending")
        self.assertEqual(pending["ui_confirmation"]["status"], "pending")
        with self.assertRaises(WorksError):
            self.desktop.review("alpha", pending["ui_confirmation"]["id"])

    def test_deferred_feedback_is_preserved_on_repeated_review_after_restart(self):
        gate = self.first_confirmation()
        preview = self.desktop.review("alpha", gate["id"])
        self.desktop.confirm("alpha", gate["id"], preview["digest"], "defer", "周五再决定")
        fresh = Workspace(self.home)
        returned = fresh.review("alpha", gate["id"])
        self.assertEqual(returned["decision"], "defer")
        self.assertEqual(returned["feedback"], "周五再决定")
        self.assertEqual(returned["digest"], preview["digest"])
        self.assertEqual(fresh.status("alpha")["current_stage"], preview["run"])

    def test_final_ui_with_actual_changed_content_requires_and_passes_fresh_reviews(self):
        for phase in ("discovery", "product"):
            self.finish_phase(phase)
        self.desktop.plan("alpha", "design")
        store = self.desktop.store
        revision_id = next(t["id"] for t in self.stage()["tasks"] if t["code"] == "revision")
        changed = False
        for _ in range(120):
            assignments = self.desktop.begin("alpha", "codex-desktop", max_tasks=3)
            if assignments:
                for assignment in assignments:
                    if assignment["ticket"]["task"] == revision_id:
                        (store.workspace("alpha") / "design/prototype/fixture.txt").unlink()
                        artifact = store.workspace("alpha") / "design/prototype/revised.txt"
                        artifact.write_text("v2 真实变更后的原型内容", encoding="utf-8")
                        value = result()
                        value["artifacts"] = ["design/prototype/revised.txt"]
                        self.desktop.complete("alpha", assignment["ticket"], value)
                        changed = True
                    else:
                        self.deliver([assignment])
            else:
                tasks = self.stage()["tasks"]
                done = {t["code"] for t in tasks if t["status"] == "completed"}
                gates = [t for t in tasks if t["spec"].get("user_confirmation") and t["status"] == "pending"
                         and set(t["spec"]["depends"]) <= done]
                if not gates:
                    break
                for gate in gates:
                    preview = self.desktop.review("alpha", gate["id"])
                    if gate["code"] == "ui_confirmation":
                        self.assertTrue(changed)
                        self.assertTrue(all(t["status"] == "completed" for t in tasks if t["code"].endswith("_recheck")))
                        self.assertEqual((store.workspace("alpha") / "design/prototype/revised.txt").read_text(), "v2 真实变更后的原型内容")
                    self.desktop.confirm("alpha", gate["id"], preview["digest"], "approve", "批准当前真实修订版")
        self.assertTrue(changed)
        self.assertEqual(store.run_status(store.latest("alpha")), "completed")

    def test_revision_invalidation_history_survives_backup_and_restoration(self):
        for phase in ("discovery", "product", "design", "build"):
            self.finish_phase(phase)
        store = self.desktop.store
        design = store.latest("alpha", "design")
        source = next(t for t in store.tasks(design["id"]) if t["code"] == "revision")
        self.desktop.revise("alpha", source["id"], "回归测试：跨阶段修改")
        archive = self.desktop.export("alpha", Path(self.temp.name) / "revised.zip")
        fresh = Workspace(Path(self.temp.name) / "revised-restored")
        fresh.restore(archive)
        self.assertEqual(fresh.status("alpha")["current_stage"], design["id"])
        self.assertTrue(next(r for r in fresh.store.runs("alpha") if r["phase"] == "build")["abandoned"])
        self.assertTrue(any(event["kind"] == "delivery_invalidated" for event in fresh.history("alpha")))
        self.assertTrue(any(event["kind"] == "superseded" for event in fresh.history("alpha")))
        with self.assertRaises(WorksError):
            fresh.plan("alpha", "launch")

    def test_confirmation_report_cannot_diverge_from_saved_human_decision(self):
        gate, preview = self.approve_scope()
        saved = next(t for t in self.stage()["tasks"] if t["id"] == gate["id"])
        report = self.desktop.store.workspace("alpha") / placement(self.desktop.store, "alpha", saved)["report"]
        report.write_text("替换后的批准内容", encoding="utf-8")
        with self.assertRaises(WorksError):
            self.desktop.begin("alpha", "codex-desktop")
        fresh = Workspace(self.home)
        stored = next(t for t in fresh.store.tasks(fresh.store.latest("alpha")["id"]) if t["id"] == gate["id"])
        self.assertEqual(stored["status"], "needs_revision")
        self.assertEqual(json.loads(stored["review"])["decision"], "invalidated")
        with self.assertRaises(WorksError):
            fresh.plan("alpha", "design")
