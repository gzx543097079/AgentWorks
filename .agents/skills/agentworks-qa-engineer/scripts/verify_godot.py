#!/usr/bin/env python3
"""检查项目内 Godot 导入与真实测试脚本，错误日志不能被退出码 0 掩盖。"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def find_godot(explicit=None):
    if explicit:
        candidate = shutil.which(explicit) or explicit
    else:
        candidate = shutil.which('godot') or shutil.which('godot4')
        if not candidate and Path('/Applications/Godot.app/Contents/MacOS/Godot').is_file():
            candidate = '/Applications/Godot.app/Contents/MacOS/Godot'
    if not candidate or not Path(candidate).is_file():
        raise ValueError('未找到 Godot；使用 --godot 指定已有可执行文件')
    return str(Path(candidate).resolve())


def project_file(project, name):
    path = project / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('文件必须相对游戏根：' + name)
    current = project
    for part in Path(name).parts:
        current /= part
        if current.is_symlink():
            raise ValueError('项目路径包含符号链接：' + name)
    if not path.is_file():
        raise ValueError('缺少项目文件：' + name)
    return path


def project_version(project):
    """读取 project.godot 的 config/features 中的主次版本；未声明时返回 None。"""
    text = (project / 'project.godot').read_text()
    features = re.search(r'^config/features=PackedStringArray\(([^)]*)\)', text, re.MULTILINE)
    match = re.search(r'"(\d+)\.(\d+)"', features.group(1)) if features else None
    return (int(match.group(1)), int(match.group(2))) if match else None


def check_version(version, expected=None, project=None):
    """显式版本须精确匹配；否则引擎须与工程同主版本且次版本不低于工程，允许升级引擎。"""
    if expected:
        if version.split('.stable', 1)[0] != expected:
            raise ValueError('Godot 版本不匹配：预期 ' + expected + '，实际 ' + version)
        return
    engine = re.match(r'(\d+)\.(\d+)', version)
    if project and (not engine or int(engine.group(1)) != project[0] or int(engine.group(2)) < project[1]):
        raise ValueError(f'Godot 版本低于工程声明：工程 {project[0]}.{project[1]}，实际 {version}')


def pinned_version(project):
    """未显式传版本时沿用团队锁定：Git 根 .agents/team/toolchain.json 的 godot 字段。"""
    top = subprocess.run(['git', '-C', str(project), 'rev-parse', '--show-toplevel'],
                         capture_output=True, text=True)
    if top.returncode:
        return None
    path = Path(top.stdout.strip()) / '.agents/team/toolchain.json'
    if not path.is_file() or path.is_symlink():
        return None
    value = json.loads(path.read_text()).get('godot')
    if value is not None and not (isinstance(value, str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?', value)):
        raise ValueError('toolchain.json 的 godot 须为 X.Y 或 X.Y.Z')
    return value


def run_phase(argv, project, timeout, allowed_errors=()):
    """进程退出 0 也要检查引擎错误行；allowed_errors 只放行测试明确预期的错误。"""
    result = subprocess.run(argv, cwd=project, capture_output=True, text=True, timeout=timeout)
    output = result.stdout + '\n' + result.stderr
    errors = [line for line in output.splitlines() if re.match(r'\s*(?:SCRIPT ERROR|ERROR):', line)
              and not any(re.search(pattern, line) for pattern in allowed_errors)]
    if result.returncode or errors:
        raise ValueError('Godot 检查失败：\n' + output.strip())
    return result.stdout.strip()


def verify(project, godot=None, test_script=None, import_only=False, timeout=120, expected_version=None,
           allowed_errors=()):
    project = Path(project).expanduser().resolve()
    project_file(project, 'project.godot')
    if import_only and test_script:
        raise ValueError('--import-only 与 --test-script 互斥')
    if not import_only:
        if not test_script:
            raise ValueError('必须提供真实 --test-script；仅导入需明确 --import-only')
        project_file(project, test_script)
    if timeout <= 0:
        raise ValueError('timeout 必须大于 0')
    executable = find_godot(godot)
    version = run_phase([executable, '--version'], project, timeout)
    check_version(version, expected_version or pinned_version(project), project_version(project))
    logs = project / '.godot/teamflow-checks'
    for path in (project / '.godot', logs):
        if path.is_symlink():
            raise ValueError('缓存路径包含符号链接')
    logs.mkdir(parents=True, exist_ok=True)
    for name in ('import.log', 'tests.log'):
        if (logs / name).is_symlink():
            raise ValueError('日志路径包含符号链接')
    base = [executable, '--headless', '--path', str(project)]
    run_phase(base + ['--log-file', str(logs / 'import.log'), '--editor', '--import'], project, timeout)
    if not import_only:
        run_phase(base + ['--log-file', str(logs / 'tests.log'), '--script', 'res://' + test_script], project, timeout,
                  allowed_errors)
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--godot')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--test-script')
    mode.add_argument('--import-only', action='store_true')
    parser.add_argument('--expect-version')
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--allow-error', action='append', default=[], metavar='正则',
                        help='测试阶段放行的预期引擎错误行（如故意损坏存档），可重复；只匹配该行')
    args = parser.parse_args()
    try:
        for pattern in args.allow_error:
            re.compile(pattern)
        version = verify(args.project, args.godot, args.test_script, args.import_only,
                         args.timeout, args.expect_version, tuple(args.allow_error))
    except (ValueError, OSError, subprocess.TimeoutExpired, re.error) as error:
        parser.exit(1, '验证：失败\n' + str(error) + '\n')
    print('验证：通过（Godot ' + version + '，' + ('仅导入' if args.import_only else '导入与项目测试') + '）')


if __name__ == '__main__':
    main()
