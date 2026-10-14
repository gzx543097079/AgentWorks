import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agentworks.core import WorksError
from agentworks.install import ENGINE, install, verify

EMBEDDED_RUN = """
import json, sys
sys.path.insert(0, ".agentworks/engine")
from agentworks.desktop import Workspace
team = Workspace()
check = team.check()
team.create("cleaner", "清理工具", kind="tool")
team.plan("cleaner", "discovery")
task = team.begin("cleaner", "claude-code-desktop")[0]
try:
    team.create("other", "第二个项目")
    second = "allowed"
except Exception as exc:
    second = str(exc)
print(json.dumps({"check": check, "workspace": team.status("cleaner")["workspace"],
                  "prompt": task["prompt"], "second": second}, ensure_ascii=False))
"""


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "Cleaner"
        self.project.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_install_keeps_user_rules_and_is_idempotent(self):
        (self.project / "AGENTS.md").write_text("# 我的规则\n", encoding="utf-8")
        (self.project / ".gitignore").write_text("*.sqlite3\n", encoding="utf-8")
        install(self.project)
        rules = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(rules.startswith("# 我的规则\n"))
        self.assertEqual(rules.count("<!-- agentworks:start -->"), 1)
        self.assertIn("@AGENTS.md", (self.project / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertEqual(len(list((self.project / ".claude/agents").glob("agentworks-*.md"))), 27)
        self.assertEqual(len(list((self.project / ".codex/agents").glob("agentworks-*.toml"))), 27)
        skill = (self.project / ".agents/skills/agentworks/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("../../../" + ENGINE + "/docs/", skill)
        self.assertTrue((self.project / ENGINE / "docs/团队运行手册.md").is_file())
        version = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
        self.assertIn("AgentWorks " + version, rules)
        self.assertEqual(json.loads((self.project / ENGINE / "install.json").read_text(encoding="utf-8"))["version"], version)
        self.assertEqual((self.project / ENGINE / "VERSION").read_text(encoding="utf-8").strip(), version)
        self.assertEqual(install(self.project)["changed"], [])
        self.assertEqual(verify(self.project), [])
        (self.project / ENGINE / "config/team.json").write_text("{}", encoding="utf-8")
        self.assertEqual(verify(self.project), [ENGINE + "/config/team.json（已修改）"])

    def test_refuses_unowned_collision_without_partial_install(self):
        (self.project / ".claude/agents").mkdir(parents=True)
        (self.project / ".claude/agents/agentworks-director.md").write_text("用户自己的角色", encoding="utf-8")
        with self.assertRaises(WorksError):
            install(self.project)
        self.assertFalse((self.project / ".agentworks").exists())
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_refuses_source_repository(self):
        with self.assertRaises(WorksError):
            install(Path(__file__).resolve().parents[1])

    def test_embedded_project_keeps_state_and_logs_inside_repository(self):
        install(self.project)
        output = subprocess.run([sys.executable, "-c", EMBEDDED_RUN], cwd=self.project,
                                capture_output=True, text=True, check=True).stdout
        data = json.loads(output)
        self.assertTrue(data["check"]["embedded"])
        self.assertEqual(data["check"]["version"], (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip())
        self.assertNotIn("研究海外游戏机会", data["prompt"])
        self.assertEqual(data["check"]["configuration_drift"], [])
        self.assertEqual(Path(data["workspace"]), self.project.resolve())
        self.assertIn("本仓库已绑定项目 cleaner", data["second"])
        self.assertIn(str(self.project.resolve() / ".agents/skills/agentworks-market-researcher/SKILL.md"), data["prompt"])
        meta = self.project / ".agentworks/projects/cleaner"
        self.assertTrue((meta / "BRIEF.md").is_file())
        self.assertTrue(list((meta / "runs/1").glob("*-prompt.txt")))
        self.assertTrue((self.project / ".git").is_dir())
        ignored = subprocess.run(["git", "check-ignore", ".agentworks/locks/cleaner.lock", ".agentworks/state.sqlite3",
                                  ".agentworks/projects/cleaner/input/README.md"],
                                 cwd=self.project, capture_output=True, text=True).stdout.split()
        self.assertEqual(ignored, [".agentworks/locks/cleaner.lock"])


if __name__ == "__main__":
    unittest.main()
