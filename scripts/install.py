#!/usr/bin/env python3
"""Install or upgrade AgentWorks inside a product repository."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentworks.core import WorksError
from agentworks.install import install


def main():
    if len(sys.argv) != 2:
        print("用法：python3 scripts/install.py <产品仓库路径>")
        return 2
    try:
        print(json.dumps(install(sys.argv[1]), ensure_ascii=False, indent=2))
    except WorksError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
