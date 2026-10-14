#!/usr/bin/env python3
"""Opt-in live check: two real roles using the selected backend hand off a local fixture."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentworks.core import Store, write_json
from agentworks.backends import resolve_backend
from agentworks.runner import run_tasks


def main():
    parser = argparse.ArgumentParser(description="实际调用两个角色检查跨任务交接，会使用当前账号模型额度。")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--backend", choices=["codex", "claude", "auto"], default="auto")
    args = parser.parse_args()
    if not args.execute:
        print("加 --execute 才会调用模型；此检查只处理本地测试简报。")
        return 0
    backend = resolve_backend(args.backend)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    store = Store(ROOT / ".agentworks/verification" / stamp)
    store.create("smoke", "本地交接验证", kind="tool", market="英语使用者",
                 brief="这是系统连通性测试，不做市场调研。假设工具只有添加待办、标记完成、删除待办三个功能。")
    run = store.plan("smoke", "discovery")
    tasks = [
        {"id": "brief", "role": "product_manager", "title": "提炼测试简报", "depends": [],
         "prompt": "只根据简报给出3条可测试的验收条件，简短回答。不要使用工具、搜索或编写产品。证据类型 hypothesis；这是本地连通性测试。"},
        {"id": "check", "role": "qa_engineer", "title": "检查前置交付", "depends": ["brief"], "gate": True,
         "prompt": "只核查前置角色交付是否覆盖添加、完成、删除三个动作并能测试。报告你实际收到的交付内容；满足则 pass。不要使用工具、搜索或编写产品。"}
    ]
    with store.db() as db:
        db.execute("DELETE FROM tasks WHERE run=?", (run["id"],))
        for task in tasks:
            db.execute("INSERT INTO tasks(run,code,spec) VALUES(?,?,?)", (run["id"], task["id"], json.dumps(task, ensure_ascii=False)))
    print("测试记录：" + str(store.home), flush=True)
    outcomes = run_tasks(store, "smoke", max_tasks=2, workers=1, timeout=180, search=False, backend=backend)
    passed = len(outcomes) == 2 and all(status == "completed" for _, status in outcomes)
    summary = {"passed": passed, "backend": backend, "scope": "两个真实角色处理本地夹具并交接；不含市场、设计、开发或运营成效验证。",
               "outcomes": outcomes, "data_dir": str(store.home)}
    write_json(ROOT / ".agentworks/verification/latest.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
