import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentworks.backends import build_command, read_response, resolve_backend
from agentworks.cli import main
from agentworks.core import ROOT, Store, WorksError, write_json
from agentworks.runner import execute, packet, run_tasks, submit
from scripts.sync_agents import synchronize


def fixture():
    return {"status": "completed", "summary": "离线交接夹具", "report": "测试报告，不代表真实研究。",
            "verdict": "not_applicable", "evidence": [], "artifacts": [], "next_actions": []}


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "data")
        self.store.create("alpha", "跨平台测试")
        self.run = self.store.plan("alpha", "discovery")

    def tearDown(self):
        self.temp.cleanup()

    def fake_cli(self, backend, body):
        binary = self.root / backend
        binary.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
        binary.chmod(0o755)
        return str(binary)

    def test_backend_resolution_does_not_silently_switch_accounts(self):
        with patch("agentworks.backends.shutil.which", side_effect=lambda n: "/bin/" + n if n == "claude" else None):
            self.assertEqual(resolve_backend(), "claude")
            with self.assertRaises(WorksError):
                resolve_backend("codex")
        for available in (None, "/bin/fake"):
            with patch("agentworks.backends.shutil.which", return_value=available):
                with self.assertRaises(WorksError):
                    resolve_backend()

    def test_claude_command_limits_tools_and_scopes_writes(self):
        with patch("agentworks.backends.shutil.which", return_value="/bin/claude"):
            for writable in (False, True):
                cmd = build_command(self.store.workspace("alpha"), self.root / "out", model="selected-model",
                                    search=False, writable=writable, backend="claude")
                self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
                tools = cmd[cmd.index("--tools") + 1].split(",")
                self.assertNotIn("Bash", tools)
                self.assertNotIn("Agent", tools)
                self.assertNotIn("WebSearch", tools)
                self.assertEqual("Write" in tools, writable)
                allowed = cmd[cmd.index("--allowedTools") + 1].split(",")
                self.assertNotIn("Write", allowed)
                if writable:
                    self.assertIn("Write(./app/**)", allowed)
                self.assertEqual(cmd[cmd.index("--model") + 1], "selected-model")
                self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1])["type"], "object")

    def test_claude_envelope_errors_and_denials_do_not_pass(self):
        output = self.root / "stdout.json"
        for value in ([fixture()], {"result": json.dumps(fixture())},
                      {"is_error": True, "structured_output": fixture()},
                      {"subtype": "error_max_turns", "structured_output": fixture()},
                      {"permission_denials": [{"tool": "Write"}], "structured_output": fixture()}):
            write_json(output, value)
            with self.assertRaises(WorksError):
                read_response("claude", self.root / "unused.json", output)
        value = fixture()
        value["status"] = "blocked"
        write_json(output, {"permission_denials": [{"tool": "Write"}], "structured_output": value})
        self.assertEqual(read_response("claude", self.root / "unused.json", output)["status"], "blocked")

    def test_cross_backend_and_manual_handoff_share_existing_progress(self):
        codex = self.fake_cli("codex", "import sys,pathlib\nprompt=sys.stdin.read()\npathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(" + repr(json.dumps(fixture())) + ")\n")
        envelope = {"type": "result", "subtype": "success", "is_error": False, "structured_output": fixture()}
        claude = self.fake_cli("claude", "import sys,pathlib\nprompt=sys.stdin.read()\nassert pathlib.Path('BRIEF.md').is_file()\nassert 'output_schema' in prompt\nprint(" + repr(json.dumps(envelope)) + ")\n")
        with patch("agentworks.backends.shutil.which", side_effect={"codex": codex, "claude": claude}.get):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_tasks(self.store, "alpha", backend="codex")[0][1], "completed")
                fresh = Store(self.store.home)
                self.assertEqual(run_tasks(fresh, "alpha", backend="claude")[0][1], "completed")
        task = self.store.ready(self.run["id"])[0]
        content = packet(self.store, "alpha", task)
        self.assertEqual(task["code"], "channels")
        self.assertIn("测试报告", content)
        self.assertIn('"output_schema"', content)
        path = self.root / "manual.json"
        write_json(path, fixture())
        self.assertEqual(submit(fresh, "alpha", task["id"], path), "completed")
        completed = [t for t in fresh.tasks(self.run["id"]) if t["status"] == "completed"]
        self.assertEqual(len(completed), 3)
        self.assertTrue(all(t["attempts"] == 1 for t in completed))
        logs = list((self.store.home / "projects/alpha/runs").rglob("*-execution.json"))
        self.assertEqual({json.loads(p.read_text())["backend"] for p in logs}, {"codex", "claude"})

    def test_claude_failure_retains_task_for_explicit_retry(self):
        binary = self.fake_cli("claude", "import sys,json\nsys.stdin.read()\nprint(json.dumps({'is_error': True, 'result': 'failed'}))\n")
        task = self.store.ready(self.run["id"])[0]
        with patch("agentworks.backends.shutil.which", return_value=binary):
            self.assertEqual(execute(self.store, "alpha", self.run, task, 5, backend="claude"), "failed")
        saved = self.store.tasks(self.run["id"])[0]
        self.assertEqual(saved["attempts"], 1)
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(list(self.store.home.rglob("*-process.json")), [])

    def test_preview_does_not_require_either_cli(self):
        with patch("agentworks.backends.shutil.which", return_value=None), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--data-dir", str(self.store.home), "run", "alpha", "--backend", "claude"]), 0)
        self.assertTrue(all(t["attempts"] == 0 for t in self.store.tasks(self.run["id"])))

    def test_missing_backend_does_not_claim_or_consume_task_attempt(self):
        with patch("agentworks.backends.shutil.which", return_value=None):
            with self.assertRaises(WorksError):
                run_tasks(self.store, "alpha", backend="claude")
        self.assertTrue(all(t["attempts"] == 0 for t in self.store.tasks(self.run["id"])))

    def test_generation_removes_retired_roles_but_preserves_custom_roles(self):
        root = self.root / "config-repo"
        for source in ("config/team.json", ".agents/skills/agentworks/SKILL.md"):
            path = root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, path)
        synchronize(root)
        self.assertEqual(len(list((root / "roles").glob("*.md"))), 15)
        custom = root / ".claude/agents/custom.md"
        custom.write_text("A user-authored custom role")
        team = json.loads((root / "config/team.json").read_text())
        removed = team["roles"].pop()
        write_json(root / "config/team.json", team)
        drift = synchronize(root, check=True)
        self.assertTrue(any(removed["id"] in name for name in drift))
        synchronize(root)
        self.assertFalse((root / "roles" / (removed["id"] + ".md")).exists())
        self.assertTrue(custom.exists())
        self.assertEqual(synchronize(root, check=True), [])


if __name__ == "__main__":
    unittest.main()
