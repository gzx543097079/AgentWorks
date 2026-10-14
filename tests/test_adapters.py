import json
import shutil
import tempfile
import unittest
from pathlib import Path

from agentworks.core import ROOT, write_json
from scripts.sync_agents import synchronize


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_generation_removes_retired_roles_but_preserves_custom_roles(self):
        root = self.root / "config-repo"
        for source in ("config/team.json", ".agents/skills/agentworks/SKILL.md"):
            path = root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, path)
        synchronize(root)
        team = json.loads((root / "config/team.json").read_text())
        for folder, pattern in (("roles", "*.md"), (".codex/agents", "*.toml"), (".claude/agents", "*.md")):
            self.assertEqual(len(list((root / folder).glob(pattern))), len(team["roles"]))
        custom = root / ".claude/agents/custom.md"
        custom.write_text("A user-authored custom role")
        removed = team["roles"].pop()
        write_json(root / "config/team.json", team)
        drift = synchronize(root, check=True)
        self.assertTrue(any(removed["id"] in name for name in drift))
        synchronize(root)
        self.assertFalse((root / "roles" / (removed["id"] + ".md")).exists())
        self.assertTrue(custom.exists())
        self.assertEqual(synchronize(root, check=True), [])
