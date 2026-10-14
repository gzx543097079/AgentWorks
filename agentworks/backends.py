"""CLI-specific transport; workflow state and role definitions stay portable."""
import json
import shutil

from .core import ROOT, WorksError, read_json

BACKENDS = ("codex", "claude")


def resolve_backend(name="auto"):
    if name == "auto":
        available = [item for item in BACKENDS if shutil.which(item)]
        if len(available) != 1:
            raise WorksError("自动选择需要恰好一个可用 CLI；请指定 --backend codex 或 --backend claude，"
                             "也可在任意 Agent 环境通过 packet / submit 执行。")
        return available[0]
    if name not in BACKENDS:
        raise WorksError("不支持的运行后端：" + str(name))
    if not shutil.which(name):
        raise WorksError("未找到 " + name + " CLI；可通过当前对话的 packet / submit 执行，无需另装 CLI。")
    return name


def build_command(workspace, output, model=None, search=True, writable=False, backend="codex"):
    backend = resolve_backend(backend)
    binary = shutil.which(backend)
    if backend == "codex":
        cmd = [binary] + (["--search"] if search else [])
        cmd += ["-a", "never", "exec", "--json", "--color", "never", "--skip-git-repo-check",
                "--sandbox", "workspace-write" if writable else "read-only",
                "-c", "agents.enabled=false", "-C", str(workspace),
                "--output-schema", str(ROOT / "config/result.schema.json"),
                "--output-last-message", str(output)]
        if model:
            cmd += ["--model", model]
        return cmd + ["-"]

    # No shell or delegating tools in unattended Claude workers. Use the host
    # conversation for builds/tests requiring shell, browser, or connected tools.
    available = ["Read", "Glob", "Grep"]
    if search:
        available += ["WebSearch", "WebFetch"]
    allowed = list(available)
    if writable:
        available += ["Edit", "Write"]
        allowed += [tool + "(./" + folder + "/**)"
                    for tool in ("Edit", "Write") for folder in ("design", "app")]
    cmd = [binary, "-p", "--output-format", "json",
           "--json-schema", json.dumps(read_json(ROOT / "config/result.schema.json")),
           "--permission-mode", "dontAsk", "--tools", ",".join(available),
           "--allowedTools", ",".join(allowed), "--disallowedTools", "mcp__*",
           "--disable-slash-commands", "--no-session-persistence"]
    if model:
        cmd += ["--model", model]
    return cmd


def read_response(backend, response, stdout):
    if backend == "codex":
        if not response.is_file():
            raise WorksError("Codex 未生成结构化结果。")
        return read_json(response)
    envelope = read_json(stdout)
    if not isinstance(envelope, dict):
        raise WorksError("Claude 输出不是有效的结果对象。")
    if envelope.get("is_error") or envelope.get("subtype") not in (None, "success"):
        raise WorksError("Claude 报告执行失败；查看该次 stdout 和 stderr 日志。")
    result = envelope.get("structured_output")
    if not isinstance(result, dict):
        raise WorksError("Claude 未返回 structured_output；检查 CLI 版本和 JSON Schema 支持。")
    # A successful-looking response must not hide denied required operations.
    if envelope.get("permission_denials") and result.get("status") != "blocked":
        raise WorksError("Claude 存在权限拒绝，不能自动认定完成；检查日志后在有权限的对话中接续。")
    return result
