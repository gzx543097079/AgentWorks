"""在工程生成阶段复制对应语言日志源码，返回待纳入构建的文件清单；由桌面 Agent 调用 install(app_root, destination, language)。"""
from pathlib import Path

SOURCES = {
    'swift': ('TFLogger.swift',),
    'objc': ('TFLogger.h', 'TFLogger.m'),
    'mixed': ('TFLogger.swift', 'TFLogger.h', 'TFLogger.m'),
}


def install(project, destination, language):
    """预检全部目标，保留既有定制；重复安装相同内容不会重写文件。"""
    root = Path(project).resolve()
    if not root.is_dir():
        raise ValueError('业务工程目录不存在')
    if language not in SOURCES:
        raise ValueError('语言须为 swift、objc 或 mixed')
    skill = Path(__file__).resolve().parents[1]
    relative = Path(destination)
    if (relative.is_absolute() or '..' in relative.parts or not relative.parts
            or relative.parts[0] in ('.agents', '.git', 'requirements', 'logs')):
        raise ValueError('日志目标须为项目内的业务源码目录')
    directory = root / relative
    for node in (directory, *directory.parents):
        if node == root:
            break
        if node.is_symlink() or (node.exists() and not node.is_dir()):
            raise ValueError('日志目录不能包含符号链接或普通文件：' + str(node))
    pending = []
    for name in SOURCES[language]:
        source = skill / 'assets/logging' / name
        if any(node.is_symlink() for node in (source, source.parent, source.parent.parent)):
            raise ValueError('日志源文件不能为符号链接')
        data = source.read_bytes()
        target = directory / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('日志目标不是普通文件：' + str(target))
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError('日志文件已有定制，请先比较并合并：' + str(target))
        else:
            pending.append((target, data))
    written = []
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for target, data in pending:
            # 排他创建避免覆盖预检后出现的文件；失败时仅撤销本次创建内容。
            with target.open('xb') as stream:
                written.append(target)
                stream.write(data)
    except OSError:
        for target in written:
            target.unlink()
        raise
    return {
        'files': [str(relative / name) for name in SOURCES[language]],
        'created': [str(path.relative_to(root)) for path in written],
        'next': '生成工程时将 .swift/.m 纳入目标 Sources，并核对 Debug 定义 DEBUG、Release 不定义 DEBUG；复制成功不代表已加入构建目标。',
    }
