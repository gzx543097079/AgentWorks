import contextlib
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentworks.core import ROOT, Store, load_config, write_json
from agentworks.desktop import Workspace
from agentworks.handoff import packet
from agentworks.skills import role_skills
from scripts.sync_agents import MANIFEST, synchronize


def module(role, file):
    path = ROOT / '.agents/skills' / ('agentworks-' + role) / 'scripts' / file
    spec = importlib.util.spec_from_file_location(file[:-3], path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class SkillIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_all_roles_have_resolvable_skills_and_packets_only_assign_own_skill(self):
        team, _ = load_config()
        entries = [role_skills(ROOT, r)[0]['entrypoint'] for r in team['roles']]
        self.assertEqual(len(set(entries)), 27)
        store = Store(self.base / 'data')
        store.create('skills', '离线夹具')
        run = store.plan('skills', 'discovery')
        task = store.ready(run['id'])[0]
        prompt = packet(store, 'skills', task)
        context = json.loads(prompt.split('任务上下文：\n', 1)[1])
        role = next(r for r in team['roles'] if r['id'] == task['spec']['role'])
        self.assertEqual([s['name'] for s in context['skills']], role['skills'])
        self.assertIn('SKILL.md', context['skills'][0]['resource_sha256'])
        self.assertTrue(Path(context['skills'][0]['entrypoint']).is_absolute())

    def test_historical_stage_without_skills_keeps_its_snapshot(self):
        store = Store(self.base / 'data')
        store.create('old', '旧阶段夹具')
        run = store.plan('old', 'discovery')
        config = json.loads(run['config'])
        for r in config['team']['roles']:
            r.pop('skills')
        with store.db() as db:
            db.execute('UPDATE runs SET config=? WHERE id=?', (json.dumps(config), run['id']))
        task = store.ready(run['id'])[0]
        context = json.loads(packet(store, 'old', task).split('任务上下文：\n', 1)[1])
        self.assertEqual(context['skills'], [])
        self.assertNotIn('skills', json.loads(store.latest('old')['config'])['team']['roles'][0])

    def test_missing_skill_does_not_claim_a_task(self):
        workspace = Workspace(self.base / 'data')
        workspace.create('missing', '缺失技能夹具')
        workspace.plan('missing', 'discovery')
        with patch('agentworks.handoff.role_skills', side_effect=ValueError('missing skill')):
            with self.assertRaises(ValueError):
                workspace.begin('missing', 'codex-desktop')
        run = workspace.store.latest('missing')
        self.assertTrue(all(t['attempts'] == 0 and t['status'] == 'pending' for t in workspace.store.tasks(run['id'])))

    def test_bad_names_missing_resources_and_symlinks_fail(self):
        for value in (['../outside'], ['missing'], ['x', 'x'], [{}], 'not-a-list'):
            with self.assertRaises(ValueError):
                role_skills(ROOT, {'skills': value})
        folder = self.base / '.agents/skills/example'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text('---\nname: example\ndescription: example\n---\n')
        first = role_skills(self.base, {'skills': ['example']})
        (folder / 'asset').write_text('before')
        second = role_skills(self.base, {'skills': ['example']})
        self.assertNotEqual(first, second)
        (folder / 'escape').symlink_to(ROOT / 'AGENTS.md')
        with self.assertRaises(ValueError):
            role_skills(self.base, {'skills': ['example']})

    def test_skill_markdown_links_resolve_and_source_inventory_has_unique_owners(self):
        for path in (ROOT / '.agents/skills').rglob('*.md'):
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
                if '://' in target or target.startswith('#'):
                    continue
                target = target.split('#')[0]
                self.assertTrue((path.parent / target).exists(), (path, target))
        manifest = json.loads((ROOT / 'config/teamflow-sources.json').read_text())
        resources = manifest['resources']
        self.assertEqual(len({r['source'] for r in resources}), len(resources))
        self.assertEqual(len({r['destination'] for r in resources}), len(resources))
        for row in resources:
            self.assertTrue((ROOT / row['destination']).is_file())
            self.assertIn('agentworks-' + row['owner'].replace('_', '-'), row['destination'])

    def copy_repository(self):
        root = self.base / 'repo'
        (root / 'config').mkdir(parents=True)
        shutil.copyfile(ROOT / 'config/team.json', root / 'config/team.json')
        shutil.copytree(ROOT / '.agents/skills', root / '.agents/skills', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        return root

    def test_sync_mirrors_binary_resources_removes_retired_and_preserves_custom(self):
        root = self.copy_repository()
        source = root / '.agents/skills/agentworks-developer/assets/sample.bin'
        source.write_bytes(b'\x00\xff\x90')
        synchronize(root)
        target = root / '.claude/skills/agentworks-developer/assets/sample.bin'
        self.assertEqual(source.read_bytes(), target.read_bytes())
        custom = target.with_name('custom.bin')
        custom.write_bytes(b'personal')
        source.write_bytes(b'updated')
        self.assertTrue(synchronize(root, check=True))
        self.assertEqual(target.read_bytes(), b'\x00\xff\x90')
        synchronize(root)
        self.assertEqual(target.read_bytes(), b'updated')
        source.unlink()
        synchronize(root)
        self.assertFalse(target.exists())
        self.assertEqual(custom.read_bytes(), b'personal')
        self.assertEqual(synchronize(root, check=True), [])

    def test_unowned_collision_stops_before_mutation(self):
        root = self.copy_repository()
        target = root / '.claude/skills/agentworks-developer/SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text('custom skill')
        with self.assertRaises(ValueError):
            synchronize(root)
        self.assertEqual(target.read_text(), 'custom skill')
        self.assertFalse((root / '.codex/agents').exists())
        self.assertFalse((root / MANIFEST).exists())


class SkillHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.logger = module('developer', 'install_logging.py')
        self.verify = module('qa-engineer', 'verify_godot.py')
        self.export = module('release-engineer', 'export_ios.py')

    def test_logging_install_is_idempotent_and_preflights_customizations(self):
        result = self.logger.install(self.root, 'Sources/Logging', 'mixed')
        self.assertEqual(len(result['created']), 3)
        before = {p.name: p.stat().st_mtime_ns for p in (self.root / 'Sources/Logging').iterdir()}
        self.assertEqual(self.logger.install(self.root, 'Sources/Logging', 'mixed')['created'], [])
        self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in (self.root / 'Sources/Logging').iterdir()})
        target = self.root / 'Custom'
        target.mkdir()
        (target / 'TFLogger.m').write_text('custom implementation')
        with self.assertRaises(ValueError):
            self.logger.install(self.root, 'Custom', 'mixed')
        self.assertEqual([p.name for p in target.iterdir()], ['TFLogger.m'])

    def test_logging_rejects_outside_paths_and_symlink(self):
        for path in ('../outside', '/tmp/outside', '.', '.agents/overwrite'):
            with self.assertRaises(ValueError):
                self.logger.install(self.root, path, 'swift')
        (self.root / 'Link').symlink_to(self.root / 'External')
        with self.assertRaises(ValueError):
            self.logger.install(self.root, 'Link', 'swift')

    def fake_tool(self, name, body):
        path = self.root / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)
        return str(path)

    def game(self):
        game = self.root / 'game'
        game.mkdir()
        (game / 'project.godot').write_text('config_version=5\n[application]\nconfig/name="Example"\n')
        (game / 'test.gd').write_text('# fixture')
        return game

    def test_godot_does_not_accept_zero_exit_with_engine_error(self):
        game = self.game()
        tool = self.fake_tool('godot', 'import sys\nprint("4.7.2.stable" if "--version" in sys.argv else "ERROR: failed import")\n')
        with self.assertRaisesRegex(ValueError, 'Godot 检查失败'):
            self.verify.verify(game, godot=tool, test_script='test.gd')
        with self.assertRaises(ValueError):
            self.verify.verify(game, godot=tool)

    def test_godot_real_process_fixture_checks_import_and_test(self):
        game = self.game()
        tool = self.fake_tool('godot', 'import sys\nprint("4.7.2.stable" if "--version" in sys.argv else "fixture passed")\n')
        self.assertEqual(self.verify.verify(game, godot=tool, test_script='test.gd', expected_version='4.7.2'), '4.7.2.stable')
        with self.assertRaises(ValueError):
            self.verify.verify(game, godot=tool, test_script='test.gd', expected_version='4.6.0')

    def export_tools(self):
        godot = self.fake_tool('godot', '''import sys
from pathlib import Path
if '--version' in sys.argv:
    print('4.7.2.stable')
else:
    output = Path(sys.argv[-1])
    (output.parent / (output.stem + '.xcodeproj')).mkdir()
''')
        xcode = self.fake_tool('xcodebuild', '''import sys
from pathlib import Path
derived = Path(sys.argv[sys.argv.index('-derivedDataPath') + 1])
(derived / 'Build/Products/Debug-iphonesimulator/Example.app').mkdir(parents=True)
''')
        return godot, xcode

    def test_export_fixture_uses_fresh_in_project_output_and_preserves_previous(self):
        game = self.game()
        godot, xcode = self.export_tools()
        with patch.object(self.export, 'preflight', return_value=[]), patch.object(self.export, 'simulator_archs', return_value=['x86_64']), patch.object(self.export.platform, 'machine', return_value='arm64'), contextlib.redirect_stdout(io.StringIO()):
            result = self.export.export(game, output='build/one', godot=godot, xcodebuild=xcode)
            self.assertTrue(Path(result['app']).is_dir())
            self.assertIn('缺少本机 arm64', result['notes'][0])
            for output in ('build/one', '../outside', str(self.root / 'absolute'), 'build'):
                with self.assertRaises(ValueError):
                    self.export.export(game, output=output, godot=godot, xcodebuild=xcode)
            self.assertTrue(Path(result['app']).is_dir())
            (game / 'build/link').symlink_to(self.root, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.export.export(game, output='build/link/out', godot=godot, xcodebuild=xcode)

    def test_export_preflight_reports_missing_actual_configuration(self):
        game = self.game()
        self.assertIn('没有名为', self.export.preflight(game, 'iOS', '4.7.2.stable')[0])
        (game / 'export_presets.cfg').write_text('[preset.0]\nname="iOS"\nplatform="iOS"\n[preset.0.options]\n')
        errors = '\n'.join(self.export.preflight(game, 'iOS', '4.7.2.stable'))
        self.assertIn('app_store_team_id', errors)
        self.assertIn('bundle_identifier', errors)
        self.assertIn('export_project_only', errors)
