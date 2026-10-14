#!/usr/bin/env python3
"""从游戏源导出 iOS Xcode 工程并在模拟器 Debug 构建；产物写入输出目录，不提交。

Godot 无界面导出遇到配置问题时只报“configuration errors”而不给原因，因此先核对已知前置条件。
"""
import argparse
import platform
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'agentworks-qa-engineer/scripts'))
from verify_godot import find_godot  # noqa: E402

ERROR_LINE = re.compile(r'^\s*(?:SCRIPT ERROR|ERROR):', re.MULTILINE)


def preset_section(text, name):
    """返回名为 name 的预设及其 options 文本；找不到时返回 None。"""
    for match in re.finditer(r'^\[preset\.(\d+)\]\s*$', text, re.MULTILINE):
        index = match.group(1)
        end = re.search(r'^\[preset\.(?!' + index + r'\.options\])', text[match.end():], re.MULTILINE)
        body = text[match.end(): match.end() + end.start()] if end else text[match.end():]
        if re.search(r'^name="' + re.escape(name) + '"$', body, re.MULTILINE):
            return body
    return None


def option(body, key):
    match = re.search(r'^' + re.escape(key) + r'=(.*)$', body, re.MULTILINE)
    return match.group(1).strip().strip('"') if match else ''


def preflight(project, preset, version):
    """核对导出前置条件，返回全部问题，避免逐个试错。"""
    problems = []
    settings = (project / 'project.godot').read_text()
    presets = project / 'export_presets.cfg'
    body = preset_section(presets.read_text(), preset) if presets.is_file() else None
    if body is None:
        return [f'export_presets.cfg 中没有名为 "{preset}" 的预设']
    if option(body, 'platform') != 'iOS':
        problems.append(f'预设 "{preset}" 的 platform 不是 iOS')
    if not option(body, 'application/app_store_team_id'):
        problems.append('application/app_store_team_id 为空；只做关闭签名的模拟器构建时可填占位值，真机与发布须用真实 Team ID')
    if not re.fullmatch(r'[A-Za-z0-9.-]+\.[A-Za-z0-9.-]+', option(body, 'application/bundle_identifier')):
        problems.append('application/bundle_identifier 缺失或格式无效')
    if option(body, 'application/export_project_only') != 'true':
        problems.append('application/export_project_only 须为 true：本脚本只导出 Xcode 工程，构建交给 xcodebuild')
    if not re.search(r'^config/icon="[^"]+"', settings, re.MULTILINE) and not option(body, 'icons/app_store_1024x1024'):
        problems.append('缺少图标：设置 project.godot 的 config/icon 或预设的 icons/app_store_1024x1024')
    if not re.search(r'^textures/vram_compression/import_etc2_astc=true', settings, re.MULTILINE):
        problems.append('iOS 导出需要 ETC2/ASTC：在 project.godot [rendering] 设置 textures/vram_compression/import_etc2_astc=true')
    # 模板目录取“版本.状态”，如 4.7.2.stable.official.ed1daf0bf → 4.7.2.stable。
    match = re.match(r'\d+\.\d+(?:\.\d+)?\.[A-Za-z0-9]+', version)
    template_dir = match.group(0) if match else version
    templates = Path.home() / 'Library/Application Support/Godot/export_templates' / template_dir / 'ios.zip'
    custom = option(body, 'custom_template/debug')
    if not custom and not templates.is_file():
        problems.append('未找到 iOS 导出模板：' + str(templates))
    return problems


def simulator_archs(output):
    """读取导出 xcframework 模拟器切片的真实架构；目录名不可信（可能写 arm64_x86_64 但只含 x86_64）。"""
    # 只看引擎主库 libgodot.a；MoltenVK 等附带库的架构不代表游戏能否链接。
    for library in sorted(output.glob('*.xcframework/ios-*simulator/libgodot.a')):
        result = subprocess.run(['lipo', '-archs', str(library)], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.split():
            return result.stdout.split()
    return []


def run(argv, cwd, timeout):
    print('$ ' + ' '.join(map(str, argv)), flush=True)
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    output = result.stdout + '\n' + result.stderr
    print(output[-6000:], flush=True)
    if result.returncode or ERROR_LINE.search(output):
        raise ValueError(f'{Path(str(argv[0])).name} 失败（退出码 {result.returncode}）')


def export(project, preset='iOS', output='build/ios', godot=None, xcodebuild='xcodebuild', timeout=1200):
    project = Path(project).expanduser().resolve()
    if not (project / 'project.godot').is_file():
        raise ValueError('游戏根缺少 project.godot：' + str(project))
    executable = find_godot(godot)
    if timeout <= 0:
        raise ValueError('timeout 必须大于 0')
    version_result = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=timeout)
    if version_result.returncode:
        raise ValueError('无法读取 Godot 版本')
    version = version_result.stdout.strip()
    problems = preflight(project, preset, version)
    if problems:
        raise ValueError('导出前置条件未满足：\n- ' + '\n- '.join(problems))
    relative = Path(output)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'build':
        raise ValueError('输出须在游戏根 build/ 内的全新子目录')
    if len(relative.parts) < 2:
        raise ValueError('输出须指定 build/ 的子目录')
    output = project / relative
    derived = output.parent / (output.name + '-derived')
    for target in (output, derived):
        if target.exists() or target.is_symlink():
            raise ValueError('保留已有产物，请选择新的输出目录：' + str(target))
        if any(node.is_symlink() for node in target.parents if node != project and project in node.parents):
            raise ValueError('输出路径不能经过符号链接')
    output.mkdir(parents=True, exist_ok=False)
    name = re.search(r'^config/name="([^"]+)"', (project / 'project.godot').read_text(), re.MULTILINE)
    stem = (re.sub(r'[^A-Za-z0-9_-]', '', name.group(1)) if name else '') or project.name
    run([executable, '--headless', '--path', str(project), '--export-debug', preset,
         str(output / (stem + '.ipa'))], project, timeout)
    xcodeproj = next(output.glob('*.xcodeproj'), None)
    if xcodeproj is None:
        raise ValueError('导出后没有生成 Xcode 工程')
    archs = simulator_archs(output)
    host = 'arm64' if platform.machine() in ('arm64', 'aarch64') else 'x86_64'
    arch = host if host in archs or not archs else archs[0]
    run([xcodebuild, 'build', '-project', str(xcodeproj), '-scheme', xcodeproj.stem, '-configuration', 'Debug',
         '-sdk', 'iphonesimulator', '-destination', 'generic/platform=iOS Simulator', '-derivedDataPath', str(derived),
         'CODE_SIGNING_ALLOWED=NO', 'ARCHS=' + arch, 'ONLY_ACTIVE_ARCH=NO', '-quiet'], project, timeout)
    app = next(derived.glob('Build/Products/Debug-iphonesimulator/*.app'), None)
    if app is None:
        raise ValueError('xcodebuild 未生成模拟器 App')
    notes = []
    if arch != host:
        notes.append(f'模板模拟器切片只有 {"/".join(archs)}，缺少本机 {host}：产物不能在本机 iOS 模拟器运行，'
                     '运行与视觉验收需真机或含本机架构模拟器切片的模板')
    return {'app': str(app), 'arch': arch, 'notes': notes}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--project', required=True, help='游戏根（含 project.godot）')
    parser.add_argument('--preset', default='iOS')
    parser.add_argument('--output', default='build/ios', help='游戏根 build/ 内的全新子目录；构建目录为同级 <名>-derived')
    parser.add_argument('--godot')
    parser.add_argument('--xcodebuild', default='xcodebuild')
    parser.add_argument('--timeout', type=float, default=1200)
    args = parser.parse_args()
    try:
        result = export(args.project, args.preset, args.output, args.godot, args.xcodebuild, args.timeout)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, '导出构建：失败\n' + str(error) + '\n')
    print(f"导出构建：通过（模拟器 {result['arch']}）：{result['app']}")
    for note in result['notes']:
        print('注意：' + note)


if __name__ == '__main__':
    main()
