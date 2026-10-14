"""Versioned deliveries and explicit human approval bound to file contents."""
import hashlib
import json
import re
import tempfile
from pathlib import Path

from .core import WorksError, now, read_json, within, write_json
from .handoff import placement, run_dir, save_result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_hashes(store, project, names):
    files = {}
    for name in sorted(set(names)):
        path = within(store.workspace(project), name)
        if not path.is_file():
            raise WorksError("确认交付缺少文件：" + name)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def archive_files(store, project, directory, files):
    for name, expected in files.items():
        source = within(store.workspace(project), name)
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise WorksError("交付在保存期间变化，请重新检查：" + name)
        target = directory / "files" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def atomic_archive(store, project, directory, files, value):
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory.parent) as temp:
        staged = Path(temp) / "snapshot"
        staged.mkdir()
        archive_files(store, project, staged, files)
        write_json(staged / "manifest.json", value)
        staged.rename(directory)


def snapshot_delivery(store, project, task, result, inputs=None):
    names = result["artifacts"] + [placement(store, project, task)["report"]]
    directories = task["spec"].get("outputs", [])
    for folder in directories:
        names.extend(directory_files(store, project, folder))
    files = file_hashes(store, project, names)
    value = {"result_digest": fingerprint(result), "inputs": inputs, "directories": directories, "product_version": store.project(project)["product_version"], "run": task["run"],
             "task": task["id"], "revision": task["attempts"], "files": files, "created": now()}
    directory = run_dir(store, project, task["run"]) / (str(task["id"]) + "-v" + str(task["attempts"]))
    if directory.exists():
        saved = read_json(directory / "manifest.json")
        if any(saved.get(key) != item for key, item in value.items() if key != "created"):
            raise WorksError("该交付版本已存在，拒绝覆盖。")
        value = saved
    else:
        atomic_archive(store, project, directory, files, value)
    value["archive"] = str(directory.relative_to(store.home / "projects" / project))
    with store.db() as db:
        db.execute("UPDATE tasks SET snapshot=? WHERE id=?", (json.dumps(value, ensure_ascii=False), task["id"]))
    return value


def current_task(store, project, task_id):
    run = store.latest(project)
    task = next((t for t in store.tasks(run["id"]) if t["id"] == task_id), None)
    if task is None:
        raise WorksError("任务不属于当前阶段。")
    return run, task


def ensure_idle(store, project):
    if any(t["status"] == "running" for r in store.runs(project) for t in store.tasks(r["id"])):
        raise WorksError("请先收齐或停止当前执行任务。")


def supersede_runs(store, project, roots, db, reason, include_roots=False):
    """Retire dependent phase runs without deleting their evidence or approvals."""
    affected = set(roots)
    for run in store.runs(project):
        if run["prerequisite"] in affected:
            affected.add(run["id"])
    retired = affected if include_roots else affected - set(roots)
    for run_id in sorted(retired):
        db.execute("UPDATE runs SET abandoned=1 WHERE id=?", (run_id,))
    if retired:
        store.event(db, project, "superseded", json.dumps({"runs": sorted(retired), "reason": reason}, ensure_ascii=False))
    return retired


def overlapping_outputs(first, second):
    return any(Path(a) == Path(b) or Path(a) in Path(b).parents or Path(b) in Path(a).parents
               for a in first for b in second)


def invalidate_tasks(store, project, run, task, reason, db):
    tasks = store.tasks(run["id"])
    affected = {task["code"]}
    outputs = list(task["spec"].get("outputs", []))
    # Multiple writer tasks can share mutable files; restart their readers too.
    changed = True
    while changed:
        changed = False
        for item in tasks:
            if (item["code"] not in affected and
                    (affected.intersection(item["spec"]["depends"]) or
                     overlapping_outputs(outputs, item["spec"].get("outputs", [])))):
                affected.add(item["code"])
                outputs.extend(item["spec"].get("outputs", []))
                changed = True
    for item in tasks:
        if item["code"] in affected:
            store.event(db, project, "delivery_invalidated", json.dumps(
                {"task": item["id"], "attempt": item["attempts"], "result": item["result"],
                 "review": item["review"], "snapshot": item["snapshot"], "reason": reason}, ensure_ascii=False))
            db.execute("UPDATE tasks SET status='pending',result=NULL,review=NULL,snapshot=NULL,retry_count=0,error=? WHERE id=?",
                       ("修订要求：" + reason, item["id"]))
    return affected


def review_inputs(store, project, run, task):
    tasks = {t["code"]: t for t in store.tasks(run["id"])}
    selected, pending = {}, list(task["spec"]["depends"])
    while pending:
        code = pending.pop()
        if code in selected:
            continue
        dependency = tasks[code]
        if dependency["status"] != "completed":
            raise WorksError("确认的前置交付尚未完成：" + code)
        selected[code] = dependency
        pending.extend(dependency["spec"]["depends"])
    # Bind the confirmation to the prerequisite lineage as well as this phase.
    prior = run["prerequisite"]
    runs = {r["id"]: r for r in store.runs(project)}
    inherited = []
    while prior is not None:
        inherited.extend(t for t in store.tasks(prior) if t["status"] == "completed")
        prior = runs[prior]["prerequisite"]
    names, deliveries, directories = [], [], set()
    for dependency in list(selected.values()) + inherited:
        if dependency["result"]:
            names.extend(dependency["result"]["artifacts"])
            names.append(placement(store, project, dependency)["report"])
        directories.update(dependency["spec"].get("outputs", []))
        deliveries.append({"task": dependency["id"], "attempt": dependency["attempts"]})
    # Later writer revisions may remove/rename files declared by an earlier task.
    names = [name for name in names if not any(Path(folder) in Path(name).parents for folder in directories)]
    for folder in directories:
        names.extend(directory_files(store, project, folder))
    return {"project": {k: store.project(project)[k] for k in ("id", "kind", "market")}, "directories": sorted(directories), "product_version": store.project(project)["product_version"], "run": run["id"],
            "task": task["id"], "deliveries": sorted(deliveries, key=lambda d: d["task"]),
            "files": file_hashes(store, project, names)}


def validate_deliveries(store, project, value):
    """Reject approval of files changed outside a recorded delivery/review round."""
    tasks = {t["id"]: t for r in store.runs(project) for t in store.tasks(r["id"])}
    expected, directory_states, latest_roles = {}, {}, {}
    for delivery in value["deliveries"]:
        task = tasks[delivery["task"]]
        if not task["snapshot"]:
            if task["spec"].get("user_confirmation"):
                name = placement(store, project, task)["report"]
                expected[name] = hashlib.sha256((task["result"]["report"] + "\n").encode()).hexdigest()
                continue
            raise WorksError("交付缺少版本快照，请重新执行：" + task["code"])
        snapshot = json.loads(task["snapshot"])
        for folder in snapshot.get("directories", []):
            root = Path(folder)
            expected = {name: sha for name, sha in expected.items() if root not in Path(name).parents}
            directory_states[folder] = {name for name in snapshot["files"] if root in Path(name).parents}
        expected.update(snapshot["files"])
        latest_roles[task["spec"]["role"]] = (task, snapshot)
    if file_hashes(store, project, expected) != expected:
        raise WorksError("交付文件在验收后变化，请 revise 对应产出并重新评审。")
    for folder in directory_states:
        names = {name for name in expected if Path(folder) in Path(name).parents}
        if set(directory_files(store, project, folder)) != names:
            raise WorksError("交付目录在验收后变化，请 revise 对应产出并重新评审：" + folder)
    for task, snapshot in latest_roles.values():
        inputs = snapshot.get("inputs")
        run = next(r for r in store.runs(project) if r["id"] == task["run"])
        from .handoff import role_for
        if inputs and role_for(run, task)["mode"] == "read-only":
            validate_inputs(store, project, inputs, task)


def validate_inputs(store, project, inputs, task):
    current = store.project(project)
    if inputs["product_version"] != current["product_version"] or inputs["project"] != {k: current[k] for k in ("id", "kind", "market")}:
        raise WorksError("任务的产品方向或版本已变化，请重新执行：" + task["code"])
    outputs = task["spec"].get("outputs", [])
    expected = {name: sha for name, sha in inputs["files"].items()
                if not any(Path(folder) in Path(name).parents for folder in outputs)}
    if file_hashes(store, project, expected) != expected:
        raise WorksError("任务评审输入已变化，请重新执行受影响评审：" + task["code"])
    for folder in inputs.get("directories", []):
        if overlapping_outputs([folder], outputs):
            continue
        names = {name for name in inputs["files"] if Path(folder) in Path(name).parents}
        if set(directory_files(store, project, folder)) != names:
            raise WorksError("任务评审输入目录已变化，请重新执行：" + task["code"])


def review(store, project, task_id):
    with store.lock(project):
        ensure_idle(store, project)
        check_approvals(store, project)
        run, task = current_task(store, project, task_id)
        if not task["spec"].get("user_confirmation") or task["status"] not in ("pending", "awaiting_user_confirmation"):
            raise WorksError("只有待确认的用户关卡可以提交预览。")
        value = review_inputs(store, project, run, task)
        validate_deliveries(store, project, value)
        value["digest"] = fingerprint(value)
        if task["review"]:
            saved = json.loads(task["review"])
            if saved["digest"] == value["digest"]:
                return saved
        value["created"] = now()
        directory = run_dir(store, project, run["id"]) / (str(task_id) + "-review-" + value["digest"])
        if not directory.exists():
            atomic_archive(store, project, directory, value["files"], value)
        value["archive"] = str(directory.relative_to(store.home / "projects" / project))
        with store.db() as db:
            db.execute("UPDATE tasks SET status='awaiting_user_confirmation',review=? WHERE id=?",
                       (json.dumps(value, ensure_ascii=False), task_id))
            store.event(db, project, "review_requested", json.dumps(value, ensure_ascii=False))
        return value


def confirm(store, project, task_id, digest, decision, feedback):
    if decision not in ("approve", "revise", "defer") or not isinstance(feedback, str) or not feedback.strip():
        raise WorksError("需要用户明确的 approve/revise/defer 决定及原话反馈。")
    with store.lock(project):
        ensure_idle(store, project)
        check_approvals(store, project)
        run, task = current_task(store, project, task_id)
        if not task["spec"].get("user_confirmation") or task["status"] != "awaiting_user_confirmation" or not task["review"]:
            raise WorksError("该用户关卡尚未提交确认或已处理。")
        saved = json.loads(task["review"])
        current = review_inputs(store, project, run, task)
        validate_deliveries(store, project, current)
        if saved["digest"] != digest or fingerprint(current) != digest:
            raise WorksError("版本或文件已变化，拒绝使用旧确认，请重新 review。")
        status = {"approve": "completed", "revise": "needs_revision", "defer": "awaiting_user_confirmation"}[decision]
        record = {**saved, "decision": decision, "feedback": feedback, "confirmed_by": "user", "decided": now()}
        result = {"status": "completed", "summary": feedback, "report": "# 用户确认\n\n" +
                  json.dumps(record, ensure_ascii=False, indent=2), "verdict": "pass" if decision == "approve" else "revise",
                  "evidence": [], "artifacts": [], "next_actions": []}
        save_result(store, project, task, result)
        with store.db() as db:
            db.execute("UPDATE tasks SET status=?,review=?,result=? WHERE id=?",
                       (status, json.dumps(record, ensure_ascii=False), json.dumps(result, ensure_ascii=False), task_id))
            store.event(db, project, "user_confirmation", json.dumps(record, ensure_ascii=False))
        return status


def directory_files(store, project, folder):
    root = within(store.workspace(project), folder)
    return [str(p.relative_to(store.workspace(project))) for p in root.rglob("*") if p.is_file()
            and not any(part in (".git", "__pycache__", ".DS_Store", "node_modules", ".godot", ".build", ".venv") for part in p.relative_to(root).parts)]


def check_approvals(store, project, excluded_phases=()):
    # Only the latest non-abandoned run of each phase is an active baseline.
    latest = {r["phase"]: r for r in store.runs(project) if not r["abandoned"]}
    runs = {r["id"]: r for r in store.runs(project)}
    for run in latest.values():
        if run["phase"] in excluded_phases:
            continue
        lineage, current = run, True
        while lineage["prerequisite"] is not None:
            parent = runs[lineage["prerequisite"]]
            if parent["phase"] not in latest or latest[parent["phase"]]["id"] != parent["id"]:
                current = False
                break
            lineage = parent
        if not current:
            continue
        for task in store.tasks(run["id"]):
            if task["status"] == "completed" and task["spec"].get("user_confirmation"):
                saved = json.loads(task["review"] or "{}")
                expected = dict(saved.get("files", {}))
                if task["result"]:
                    expected[placement(store, project, task)["report"]] = hashlib.sha256(
                        (task["result"]["report"] + "\n").encode()).hexdigest()
                names = set(expected)
                changed = not saved
                try:
                    for folder in saved.get("directories", []):
                        names.update(directory_files(store, project, folder))
                    changed = changed or file_hashes(store, project, names) != expected
                except (WorksError, OSError):
                    changed = True
                changed = changed or saved.get("project") != {k: store.project(project)[k] for k in ("id", "kind", "market")}
                if changed:
                    reason = "已批准交付或产品方向发生变化：" + task["code"]
                    with store.db() as db:
                        record = {**saved, "decision": "invalidated", "invalidated": now(), "invalidation_reason": reason}
                        store.event(db, project, "user_approval_invalidated", json.dumps(
                            {"task": task["id"], "previous_review": saved, "reason": reason}, ensure_ascii=False))
                        db.execute("UPDATE tasks SET status='needs_revision',review=?,result=NULL,error=? WHERE id=?",
                                   (json.dumps(record, ensure_ascii=False), reason, task["id"]))
                        supersede_runs(store, project, {run["id"]}, db, reason)
                    raise WorksError(reason + "；请 revise 实际产出并重新评审确认。")
                if saved.get("product_version") != store.project(project)["product_version"]:
                    raise WorksError("批准属于其他产品版本，请 plan 开启对应的新阶段。")


def revise(store, project, task_id, reason):
    if not isinstance(reason, str) or not reason.strip():
        raise WorksError("请记录修改范围和原因。")
    with store.lock(project):
        ensure_idle(store, project)
        runs = [r for r in store.runs(project) if not r["abandoned"]]
        found = [(r, t) for r in runs for t in store.tasks(r["id"]) if t["id"] == task_id]
        if not found:
            raise WorksError("任务不属于当前有效阶段。")
        run, task = found[0]
        if store.latest(project, run["phase"])["id"] != run["id"]:
            raise WorksError("不能修订已被新一轮替代的历史任务。")
        if json.loads(run["config"]).get("product_version") != store.project(project)["product_version"]:
            raise WorksError("历史任务属于其他产品版本，请 plan 开启当前版本的新阶段。")
        if task["spec"].get("user_confirmation"):
            raise WorksError("请 revise 实际上游产出任务，不能只重置用户确认关卡。")
        if task["status"] in ("pending", "running"):
            raise WorksError("只对已经交付或评审的任务开启修订。")
        with store.db() as db:
            affected = invalidate_tasks(store, project, run, task, reason, db)
            retired = supersede_runs(store, project, {run["id"]}, db, reason)
            store.event(db, project, "revision", json.dumps(
                {"run": run["id"], "tasks": sorted(affected), "superseded_runs": sorted(retired), "reason": reason}, ensure_ascii=False))


def set_version(store, project, product_version):
    if not isinstance(product_version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", product_version):
        raise WorksError("产品版本使用 major.minor.patch，如 0.2.0。")
    with store.lock(project):
        ensure_idle(store, project)
        if any(not r["abandoned"] and store.run_status(r) != "completed" for r in store.runs(project)):
            raise WorksError("请先完成或终止当前阶段再设置产品版本。")
        store.project(project)
        with store.db() as db:
            db.execute("UPDATE projects SET product_version=? WHERE id=?", (product_version, project))
            store.event(db, project, "product_version", product_version)
