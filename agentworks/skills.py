"""Resolve portable role skills without relying on a desktop's auto-discovery."""
import hashlib
import re
from pathlib import Path


def role_skills(root, role):
    root = Path(root).resolve()
    directory = root / ".agents/skills"
    result = []
    names = role.get("skills", [])  # Historical run snapshots may predate skills.
    if not isinstance(names, list) or any(not isinstance(n, str) for n in names) or len(names) != len(set(names)):
        raise ValueError("角色技能配置须为不重复的名称列表。")
    for name in names:
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name):
            raise ValueError("无效技能名称：" + str(name))
        folder = directory / name
        entry = folder / "SKILL.md"
        if (not entry.is_file() or folder.is_symlink() or entry.is_symlink()
                or directory.is_symlink() or directory.parent.is_symlink()):
            raise ValueError("找不到普通技能入口：" + str(entry))
        files = {}
        for path in sorted(folder.rglob("*")):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise ValueError("技能资源不能为符号链接：" + str(path))
            if path.is_file():
                files[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        result.append({"name": name, "entrypoint": str(entry), "resource_sha256": files})
    return result
