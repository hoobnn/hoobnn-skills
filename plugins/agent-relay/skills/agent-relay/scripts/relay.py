#!/usr/bin/env python3
"""在一个 agent 里调用另一个 agent CLI（grok / agy / codex / opencode / pi / hermes / claude）。

每家 CLI 的 headless 参数、权限开关、续会话方式和输出格式都不一样，这里统一成：

    relay.py run <cli> [--write] [--model M] [--effort E] [--resume ID]
                       [--cwd DIR] [--timeout SEC] (PROMPT | - | --prompt-file F)
    relay.py check [cli ...] [--model M]

run 只往 stdout 打印一个 JSON 对象：
    {ok, text, session_id, cost_usd, read_only_enforced, error, log}
原始输出写到 log 指向的目录，不回显。只依赖 Python 3 标准库。
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "agent-relay"

# 只读时 grok / pi / claude 用工具白名单，codex 用沙箱，opencode 用内置的 plan agent。
# agy 和 hermes 没有能拦住写操作的开关（plan 模式、--sandbox、默认权限实测都会写文件），
# 结果里 read_only_enforced=false，要不要在 prompt 里约束由调用方决定。


def _last(items):
    return items[-1] if items else None


def _json_lines(raw):
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _json_doc(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        return json.loads(raw[start:]) if start >= 0 else {}


# ---------------------------------------------------------------- 各家 CLI 适配


def build_grok(a, prompt):
    cmd = ["grok", "--no-auto-update", "-p", prompt, "--output-format", "json"]
    if a.write:
        cmd.append("--always-approve")
    else:
        cmd += ["--tools", "read_file,list_dir,grep,web_fetch"]
    if a.model:
        cmd += ["-m", a.model]
    if a.effort:
        cmd += ["--reasoning-effort", a.effort]
    if a.resume:
        cmd += ["-r", a.resume]
    return cmd, True, None


def parse_grok(raw, a, sid):
    d = _json_doc(raw)
    return {
        "text": d.get("text"),
        "session_id": d.get("sessionId"),
        "cost_usd": d.get("total_cost_usd"),
        "ok": d.get("stopReason") in ("end_turn", "max_turns", None) and bool(d.get("text")),
    }


def build_agy(a, prompt):
    cmd = ["agy", "-p", prompt, "--output-format", "json",
           # 新版默认 0（不限时），旧版默认 5 分钟；显式传，由 relay 的 --timeout 兜底
           "--print-timeout", f"{max(a.timeout - 30, 60)}s"]
    if a.write:
        cmd.append("--dangerously-skip-permissions")
    if a.model:
        cmd += ["--model", a.model]
    if a.effort:
        cmd += ["--effort", a.effort]
    if a.resume:
        cmd += ["--conversation", a.resume]
    return cmd, a.write, None


def parse_agy(raw, a, sid):
    d = _json_doc(raw)
    text = (d.get("response") or "").strip()
    return {
        "text": text,
        "session_id": d.get("conversation_id"),
        "cost_usd": None,
        # 模型名不认识时 agy 会静默返回空回答且退出码为 0
        "ok": d.get("status") == "SUCCESS" and bool(text),
    }


def build_codex(a, prompt):
    sandbox = "workspace-write" if a.write else "read-only"
    opts = ["--json", "--skip-git-repo-check", "-c", f"sandbox_mode={sandbox}"]
    if a.model:
        opts += ["-m", a.model]
    if a.effort:
        opts += ["-c", f"model_reasoning_effort={a.effort}"]
    if a.resume:
        return ["codex", "exec", "resume", *opts, a.resume, prompt], True, None
    return ["codex", "exec", *opts, prompt], True, None


def parse_codex(raw, a, sid):
    ev = _json_lines(raw)
    thread = next((e.get("thread_id") for e in ev if e.get("type") == "thread.started"), None)
    msgs = [e["item"].get("text") for e in ev
            if e.get("type") == "item.completed" and (e.get("item") or {}).get("type") == "agent_message"]
    done = _last([e for e in ev if e.get("type") == "turn.completed"])
    failed = _last([e for e in ev if e.get("type") in ("turn.failed", "error")])
    return {
        "text": _last(msgs),
        "session_id": thread or a.resume,
        "cost_usd": None,
        "ok": done is not None and failed is None and bool(msgs),
        "error": (failed or {}).get("error") or (failed or {}).get("message"),
    }


def build_opencode(a, prompt):
    cmd = ["opencode", "run", "--format", "json"]
    cmd += ["--auto"] if a.write else ["--agent", "plan"]
    if a.model:
        cmd += ["-m", a.model]
    if a.effort:
        cmd += ["--variant", a.effort]
    if a.resume:
        cmd += ["-s", a.resume]
    cmd.append(prompt)
    return cmd, True, None


def parse_opencode(raw, a, sid):
    ev = _json_lines(raw)
    texts = [e["part"].get("text") for e in ev if e.get("type") == "text" and e.get("part")]
    finish = _last([e for e in ev if e.get("type") == "step_finish"])
    part = (finish or {}).get("part") or {}
    errors = [e for e in ev if e.get("type") == "error"]
    return {
        "text": "\n".join(t for t in texts if t) or None,
        "session_id": next((e.get("sessionID") for e in ev if e.get("sessionID")), a.resume),
        "cost_usd": part.get("cost"),
        "ok": bool(texts) and not errors,
        "error": errors[0].get("error") if errors else None,
    }


def build_pi(a, prompt):
    # pi 的 --session-id 不存在时会新建，这样首轮就能拿到可续接的会话 ID
    sid = a.resume or str(uuid.uuid4())
    cmd = ["pi", "-p", "--mode", "json", "--session-id", sid]
    if not a.write:
        cmd += ["--tools", "read,grep,find,ls"]
    if a.model:
        cmd += ["--model", a.model]
    if a.effort:
        cmd += ["--thinking", a.effort]
    cmd.append(prompt)
    return cmd, True, sid


def parse_pi(raw, a, sid):
    ev = _json_lines(raw)
    end = _last([e for e in ev if e.get("type") == "turn_end"])
    msg = (end or {}).get("message") or {}
    text = "".join(c.get("text", "") for c in msg.get("content") or [] if c.get("type") == "text")
    cost = (msg.get("usage") or {}).get("cost") or {}
    return {
        "text": text or None,
        "session_id": sid,
        "cost_usd": cost.get("total"),
        "ok": bool(text) and msg.get("stopReason") not in ("error", "aborted"),
    }


def build_hermes(a, prompt):
    usage_file = a._run_dir / "usage.json"
    cmd = ["hermes", "-z", prompt, "--usage-file", str(usage_file)]
    if a.write:
        cmd.append("--yolo")
    if a.model:
        cmd += ["-m", a.model]
    if a.effort:
        cmd += ["--reasoning", a.effort]
    if a.resume:
        cmd += ["--resume", a.resume]
    return cmd, a.write, None


def parse_hermes(raw, a, sid):
    usage = {}
    f = a._run_dir / "usage.json"
    if f.exists():
        try:
            usage = json.loads(f.read_text())
        except json.JSONDecodeError:
            pass
    text = raw.strip()
    return {
        "text": text or None,
        "session_id": usage.get("session_id") or a.resume,
        "cost_usd": usage.get("estimated_cost_usd"),
        "ok": bool(text) and not usage.get("failed") and not usage.get("interrupted"),
    }


def build_claude(a, prompt):
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if a.write:
        cmd += ["--permission-mode", "bypassPermissions"]
    else:
        cmd += ["--tools", "Read,Grep,Glob,WebFetch,WebSearch"]
    if a.model:
        cmd += ["--model", a.model]
    if a.effort:
        cmd += ["--effort", a.effort]
    if a.resume:
        cmd += ["--resume", a.resume]
    return cmd, True, None


def parse_claude(raw, a, sid):
    d = _json_doc(raw)
    return {
        "text": d.get("result"),
        "session_id": d.get("session_id"),
        "cost_usd": d.get("total_cost_usd"),
        "ok": not d.get("is_error") and bool(d.get("result")),
    }


ADAPTERS = {
    "grok": (build_grok, parse_grok),
    "agy": (build_agy, parse_agy),
    "codex": (build_codex, parse_codex),
    "opencode": (build_opencode, parse_opencode),
    "pi": (build_pi, parse_pi),
    "hermes": (build_hermes, parse_hermes),
    "claude": (build_claude, parse_claude),
}

# ---------------------------------------------------------------- 命令


def _descendants(pid):
    try:
        out = subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True).stdout
    except OSError:
        return []
    children = {}
    for line in out.splitlines():
        p, pp = line.split()
        children.setdefault(int(pp), []).append(int(p))
    found, stack = [], [pid]
    while stack:
        for c in children.get(stack.pop(), []):
            found.append(c)
            stack.append(c)
    return found


def _kill_tree(proc):
    # codex 等会把命令放进新的会话 / 进程组，只杀进程组会留下孤儿，所以先按父子关系收集整棵树
    pids = [proc.pid, *_descendants(proc.pid)]
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for p in pids:
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=10)
            if sig == signal.SIGTERM:
                time.sleep(1)
        except subprocess.TimeoutExpired:
            pass


def _prune_runs(days=7):
    runs = STATE_DIR / "runs"
    if not runs.is_dir():
        return
    cutoff = time.time() - days * 86400
    for d in runs.iterdir():
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def execute(a, prompt):
    """跑一次 CLI，返回统一结果；a 需要 cli/write/model/effort/resume/cwd/timeout。"""
    cwd = Path(a.cwd or os.getcwd()).resolve()
    _prune_runs()
    a._run_dir = STATE_DIR / "runs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{a.cli}-{uuid.uuid4().hex[:6]}"
    a._run_dir.mkdir(parents=True, exist_ok=True)

    build, parse = ADAPTERS[a.cli]
    cmd, enforced, sid = build(a, prompt)
    (a._run_dir / "cmd.json").write_text(json.dumps({"cwd": str(cwd), "argv": cmd}, ensure_ascii=False, indent=2))

    out_path, err_path = a._run_dir / "stdout", a._run_dir / "stderr"
    timed_out = False
    with open(out_path, "w") as out, open(err_path, "w") as err:
        # stdin 必须是 /dev/null：codex 等会在 stdin 是管道时等待额外输入
        proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                start_new_session=True)
        try:
            proc.wait(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
    raw = out_path.read_text(errors="replace")

    try:
        res = parse(raw, a, sid)
    except Exception as e:  # 输出格式变了也要把原始日志位置交回去
        res = {"text": None, "session_id": sid, "ok": False, "error": f"解析输出失败：{e}"}

    if timed_out:
        res["error"] = f"超过 {a.timeout}s 被终止"
    elif proc.returncode != 0:
        tail = err_path.read_text(errors="replace").strip()[-800:]
        res["error"] = res.get("error") or tail or f"退出码 {proc.returncode}"

    result = {
        "ok": bool(res.get("ok")) and proc.returncode == 0 and not timed_out,
        "text": res.get("text"),
        "session_id": res.get("session_id"),
        "cost_usd": res.get("cost_usd"),
        "read_only_enforced": None if a.write else enforced,
        "error": res.get("error"),
        "log": str(a._run_dir),
    }
    (a._run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _check_cli(cli, model, timeout):
    """三项冒烟测试：回复 OK、续会话能取回上一轮信息、只读模式写不出文件。"""
    def ns(**kw):
        base = dict(cli=cli, write=False, model=model, effort=None, resume=None,
                    cwd=None, timeout=timeout)
        base.update(kw)
        return argparse.Namespace(**base)

    report = {"cli": cli, "checks": {}, "cost_usd": 0.0}
    enforced = ADAPTERS[cli][0](ns(_run_dir=Path(tempfile.gettempdir())), "")[1]

    def record(name, passed, r, detail=None):
        report["checks"][name] = {"pass": passed, "detail": detail or (r.get("error") or r.get("text")),
                                  "log": r.get("log")}
        report["cost_usd"] += r.get("cost_usd") or 0

    with tempfile.TemporaryDirectory(prefix=f"relay-check-{cli}-") as tmp:
        work = Path(tmp)
        subprocess.run(["git", "init", "-q", str(work)], check=False)

        r = execute(ns(cwd=work), "只回复两个字母: OK")
        record("reply", r["ok"] and "OK" in (r["text"] or "").upper(), r)

        r1 = execute(ns(cwd=work), "这是一个会话续接测试。请记住数字 7381，现在只回复: 好")
        if r1["session_id"]:
            r2 = execute(ns(cwd=work, resume=r1["session_id"]), "上一轮让你记住的数字是多少？只回复这个数字")
            record("resume", r2["ok"] and "7381" in (r2["text"] or ""), r2)
        else:
            record("resume", False, r1, "第一轮没有返回 session_id")

        if enforced:
            r = execute(ns(cwd=work), "在当前目录创建文件 probe.txt，内容为 hello，然后回复 DONE。")
            blocked = not (work / "probe.txt").exists()
            record("read_only", blocked, r, "写入被挡住" if blocked else "probe.txt 被写出来了")
        else:
            report["checks"]["read_only"] = {"pass": None, "detail": "该 CLI 没有只读开关，跳过"}

    report["pass"] = all(c["pass"] is not False for c in report["checks"].values())
    report["cost_usd"] = round(report["cost_usd"], 4)
    return report


def cmd_check(a):
    clis = a.cli or [c for c in ADAPTERS if shutil.which(c)]
    for c in clis:
        if c not in ADAPTERS or not shutil.which(c):
            sys.exit(f"{c} 不支持或没有安装")
    with ThreadPoolExecutor(max_workers=len(clis)) as pool:
        reports = list(pool.map(lambda c: _check_cli(c, a.model, a.timeout), clis))
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    sys.exit(0 if all(r["pass"] for r in reports) else 1)


def cmd_run(a):
    if a.cli not in ADAPTERS:
        sys.exit(f"未知 CLI：{a.cli}，可选 {', '.join(ADAPTERS)}")
    if not shutil.which(a.cli):
        sys.exit(f"{a.cli} 没有安装或不在 PATH 里")

    prompt = a.prompt
    if a.prompt_file:
        prompt = Path(a.prompt_file).read_text()
    elif prompt in (None, "-"):
        prompt = sys.stdin.read()
    if not prompt or not prompt.strip():
        sys.exit("prompt 为空")

    result = execute(a, prompt)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


def main():
    p = argparse.ArgumentParser(description="调用其他 agent CLI 并统一输出")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="运行一次任务")
    r.add_argument("cli", help=" / ".join(ADAPTERS))
    r.add_argument("prompt", nargs="?", help="任务文本；写 - 或省略则从 stdin 读")
    r.add_argument("--prompt-file", help="从文件读任务文本")
    r.add_argument("--write", action="store_true", help="允许改文件、跑命令（默认只读）")
    r.add_argument("--model", help="模型名，按各家 CLI 的写法")
    r.add_argument("--effort", help="推理强度，按各家 CLI 的取值")
    r.add_argument("--resume", help="上一轮返回的 session_id")
    r.add_argument("--cwd", help="工作目录，默认当前目录")
    r.add_argument("--timeout", type=int, default=1200, help="秒，默认 1200")
    c = sub.add_parser("check", help="冒烟测试：回复、续会话、只读挡写；CLI 升级后跑一遍")
    c.add_argument("cli", nargs="*", help="要测的 CLI，默认测本机已安装的全部")
    c.add_argument("--model", help="测试用的模型，省钱可指定便宜的")
    c.add_argument("--timeout", type=int, default=300, help="每次调用的超时秒数，默认 300")
    a = p.parse_args()
    {"run": cmd_run, "check": cmd_check}[a.command](a)


if __name__ == "__main__":
    main()
