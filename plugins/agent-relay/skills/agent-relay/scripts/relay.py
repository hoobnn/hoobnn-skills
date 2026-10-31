#!/usr/bin/env python3
"""通过 ACP（Agent Client Protocol）调用另一个 agent：grok / agy / codex / opencode / pi / mcode / hermes / dsh / claude。

relay 是一个 stdio ACP 客户端：起 agent 子进程，按 ACP v2 草案发起版本协商（请求 2，对端只会 v1 时回落到 v1），
新建或续接会话、按 config option 切模型 / 推理强度、发 prompt（可带文件和图片），再把结果统一成一个 JSON。
权限沿用各家本机自己的配置，relay 不改模式；agent 按配置来问时代为放行（relay 是非交互的，没人能当场确认）。
agent 用 elicitation 反问时，--answer 预先给了答案就代答，否则结束本轮、把问题放进 questions 交回调用方：

    relay.py run <cli[,cli...]> [--model [CLI=]M] [--effort [CLI=]E] [--resume ID] [--file F ...]
                       [--answer KEY=VALUE ...] [--asks allow|deny] [--full] [--cwd DIR]
                       [--timeout SEC] [--idle-timeout SEC] [--work-timeout SEC] [--protocol 1|2] (PROMPT | - | --prompt-file F)
    relay.py options <cli>          # 列出该 agent 的模型、推理强度、模式等 config option
    relay.py check [cli ...]        # 冒烟测试：回复、续会话、写文件、附件
    relay.py install agy            # 下载 ACP 注册表里的 agy ACP server
    relay.py outdated               # 对照 ACP 注册表，列出钉住的适配器有没有新版本

run 只往 stdout 打印一个 JSON 对象（多家时是数组，每项多一个 cli）：
    {ok, text, session_id, cost_usd, error, error_kind, log, protocol_version, stop_reason,
     files_changed, timing, commands, warnings[, commits, history_rewritten][, permissions][, questions][, steps]}
JSON-RPC 往来写到 log 目录的 acp.jsonl（大块 base64 / data 只记大小和摘要）；status.json 是给界面看的进度快照（见 Session.write_status）。
只依赖 Python 3 标准库。
"""

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import platform
import queue
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "agent-relay"
CLIENT_INFO = {"name": "agent-relay", "title": "agent-relay", "version": "0.2.0"}
LATEST_PROTOCOL = 2
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
EMBED_LIMIT = 1 << 20  # 超过 1 MB 的文本文件只发链接，让 agent 自己读
STATUS_EVERY = 1.0  # status.json 最多每秒重写一次
STATUS_STEPS = 40  # status.json 只带最近这么多步，每步文本截到 STATUS_CHARS
STATUS_CHARS = 600
LOG_DATA_LIMIT = 4096
PROGRESS_KINDS = {"edit", "delete", "move", "execute"}
KILLED = threading.Event()
KILL_SIGNAL = None

# 没有 messageId 的消息块遇到这些更新就另起一段（pi-acp 会先发一段启动横幅，再发思考和回答）
SEGMENT_BREAKS = {"tool_call", "tool_call_update", "tool_call_content_chunk", "agent_thought", "agent_thought_chunk",
                  "available_commands_update", "plan", "plan_update"}

# ---------------------------------------------------------------- 各家 agent 的启动方式
#
# cmd：ACP server 的启动命令。npx 包按 ACP 注册表钉版本；registry：注册表里的 id，outdated 用它查新版本。

REGISTRY_URL = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"

# 照抄 ACP 注册表 antigravity-acp 的 binary 分发（平台键、归档、sha256、参数），升级时跑 outdated 拿新值
AGY_ACP = {
    "version": "1.4.3",
    "cmd": "agy_acp_server.par",
    "archives": {
        "darwin-aarch64": ("https://dl.google.com/agy-extensions/releases/macos/agy-acp-server-1.4.3-darwin-arm64.zip",
                           "c57db0a9b8b712daa9c3c17cdb990a61842ea569f279e8bd79d7aa85a303b20b", []),
        "darwin-x86_64": ("https://dl.google.com/agy-extensions/releases/macos/agy-acp-server-1.4.3-darwin-x86_64.zip",
                          "9392dbbdad7f0663dbfb5a0bf641297b0cf80d2ee9cd2d49a616bbbc7378731d", []),
        "linux-x86_64": ("https://dl.google.com/agy-extensions/releases/linux/agy-acp-server-1.4.3-linux-x86_64.zip",
                         "0634ce5306ba92c932945455e7a83fda78e2d99c33fa8aa6ee0566206a382714", ["--uid="]),
        "linux-aarch64": ("https://dl.google.com/agy-extensions/releases/linux/agy-acp-server-1.4.3-linux-arm64.zip",
                          "05c153443b0b1175151c760eeddea538950bc9843e317d54786a1f03670182bc", ["--uid="]),
    },
}


def _platform_key():
    machine = platform.machine().lower().replace("arm64", "aarch64").replace("amd64", "x86_64")
    return f"{sys.platform}-{machine}"


def _agy_cmd():
    path = STATE_DIR / "agents" / "agy" / AGY_ACP["version"] / AGY_ACP["cmd"]
    archive = AGY_ACP["archives"].get(_platform_key())
    return [str(path), *archive[2]] if path.exists() and archive else None


AGENTS = {
    "grok": {"cmd": ["grok", "agent", "stdio"]},
    # agy 声称选 v2，但 initialize 响应和后续行为都是 v1；认证复用本机 agy 的 Google 登录；
    # 它会把内置的 run-workflow skill 物化到会话目录的 skills/system/ 下，没有开关，跑完由 relay 清掉
    "agy": {"cmd": _agy_cmd, "install": "agy", "auth": "oauth-personal", "litter": ["skills/system/run-workflow"],
            "registry": "antigravity-acp"},
    "codex": {"cmd": ["npx", "-y", "@agentclientprotocol/codex-acp@2.3.0"], "registry": "codex-acp"},
    "opencode": {"cmd": ["opencode", "acp"]},
    "pi": {"cmd": ["npx", "-y", "pi-acp@0.0.34"], "registry": "pi-acp"},
    "mcode": {"cmd": ["mcode", "acp"]},
    "hermes": {"cmd": ["hermes", "acp"]},
    "dsh": {"cmd": ["dsh", "--profile", "acp"]},
    "claude": {"cmd": ["npx", "-y", "@agentclientprotocol/claude-agent-acp@0.97.0"], "registry": "claude-acp"},
}


def agent_cmd(cli):
    cmd = AGENTS[cli]["cmd"]
    return cmd() if callable(cmd) else list(cmd)


# ---------------------------------------------------------------- JSON-RPC over stdio


class RpcError(Exception):
    def __init__(self, err):
        self.code = err.get("code")
        self.data = err.get("data")
        super().__init__(err.get("message") or str(err))


class IdleError(Exception):
    pass


class StallError(Exception):
    pass


class KilledError(Exception):
    pass


def _on_signal(signum, frame):
    global KILL_SIGNAL
    if KILLED.is_set():
        os._exit(128 + signum)
    KILL_SIGNAL = signum
    KILLED.set()


def _log_value(value, key=""):
    if isinstance(value, dict):
        return {k: _log_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_log_value(v, key) for v in value]
    if isinstance(value, str) and len(value) > LOG_DATA_LIMIT:
        if key.lower() in ("data", "base64") or value.startswith("data:") or re.fullmatch(r"[A-Za-z0-9+/\r\n]+={0,2}", value):
            raw = value.encode()
            return f"<omitted {len(raw)} bytes sha256:{hashlib.sha256(raw).hexdigest()[:12]}>"
    return value


class Connection:
    """一条 stdio JSON-RPC 连接。读线程处理对端发来的请求（权限等），通知交给 on_notify。"""

    def __init__(self, cmd, cwd, run_dir, on_request, on_notify):
        self.log = open(run_dir / "acp.jsonl", "w")
        self.stderr = open(run_dir / "stderr", "w")
        self.proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.stderr, start_new_session=True)
        self.on_request, self.on_notify = on_request, on_notify
        self.pending, self.lock, self.next_id = {}, threading.Lock(), 0
        self.closed = threading.Event()
        threading.Thread(target=self._read, daemon=True).start()

    def _record(self, direction, msg):
        self.log.write(json.dumps({"t": round(time.time(), 3), "dir": direction, "msg": _log_value(msg)}, ensure_ascii=False) + "\n")
        self.log.flush()

    def _write(self, msg):
        self._record(">", msg)
        try:
            self.proc.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            pass

    def _read(self):
        for raw in self.proc.stdout:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._record("<raw", line)  # agent 不该往 stdout 写非 ACP 内容，记下来跳过
                continue
            for m in msg if isinstance(msg, list) else [msg]:
                self._record("<", m)
                self._dispatch(m)
        self.closed.set()
        with self.lock:
            for q in self.pending.values():
                q.put({"error": {"code": -32099, "message": "agent 进程已退出"}})

    def _dispatch(self, m):
        if "method" in m and "id" in m:
            try:
                self._write({"jsonrpc": "2.0", "id": m["id"], "result": self.on_request(m["method"], m.get("params") or {})})
            except RpcError as e:
                self._write({"jsonrpc": "2.0", "id": m["id"], "error": {"code": e.code, "message": str(e)}})
        elif "method" in m:
            self.on_notify(m["method"], m.get("params") or {})
        elif "id" in m:
            with self.lock:
                q = self.pending.pop(m["id"], None)
            if q:
                q.put(m)

    def send(self, method, params):
        """发请求不等响应，返回装响应的队列。"""
        with self.lock:
            self.next_id += 1
            rid, q = self.next_id, queue.Queue()
            self.pending[rid] = q
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return q

    def request(self, method, params, timeout):
        try:
            q = self.send(method, params)
            deadline = time.monotonic() + max(timeout, 1)
            while True:
                if KILLED.is_set():
                    raise KilledError()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise queue.Empty()
                try:
                    resp = q.get(timeout=min(remaining, 0.2))
                    break
                except queue.Empty:
                    pass
        except queue.Empty:
            raise TimeoutError(method)
        if "error" in resp:
            raise RpcError(resp["error"])
        return resp.get("result") or {}

    def notify(self, method, params):
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_tree(self.proc)
        _kill_tree(self.proc)  # 收掉 agent 留下的子进程
        self.log.close()
        self.stderr.close()


# ---------------------------------------------------------------- ACP 会话


class Session:
    """协商出的版本决定走 v1 还是 v2 的线协议；两者共用权限策略、文本收集和结果格式。"""

    def __init__(self, a, cwd):
        self.a, self.cwd = a, cwd
        self.spec = AGENTS[a.cli]
        self.version = None
        self.caps = {}
        self.sid = None
        self.config, self.modes, self.models = [], None, None
        self.prompting = False
        self.done = threading.Event()
        self.stop_reason, self.turn_error = None, None
        self.cost = None
        self.segments = []  # [[key, text], ...]，按消息、思考、工具调用切段，最后一段即最终回答
        self.break_since_text = False
        self.seg_counter = 0
        self.saw_active = False
        self.answers = dict(a.answers)
        self.questions = []
        self.auto_answers = []
        self.permissions = []
        self.tools = {}  # toolCallId -> 合并后的工具调用
        self.steps = []  # --full：按顺序的消息、思考、工具调用
        self.last_activity = time.time()
        self.last_progress = self.last_activity
        self.output_since_progress = self.read_since_progress = False
        self.prompt_started = self.prompt_ended = self.timing_at = None
        self.tool_s = self.model_s = 0.0
        self.first_tool_s = self.first_edit_s = self.first_commit_s = None
        self.git_diff, self.head, self.head_checked = False, None, float("-inf")
        self.conn = None
        self.status_path, self.status_at, self.started, self.prompt_head = None, float("-inf"), time.time(), None
        self.status_lock = threading.Lock()  # 读线程和主线程都会写
        self.status_final = False

    # ---- 对端请求

    def on_request(self, method, params):
        self.last_activity = time.time()
        self.write_status()
        if method == "session/request_permission":
            self.output_since_progress = True
            return {"outcome": self._decide(params)}
        if method == "elicitation/create":
            return self._elicit(params)
        raise RpcError({"code": -32601, "message": f"Method not found: {method}"})  # 没声明 fs / terminal

    def _decide(self, p):
        """--asks allow（默认）代为放行；deny 把本机配置里「要问」的操作当成拒绝。"""
        title = p.get("title") or (p.get("toolCall") or {}).get("title") \
            or ((p.get("subject") or {}).get("toolCall") or {}).get("title") or (p.get("subject") or {}).get("command")
        options = p.get("options") or []
        kinds = ("allow_once", "allow_always") if self.a.asks == "allow" else ("reject_once", "reject_always")
        opt = None if self.done.is_set() else next((o for k in kinds for o in options if o.get("kind") == k), None)
        self.permissions.append({"title": title, "decision": (self.a.asks if opt else "cancelled")})
        if opt:
            return {"outcome": "selected", "optionId": opt["optionId"]}
        return {"outcome": "cancelled"}  # 没有对应选项时取消

    def _elicit(self, p):
        """--answer 覆盖了全部必填字段就代答；否则记下问题、取消本轮，由调用方续会话回答。"""
        if self.done.is_set() or p.get("mode") != "form":
            return {"action": "cancel"}  # 只声明了 form，url 模式要人去浏览器里操作
        schema = p.get("requestedSchema") or {}
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        content = {k: _coerce(v, props[k]) for k, v in self.answers.items() if k in props}
        automatic = {}
        if self.a.auto_answer:
            for k, prop in props.items():
                if k not in content:
                    value = _auto_choice(prop, self.a.auto_answer)
                    if value is not None:
                        automatic[k] = value
            content.update(automatic)
        if content and all(k in content for k in required):
            if automatic:
                self.auto_answers.append({"message": p.get("message"), "content": automatic})
                if self.conn:
                    self.conn._record("auto_answer", self.auto_answers[-1])
            for k in content.keys() & self.answers.keys():
                del self.answers[k]  # 用过的答案不再答下一个问题
            return {"action": "accept", "content": content}
        self.questions.append({"message": p.get("message"),
                               "fields": {k: _field(v, k in required) for k, v in props.items()}})
        if self.sid and p.get("sessionId") == self.sid:
            self.conn.notify("session/cancel", {"sessionId": self.sid})
        return {"action": "cancel"}

    # ---- 对端通知

    def on_notify(self, method, params):
        if method != "session/update" or params.get("sessionId") not in (None, self.sid):
            return
        u = params.get("update") or {}
        kind = u.get("sessionUpdate")
        if kind == "usage_update" and isinstance(u.get("cost"), dict) and u["cost"].get("currency", "USD") == "USD":
            self.cost = u["cost"].get("amount")
        if kind == "config_option_update" and isinstance(u.get("configOptions"), list):
            self.config = u["configOptions"]
        if not self.prompting:
            return  # session/load 回放的历史、新会话的初始快照都不算本轮输出
        self.last_activity = time.time()
        if kind in ("agent_thought_chunk", "agent_thought", "agent_message_chunk", "agent_message"):
            self.output_since_progress = True
        self.write_status()
        if kind == "agent_message_chunk":
            self._append(u.get("messageId"), _text(u.get("content")))
            self._step("message", _text(u.get("content")))
        elif kind == "agent_message":
            self._replace(u.get("messageId"), u.get("content"))
        elif kind in SEGMENT_BREAKS:
            self.break_since_text = True
            if kind in ("tool_call", "tool_call_update"):
                self._track_tool(u)
            elif kind in ("agent_thought_chunk", "agent_thought"):
                c = u.get("content")
                self._step("thought", "".join(_text(x) for x in c) if isinstance(c, list) else _text(c),
                           replace=kind == "agent_thought")
        elif kind == "state_update" and self.version == 2:
            state = u.get("state")
            if state in ("running", "requires_action"):
                self.saw_active = True
            elif state == "idle" and self.saw_active:
                self.stop_reason = u.get("stopReason")
                if self.stop_reason == "error":
                    self.turn_error = (u.get("error") or {}).get("message") or "agent 报告 error"
                self.done.set()

    def _step(self, kind, text, replace=False):
        if not text:
            return
        if self.steps and self.steps[-1]["type"] == kind:
            self.steps[-1]["text"] = text if replace else self.steps[-1]["text"] + text
        else:
            self.steps.append({"type": kind, "text": text})

    def _track_tool(self, u):
        tid = u.get("toolCallId")
        if not tid:
            return
        t = self.tools.get(tid)
        new = t is None
        old_status = t.get("status") if t else None
        was_progress = self._progress_tool(t) if t else False
        if new:
            t = self.tools[tid] = {"paths": set()}
            self.steps.append({"type": "tool", "id": tid})
            if self.first_tool_s is None and self.prompt_started is not None:
                self.first_tool_s = time.monotonic() - self.prompt_started
        for k in ("title", "kind", "status", "rawInput"):
            if u.get(k):
                t[k] = u[k]
        had_diff = t.get("diff", False)
        t["diff"] = had_diff or any(c.get("type") == "diff" for c in u.get("content") or [])
        if self._progress_tool(t):
            if new or not was_progress or t.get("status") != old_status or t["diff"] != had_diff:
                self.last_progress = time.time()
                self.output_since_progress = self.read_since_progress = False
        else:
            self.output_since_progress = True
            if t.get("kind") != "think":
                self.read_since_progress = True
        if t.get("kind") in ("edit", "delete", "move") and self.first_edit_s is None and self.prompt_started is not None:
            self.first_edit_s = time.monotonic() - self.prompt_started
        for loc in u.get("locations") or []:
            t["paths"].add(loc.get("path"))
        for c in u.get("content") or []:
            if c.get("type") == "diff":
                t["paths"].add(c.get("path"))  # v1
                for ch in c.get("changes") or []:  # v2
                    t["paths"].update(ch.get(k) for k in ("path", "oldPath", "newPath", "fromPath", "toPath"))
        t["paths"].discard(None)

    def _progress_tool(self, t):
        return t.get("kind") in PROGRESS_KINDS or (not t.get("kind") and t.get("diff", False))

    def busy(self, progress_only=False):
        """有工具还在跑（长命令、测试）时不算卡住。"""
        return any(t.get("status") in (None, "pending", "in_progress")
                   for t in list(self.tools.values()) if (t.get("title") or t.get("kind"))
                   and (not progress_only or self._progress_tool(t)))

    def _account_time(self):
        """只在主线程轮询时累计工具和模型耗时。"""
        if self.prompt_started is None:
            return None
        now = time.monotonic()
        elapsed = max(0.0, now - self.timing_at)
        if self.busy():
            self.tool_s += elapsed
        else:
            self.model_s += elapsed
        self.timing_at = now
        return now

    def _check_head(self, timeout):
        now = time.monotonic()
        if not self.git_diff or now - self.head_checked < 15:
            return
        self.head_checked = now
        head = _git_head(self.cwd, timeout=timeout)
        if head and head != self.head:
            self.head = head
            self.last_progress = time.time()
            self.output_since_progress = self.read_since_progress = False
            if self.first_commit_s is None and self.prompt_started is not None:
                self.first_commit_s = now - self.prompt_started

    def timing(self):
        total = ((self.prompt_ended or time.monotonic()) - self.prompt_started) if self.prompt_started is not None else 0.0
        return {"total_s": round(total, 1), "tool_s": round(self.tool_s, 1), "model_s": round(self.model_s, 1),
                "first_tool_s": round(self.first_tool_s, 1) if self.first_tool_s is not None else None,
                "first_edit_s": round(self.first_edit_s, 1) if self.first_edit_s is not None else None,
                "first_commit_s": round(self.first_commit_s, 1) if self.first_commit_s is not None else None}

    def changed_paths(self):
        out = set()
        for t in self.tools.values():
            if t.get("kind") in ("edit", "delete", "move") and t.get("status") == "completed":
                out |= {str((self.cwd / p).resolve()) for p in t["paths"]}
        return out

    def commands(self):
        out = []
        for t in self.tools.values():
            if t.get("kind") != "execute":
                continue
            cmd = (t.get("rawInput") or {}).get("command") if isinstance(t.get("rawInput"), dict) else None
            cmd = " ".join(cmd) if isinstance(cmd, list) else cmd
            out.append({"command": cmd or t.get("title"), "status": t.get("status")})
        return out

    def full_steps(self):
        out = []
        for st in self.steps:
            if st["type"] != "tool":
                out.append(st)
                continue
            t = self.tools[st["id"]]
            out.append({"type": "tool", "title": t.get("title"), "kind": t.get("kind"), "status": t.get("status"),
                        "paths": sorted(t["paths"]) or None})
        return [{k: v for k, v in st.items() if v is not None} for st in out]

    def _key(self, mid):
        if mid:
            return mid
        if self.break_since_text or not self.segments:
            self.seg_counter += 1
        return f"_seg{self.seg_counter}"

    def _append(self, mid, text):
        key = self._key(mid)
        self.break_since_text = False
        if self.segments and self.segments[-1][0] == key:
            self.segments[-1][1] += text
        else:
            self.segments.append([key, text])

    def _replace(self, mid, content):
        if content is None or mid is None:
            return
        text = "".join(_text(c) for c in content) if isinstance(content, list) else ""
        for seg in self.segments:
            if seg[0] == mid:
                seg[1] = text
                return
        self.break_since_text = False
        self.segments.append([mid, text])

    def text(self):
        for _, t in reversed(self.segments):
            if t.strip():
                return t.strip()
        return None

    # ---- 进度快照

    def write_status(self, state="running", force=False, **extra):
        """给界面（如 hoobnn-agent-mods 的 relay-bar）读的 status.json：谁在跑、在干什么、最近几步。
        节流到每秒一次，先写临时文件再改名，读的一方不会读到半截。"""
        if not self.status_path:
            return
        with self.status_lock:  # 判断和写盘都在锁内：晚到的 running 快照不会盖掉结束时写的终态
            tick = time.monotonic()
            if self.status_final or (not force and tick - self.status_at < STATUS_EVERY):
                return
            self.status_at = tick
            self.status_final = state not in ("starting", "running")
            self._dump_status(state, time.time(), extra)

    def _dump_status(self, state, now, extra):
        def clip(t):
            return t if len(t) <= STATUS_CHARS else "…" + t[-STATUS_CHARS:]
        steps = []
        for st in self.steps[-STATUS_STEPS:]:
            if st["type"] == "tool":
                t = self.tools.get(st["id"], {})
                steps.append({"type": "tool", "title": t.get("title"), "kind": t.get("kind"), "status": t.get("status")})
            else:
                steps.append({"type": st["type"], "text": clip(st["text"])})
        named = [t for t in list(self.tools.values()) if t.get("title") or t.get("kind")]
        status = {
            "v": 1, "cli": self.a.cli, "model": self.a.model, "effort": self.a.effort,
            "pid": os.getpid(), "cwd": str(self.cwd), "prompt": self.prompt_head,
            "started": round(self.started, 3), "updated": round(now, 3), "state": state,
            "session_id": self.sid,
            "caller_session": os.environ.get("CLAUDE_CODE_SESSION_ID") or None,  # 界面据此只显示本会话派的活
            "tools": {"done": sum(t.get("status") in ("completed", "failed") for t in named), "total": len(named)},
            "timing": self.timing(), "steps": steps, **extra,
        }
        tmp = self.status_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(status, ensure_ascii=False))
            os.replace(tmp, self.status_path)
        except OSError:
            pass

    # ---- 生命周期

    def start(self, run_dir):
        cmd = agent_cmd(self.a.cli)
        if not cmd:
            raise RuntimeError(f"{self.a.cli} 的 ACP server 没装，先运行 relay.py install {self.spec.get('install')}")
        self.conn = Connection(cmd, self.cwd, run_dir, self.on_request, self.on_notify)
        req = self.a.protocol
        # v1 字段一并带上：对端选 1 时按 v1 读能力，v2 要求忽略未知字段
        params = {"protocolVersion": req, "clientInfo": CLIENT_INFO,
                  "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False,
                                         "elicitation": {"form": {}}}}
        if req == 2:
            params.update(info=CLIENT_INFO, capabilities={"elicitation": {"form": {}}})
        try:
            r = self.conn.request("initialize", params, 120)
        except RpcError as e:
            if e.code == -32022:
                raise RuntimeError(f"协议版本不兼容：请求 {req}，对端支持 {(e.data or {}).get('supported')}")
            raise
        self.version = r.get("protocolVersion")
        if self.version not in (1, 2) or self.version > req:
            raise RuntimeError(f"对端选了不支持的协议版本 {self.version}")
        if self.version == 2 and "capabilities" not in r and "agentCapabilities" in r:
            self.version = 1  # 声称 v2 却回 v1 结构（agy），按 v1 线协议走
        self.caps = (r.get("capabilities") if self.version == 2 else r.get("agentCapabilities")) or {}
        method = self.spec.get("auth")
        if method and method in [m.get("id") for m in r.get("authMethods") or []]:
            self.conn.request("auth/login" if self.version == 2 else "authenticate", {"methodId": method}, 120)

    def _prompt_caps(self):
        pc = (self.caps.get("session") or {}).get("prompt") if self.version == 2 else self.caps.get("promptCapabilities")
        return {k for k, v in (pc or {}).items() if v not in (None, False)}  # v1 是布尔，v2 是对象

    def _blocks(self, text):
        """文本在前，附件在后：图片内联；小文本文件在对端支持时嵌入内容，其余发 resource_link 让 agent 自己读。"""
        caps, blocks = self._prompt_caps(), [{"type": "text", "text": text}]
        for f in self.a.files:
            p = Path(f).expanduser().resolve()
            mime = mimetypes.guess_type(p.name)[0]
            if mime in IMAGE_TYPES:
                if "image" not in caps:
                    raise RuntimeError(f"{self.a.cli} 不接收图片：{f}")
                blocks.append({"type": "image", "mimeType": mime, "uri": p.as_uri(),
                               "data": base64.b64encode(p.read_bytes()).decode()})
                continue
            body = None
            if p.is_file() and "embeddedContext" in caps and p.stat().st_size <= EMBED_LIMIT:
                try:
                    body = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    pass
            if body is not None and "\0" not in body:
                blocks.append({"type": "resource", "resource": {"uri": p.as_uri(), "text": body,
                                                                "mimeType": mime or "text/plain"}})
            else:
                link = {"type": "resource_link", "uri": p.as_uri(), "name": p.name}
                if mime:
                    link["mimeType"] = mime
                blocks.append(link)
        return blocks

    def _session_caps(self):
        return (self.caps.get("session") or {}) if self.version == 2 else (self.caps.get("sessionCapabilities") or {})

    def open(self):
        params = {"cwd": str(self.cwd), "mcpServers": []}
        try:
            if self.a.resume:
                params["sessionId"] = self.a.resume
                if self.version == 2 or "resume" in self._session_caps():
                    r = self.conn.request("session/resume", params, 120)  # v2 不带 replayFrom：不回放历史
                elif self.caps.get("loadSession"):
                    r = self.conn.request("session/load", params, 300)
                else:
                    raise RuntimeError(f"{self.a.cli} 不支持续接会话")
                self.sid = self.a.resume
            else:
                r = self.conn.request("session/new", params, 120)
                self.sid = r.get("sessionId")
        except RpcError as e:
            if e.code == -32000:
                raise RuntimeError(f"{self.a.cli} 需要先登录（{e}），在终端里登录一次后重试")
            raise
        self.config = r.get("configOptions") or self.config or []
        self.modes, self.models = r.get("modes"), r.get("models")

    def configure(self):
        if self.a.model:
            self._set_category("model", self.a.model)
        if self.a.effort:
            self._set_category("thought_level", self.a.effort)

    def _opt_id(self, opt):
        return opt.get("configId") or opt.get("id")

    def _set(self, cid, value):
        params = {"sessionId": self.sid, "configId": cid, "value": value}
        if self.version == 2:
            params["type"] = "boolean" if isinstance(value, bool) else "id"
        r = self.conn.request("session/set_config_option", params, 60)
        self.config = r.get("configOptions") or self.config

    def _set_category(self, category, wanted):
        opt = next((o for o in self.config if o.get("category") == category), None)
        if opt:
            values = _flat_values(opt)
            match, candidates = _match(wanted, opt)
            if not match:
                if candidates:
                    raise RuntimeError(f"{wanted} 匹配到多个取值，写全其中一个：{', '.join(candidates)}")
                raise RuntimeError(f"{self._opt_id(opt)} 没有匹配 {wanted} 的取值，可选：{', '.join(values[:40])}"
                                   + (f" 等 {len(values)} 个，用 relay.py options {self.a.cli} 查看全部" if len(values) > 40 else ""))
            self._set(self._opt_id(opt), match)
        elif category == "model" and self.models:  # v1 的 unstable session/set_model
            ids = [m.get("modelId") for m in self.models.get("availableModels") or []]
            match = wanted if wanted in ids else next((i for i in ids if i.lower() == wanted.lower()), None)
            if not match:
                raise RuntimeError(f"没有模型 {wanted}，用 relay.py options {self.a.cli} 查看可选值")
            self.conn.request("session/set_model", {"sessionId": self.sid, "modelId": match}, 60)
        else:
            label = {"model": "模型", "thought_level": "推理强度"}[category]
            raise RuntimeError(f"{self.a.cli} 的 ACP 会话没有提供{label}选项")

    def prompt(self, text, deadline):
        """v1 以 prompt 响应为本轮结束；v2 的响应只确认插入，结束看 idle 的 state_update。
        按秒轮询，检查总超时、空闲超时和只思考不动手的空转，并累计耗时。"""
        self.prompting = True
        blocks = self._blocks(text)
        self.last_activity = self.last_progress = time.time()
        self.output_since_progress = self.read_since_progress = False
        self.prompt_started = self.timing_at = time.monotonic()
        try:
            q = self.conn.send("session/prompt", {"sessionId": self.sid, "prompt": blocks})
            while not self.done.is_set():
                if KILLED.is_set():
                    raise KilledError()
                try:
                    r = q.get(timeout=1)
                except queue.Empty:
                    r = None
                self._account_time()
                self._check_head(max(1, min(5, deadline - time.time())))
                if r is not None:
                    q = queue.Queue()  # 响应只处理一次
                    if "error" in r:
                        raise RpcError(r["error"])
                    r = r.get("result") or {}
                    if self.version == 1 or "stopReason" in r:
                        self.stop_reason = r.get("stopReason")
                        self.done.set()
                        break
                    self.saw_active = True
                self.write_status()  # 节流时丢下的最后一次变化，在这里补上
                now = time.time()
                if now >= deadline:
                    raise TimeoutError("session/prompt")
                if self.a.idle_timeout and now - self.last_activity > self.a.idle_timeout and not self.busy():
                    raise IdleError(self.a.idle_timeout)
                if (self.a.work_timeout and self.output_since_progress
                        and now - self.last_progress > self.a.work_timeout and not self.busy(progress_only=True)):
                    raise StallError(self.a.work_timeout)
        finally:
            self.prompting = False
            try:
                self.prompt_ended = self._account_time()
            except Exception:
                self.prompt_ended = time.monotonic()

    def cancel(self):
        if self.sid and not self.done.is_set():
            self.conn.notify("session/cancel", {"sessionId": self.sid})
            self.done.wait(10)

    def close(self):
        if self.sid and (self.version == 2 or "close" in self._session_caps()):
            try:
                self.conn.request("session/close", {"sessionId": self.sid}, 10)
            except Exception:
                pass
        self.conn.close()


def _text(content):
    if isinstance(content, dict) and content.get("type") == "text":
        return content.get("text") or ""
    return ""


def _field(prop, required):
    """把 elicitation 的字段 schema 压成调用方好读的样子：标题、说明、类型、可选值。"""
    items = prop.get("items") or {}
    options = [o.get("const") for o in prop.get("oneOf") or items.get("anyOf") or []] or prop.get("enum") or items.get("enum")
    out = {"title": prop.get("title"), "description": prop.get("description"), "type": prop.get("type"),
           "options": options, "default": prop.get("default"), "required": required}
    return {k: v for k, v in out.items() if v not in (None, [])}


def _auto_choice(prop, mode):
    items = prop.get("items") or {}
    choices = prop.get("oneOf") or prop.get("anyOf") or items.get("oneOf") or items.get("anyOf")
    if choices:
        pairs = [(o.get("const"), o.get("title", "")) for o in choices if "const" in o]
    else:
        values = prop.get("enum") or items.get("enum") or []
        titles = prop.get("enumNames") or items.get("enumNames") or []
        pairs = [(v, titles[i] if i < len(titles) else "") for i, v in enumerate(values)]
    recommended = [v for v, title in pairs if re.search(r"recommended|推荐", str(title) + " " + str(v), re.I)]
    value = recommended[0] if recommended else (pairs[0][0] if mode == "first" and pairs else None)
    return [value] if value is not None and prop.get("type") == "array" else value


def _coerce(value, prop):
    kind = prop.get("type")
    if kind == "integer":
        return int(value)
    if kind == "number":
        return float(value)
    if kind == "boolean":
        return value.strip().lower() in ("true", "1", "yes", "y", "是")
    if kind == "array":
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


def _flat_values(opt):
    vals = []
    for o in opt.get("options") or []:
        if "options" in o:  # 分组
            vals += [x.get("value") for x in o["options"]]
        elif "value" in o:
            vals.append(o["value"])
    return vals


def _flat(value):
    """dsh 的模型取值是 JSON 数组 ["provider","model"]，摊平成 provider/model 再比较。"""
    try:
        parts = json.loads(value)
    except ValueError:
        return value
    return "/".join(parts) if isinstance(parts, list) and all(isinstance(p, str) for p in parts) else value


def _match(wanted, opt):
    """按 value 精确、name 精确、value 后缀、唯一子串的顺序匹配用户写的模型 / 强度，返回 (取值, 候选)。"""
    pairs = []
    for o in opt.get("options") or []:
        pairs += [(x.get("value"), x.get("name") or "") for x in (o["options"] if "options" in o else [o])]
    flat = {v: _flat(v) for v, _ in pairs}
    w = wanted.lower()
    for test in (lambda v, n: wanted in (v, flat[v]), lambda v, n: n.lower() == w,
                 lambda v, n: flat[v].lower().endswith("/" + w) or flat[v].lower().endswith("~" + w)):
        hits = [v for v, n in pairs if test(v, n)]
        if len(hits) == 1:
            return hits[0], hits
    hits = [v for v, n in pairs if w in flat[v].lower() or w in n.lower()]
    return (hits[0] if len(hits) == 1 else None), hits


# ---------------------------------------------------------------- 进程与日志


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
    # agent 会把命令放进新的会话 / 进程组，只杀进程组会留下孤儿，所以按父子关系收集整棵树
    pids = [proc.pid, *_descendants(proc.pid)]
    for sig in (signal.SIGTERM, signal.SIGKILL):
        alive = False
        for p in pids:
            try:
                os.kill(p, sig)
                alive = True
            except (ProcessLookupError, PermissionError):
                pass
        if not alive:
            return
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        if sig == signal.SIGTERM:
            time.sleep(1)


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


def _new_run_dir(cli):
    _prune_runs()
    d = STATE_DIR / "runs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{cli}-{uuid.uuid4().hex[:6]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _litter_guard(cli, cwd):
    """记下 agent 会在会话目录里乱建的路径，返回一个只删除本次新建部分的清理函数。"""
    fresh = [cwd / rel for rel in AGENTS[cli].get("litter", []) if not (cwd / rel).exists()]

    def clean():
        for path in fresh:
            if not path.exists():
                continue
            shutil.rmtree(path, ignore_errors=True)
            parent = path.parent
            while parent != cwd and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    return clean


def _git_output(cwd, *args, timeout=60):
    """取 git 输出；失败或超时都当作没有。"""
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.decode(errors="replace") if r.returncode == 0 else None


def _git_head_start(cwd):
    """返回（是否追踪提交，HEAD）；空仓库是（True, None）。"""
    cmd = ["git", "-C", str(cwd)]
    try:
        repo = subprocess.run([*cmd, "rev-parse", "--git-dir"], capture_output=True, timeout=60)
        if repo.returncode:
            return False, None
        head = subprocess.run([*cmd, "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, timeout=60)
        if head.returncode:
            ref = subprocess.run([*cmd, "symbolic-ref", "-q", "HEAD"], capture_output=True, timeout=60)
            if ref.returncode:
                return False, None
            name = ref.stdout.decode(errors="replace").strip()
            present = subprocess.run([*cmd, "show-ref", "--verify", "--quiet", name], capture_output=True, timeout=60)
            return present.returncode == 1, None
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    return True, head.stdout.decode(errors="replace").strip() or None


def _git_head(cwd, timeout=60):
    return (_git_output(cwd, "rev-parse", "--verify", "-q", "HEAD", timeout=timeout) or "").strip() or None


def _git_original_refs(cwd, timeout=5):
    refs = _git_output(cwd, "for-each-ref", "--format=%(refname)", "refs/original/", timeout=timeout)
    return set(refs.splitlines()) if refs is not None else None


def _git_history(cwd, head_before, head_after, refs_before):
    """历史检查共用 5 秒预算；失败时提示未能确认，不把超时当成改写。"""
    deadline = time.monotonic() + 5
    rewritten, warnings = False, []
    if head_before and head_after:
        try:
            r = subprocess.run(["git", "-C", str(cwd), "merge-base", "--is-ancestor", head_before, head_after],
                               capture_output=True, timeout=max(0.01, deadline - time.monotonic()))
            rewritten = r.returncode == 1
            if r.returncode not in (0, 1):
                warnings.append("无法确认运行前 HEAD 的祖先关系")
        except (OSError, subprocess.TimeoutExpired):
            warnings.append("历史祖先检查失败或超时")
    refs_after = _git_original_refs(cwd, timeout=max(0.01, deadline - time.monotonic()))
    if refs_before is not None and refs_after is not None:
        rewritten |= bool(refs_after - refs_before)
    else:
        warnings.append("无法确认 refs/original/* 是否新增")
    if rewritten:
        warnings.append(f"历史被改写：运行前 HEAD={head_before}，当前 HEAD={head_after}；"
                        f"先保存当前 tree，再 git reset --hard {head_before}，然后摘取保存的 tree")
    return rewritten, warnings


def _git_snapshot(cwd):
    """工作区里未提交文件的内容指纹；不是 git 仓库时返回 None。"""
    def git(*args):
        return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, timeout=60)
    try:
        top = git("rev-parse", "--show-toplevel")
        status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    except (OSError, subprocess.TimeoutExpired):
        return None
    if top.returncode or status.returncode:
        return None
    root = Path(top.stdout.decode().strip())
    snap, entries = {}, status.stdout.decode(errors="replace").split("\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        if e[0] in "RC":
            i += 1  # 改名后面跟着原路径
        f = root / e[3:]
        try:
            snap[str(f)] = e[:2] + (hashlib.sha1(f.read_bytes()).hexdigest() if f.is_file() else "")
        except OSError:
            snap[str(f)] = e[:2]
    return snap


def _git_commits(cwd, head_before, head_after):
    """运行期间新增的提交及其文件；非 git 仓库时返回 None。"""
    top = _git_output(cwd, "rev-parse", "--show-toplevel")
    if top is None:
        return None
    commits, paths = [], set()
    if head_after and head_before != head_after:
        rev = f"{head_before}..{head_after}" if head_before else head_after
        log = _git_output(cwd, "log", "--format=%H%x00%s", rev)
        if log:
            for line in log.splitlines():
                sha, _, subject = line.partition("\0")
                if sha:
                    commits.append({"sha": sha[:12], "subject": subject})
        if head_before:
            changed = _git_output(cwd, "diff", "--name-only", "-z", head_before, head_after)
        else:
            changed = _git_output(cwd, "log", "--name-only", "-z", "--format=", head_after)
        root = Path(top.strip())
        paths = {str(root / path) for path in (changed or "").split("\0") if path}
    return commits, paths


def _files_changed(before, after, reported, cwd):
    """git 前后快照的差异（能抓到 shell 写的文件）加上工具调用上报的路径（能抓到仓库外的文件）。"""
    paths = set(reported)
    if before is not None and after is not None:
        paths |= {f for f in after.keys() | before.keys() if after.get(f) != before.get(f)}
    out = []
    for f in sorted(paths):
        try:
            out.append(str(Path(f).relative_to(cwd)))
        except ValueError:
            out.append(f)
    return out


def _error_kind(error):
    """按错误全文分类，额度优先于限流。"""
    if not error:
        return None
    patterns = (
        ("resume_cwd", r"does not belong to cwd"),
        ("quota", r"usage limit|quota|insufficient[_ ]?(balance|credit|funds)|credit balance|额度|余额不足|限额"),
        ("rate_limit", r"rate[ _-]?limit|too many requests|\b429\b"),
        ("auth", r"authenticat|unauthori[sz]ed|invalid api key|api key.{0,40}invalid|\b401\b"),
    )
    return next((kind for kind, pattern in patterns if re.search(pattern, error, re.IGNORECASE)), "error")


def _resume_cwd(session_id):
    runs = STATE_DIR / "runs"
    if not runs.is_dir():
        return None
    for path in sorted(runs.glob("*/result.json"), key=lambda p: p.parent.name, reverse=True):
        try:
            result = json.loads(path.read_text())
            if result.get("session_id") == session_id and result.get("cwd"):
                return result["cwd"]
        except (OSError, ValueError, TypeError):
            continue
    return None


def execute(a, prompt, git_diff=True):
    """跑一轮，返回统一结果。git_diff=False 时只按工具调用统计改动（多家并发跑同一目录时互相分不清）。"""
    cwd = Path(a.cwd or os.getcwd()).resolve()
    timeout_warning = a.asks == "allow" and a.work_timeout > 0 and (a.work_timeout >= a.timeout or a.work_timeout > 1800)
    if timeout_warning:
        print("提示：空转检测实际上已关闭（阈值过长）", file=sys.stderr)
    previous_cwd = _resume_cwd(a.resume) if a.resume else None
    run_dir = _new_run_dir(a.cli)
    clean_litter = _litter_guard(a.cli, cwd)
    before = _git_snapshot(cwd) if git_diff else None
    track_commits, head_before = _git_head_start(cwd) if git_diff else (False, None)
    refs_before = _git_original_refs(cwd) if track_commits else None
    deadline = time.time() + a.timeout
    s = Session(a, cwd)
    s.git_diff, s.head = track_commits, head_before
    s.status_path, s.prompt_head = run_dir / "status.json", " ".join(prompt.split())[:200]
    s.write_status("starting", force=True)
    error = error_kind = None
    try:
        if previous_cwd and Path(previous_cwd).resolve() != cwd:
            raise RuntimeError(f"会话原 cwd 为 {previous_cwd}，本次为 {cwd}；换目录请开新会话，把上下文写进 prompt")
        s.start(run_dir)
        s.open()
        s.configure()
        s.prompt(prompt, deadline)
    except KilledError:
        error, error_kind = f"收到 {signal.Signals(KILL_SIGNAL).name}，已取消", "killed"
        if s.conn:
            s.cancel()
    except TimeoutError:
        error, error_kind = f"超过 {a.timeout}s 被终止", "timeout"
        if s.conn:
            s.cancel()
    except IdleError:
        error = f"连续 {a.idle_timeout}s 没有任何输出、也没有工具在跑，判定卡住，已取消；会话还在，可以重跑或续接"
        error_kind = "idle"
        if s.conn:
            s.cancel()
    except StallError:
        activity = "只在读、搜索或抓取，没有写入或执行进展" if s.read_since_progress else "只在想或输出文字，没有动手进展"
        error = f"连续 {a.work_timeout}s {activity}，判定空转，已取消；会话还在，可以续接并要求先动手"
        error_kind = "stalled"
        if s.conn:
            s.cancel()
    except (RpcError, RuntimeError) as e:
        error = str(e)
        if previous_cwd and Path(previous_cwd).resolve() != cwd:
            error_kind = "resume_cwd"
    except Exception as e:  # 协议对不上也要把日志位置交回去
        error = f"{type(e).__name__}: {e}"
    finally:
        if s.conn:
            s.close()
        clean_litter()
    after = _git_snapshot(cwd) if before is not None else None
    head_after = _git_head(cwd, timeout=5) if track_commits else None
    history_rewritten, warnings = _git_history(cwd, head_before, head_after, refs_before) if track_commits else (False, [])
    if timeout_warning:
        warnings.append("空转检测实际上已关闭（阈值过长）")
    if head_after and head_before != head_after and s.first_commit_s is None and s.prompt_started is not None:
        s.first_commit_s = (s.prompt_ended or time.monotonic()) - s.prompt_started
    git_info = _git_commits(cwd, head_before, head_after) if track_commits else None

    if KILLED.is_set():
        error, error_kind = f"收到 {signal.Signals(KILL_SIGNAL).name}，已取消", "killed"
    if not error and s.turn_error:
        error = s.turn_error
    if not error and s.stop_reason not in (None, "end_turn", "max_tokens", "max_turn_requests"):
        error = f"stopReason={s.stop_reason}"
    if s.questions and (not error or error == "stopReason=cancelled"):
        error = "agent 在等回答 questions 里的问题：带 --resume 和 --answer 字段=取值 重跑，或在 prompt 里直接回答"
        error_kind = "asked"
    if error and s.conn and s.conn.proc.returncode not in (0, None, -15, -9):
        tail = (run_dir / "stderr").read_text(errors="replace").strip()[-600:]
        error = f"{error}；stderr：{tail}" if tail else error

    text = s.text()
    final_error = error or (None if text else "agent 没有返回文本")
    error_kind = error_kind or _error_kind(final_error)
    if error_kind == "resume_cwd" and "换目录" not in final_error:
        final_error += "；换目录请开新会话，把上下文写进 prompt"
    commits, committed_paths = git_info or (None, set())
    result = {
        "ok": not error and bool(text),
        "text": text,
        "session_id": s.sid,
        "cli": a.cli,
        "cwd": str(cwd),
        "cost_usd": s.cost,
        "error": final_error,
        "error_kind": error_kind,
        "log": str(run_dir),
        "protocol_version": s.version,
        "stop_reason": s.stop_reason,
        "timing": s.timing(),
        "files_changed": _files_changed(before, after, s.changed_paths() | committed_paths, cwd),
        "commands": s.commands(),
        "warnings": warnings,
    }
    if after is not None:
        changed = {f for f in after if before.get(f) != after[f]} | (committed_paths & after.keys())
        result["uncommitted"] = _files_changed(None, None, changed, cwd)
        if not result["ok"] and changed:
            warnings.append(f"有 {len(changed)} 个未提交改动，续接或换人接手前先审视（可 git diff 查看）")
    if s.auto_answers:
        result["auto_answers"] = s.auto_answers
    if commits is not None:
        result["commits"] = commits
        result["history_rewritten"] = history_rewritten
    if s.permissions:
        result["permissions"] = s.permissions
    if s.questions:
        result["questions"] = s.questions
    if a.full:
        result["steps"] = s.full_steps()
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    s.write_status("asked" if result["error_kind"] == "asked" else "done" if result["ok"] else "failed", force=True,
                   ok=result["ok"], error=result["error"], error_kind=result["error_kind"], files_changed=len(result["files_changed"]),
                   commits=len(result.get("commits", [])), cost_usd=s.cost, ended=round(time.time(), 3))
    return result


# ---------------------------------------------------------------- 命令


def _ns(**kw):
    base = dict(cli=None, model=None, effort=None, resume=None, cwd=None, timeout=300,
                protocol=LATEST_PROTOCOL, files=[], answers={}, auto_answer=None, asks="allow", full=False, idle_timeout=300, work_timeout=0)
    base.update(kw)
    return argparse.Namespace(**base)


def _installed(cli):
    cmd = agent_cmd(cli)
    return bool(cmd) and (shutil.which(cmd[0]) is not None or Path(cmd[0]).exists())


def _solid_png(rgb, size=32):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    rows = b"".join(b"\0" + bytes(rgb) * size for _ in range(size))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def _check_cli(cli, model, timeout, protocol):
    """四项冒烟测试：回复 OK、续会话能取回上一轮信息、按本机权限配置能写文件、读到随 prompt 附带的文本和图片。"""
    report = {"cli": cli, "checks": {}, "cost_usd": 0.0}

    def record(name, passed, r, detail=None):
        report["checks"][name] = {"pass": passed, "detail": detail or (r.get("error") or r.get("text")),
                                  "log": r.get("log")}
        report["cost_usd"] += r.get("cost_usd") or 0
        report["protocol_version"] = r.get("protocol_version") or report.get("protocol_version")

    with tempfile.TemporaryDirectory(prefix=f"relay-check-{cli}-") as tmp:
        work = Path(tmp)
        subprocess.run(["git", "init", "-q", str(work)], check=False)
        ns = lambda **kw: _ns(cli=cli, model=model, timeout=timeout, protocol=protocol, cwd=work, **kw)

        r = execute(ns(), "只回复两个字母: OK")
        record("reply", r["ok"] and "OK" in (r["text"] or "").upper(), r)

        r1 = execute(ns(), "这是一个会话续接测试。请记住数字 7381，现在只回复: 好")
        if r1["session_id"]:
            r2 = execute(ns(resume=r1["session_id"]), "上一轮让你记住的数字是多少？只回复这个数字")
            record("resume", r2["ok"] and "7381" in (r2["text"] or ""), r2)
        else:
            record("resume", False, r1, "第一轮没有返回 session_id")

        r = execute(ns(), "在当前目录创建文件 probe.txt，内容为 hello，然后回复 DONE。")
        wrote = (work / "probe.txt").exists()
        record("write", wrote, r, "probe.txt 已写出" if wrote else None)

        notes, image = Path(tmp) / "notes.md", Path(tmp) / "swatch.png"  # 附件放在仓库外，测的是随 prompt 送达
        notes.write_text("暗号：4619\n")
        image.write_bytes(_solid_png((220, 20, 20)))
        r = execute(ns(files=[str(notes), str(image)]), "附件里的文本给了一个暗号，图片是一块纯色。只回复：暗号 颜色（中文）")
        record("attach", r["ok"] and "4619" in (r["text"] or "") and "红" in (r["text"] or ""), r)

    report["pass"] = all(c["pass"] is not False for c in report["checks"].values())
    report["cost_usd"] = round(report["cost_usd"], 4)
    return report


def cmd_check(a):
    clis = a.cli or [c for c in AGENTS if _installed(c)]
    for c in clis:
        if c not in AGENTS:
            sys.exit(f"未知 agent：{c}，可选 {', '.join(AGENTS)}")
    with ThreadPoolExecutor(max_workers=len(clis)) as pool:
        reports = list(pool.map(lambda c: _check_cli(c, a.model, a.timeout, a.protocol), clis))
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    sys.exit(0 if all(r["pass"] for r in reports) else 1)


def _show_data(path, tail):
    path = Path(path).expanduser()
    if path.is_dir():
        result = path / "result.json"
        path = result if result.exists() else path / "status.json"
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("需要单个运行结果")
    keys = ("cli", "ok", "error_kind", "error", "session_id", "timing", "commits", "uncommitted",
            "warnings", "questions", "auto_answers", "state", "steps", "tools", "cwd")
    out = {k: data[k] for k in keys if k in data}
    if "cli" not in out:
        parts = path.parent.name.split("-")
        if len(parts) >= 4:
            out["cli"] = parts[-2]
    if "text" in data:
        out["text"] = (data["text"] or "")[-tail:] if tail else ""
    if "steps" in out:
        out["steps"] = out["steps"][-5:]
    return out


def cmd_show(a):
    if a.tail < 0:
        sys.exit("--tail 不能为负数")
    if a.latest is not None:
        runs = STATE_DIR / "runs"
        dirs = sorted((p for p in runs.glob("*") if p.is_dir() and
                       (not a.latest or f"-{a.latest}-" in p.name) and
                       ((p / "result.json").exists() or (p / "status.json").exists())), reverse=True)
        if not dirs:
            sys.exit("没有找到运行记录")
        path = dirs[0]
    elif a.path:
        path = a.path
    else:
        sys.exit("请提供结果文件、运行目录或 --latest")
    try:
        data = _show_data(path, a.tail)
    except (OSError, ValueError) as e:
        sys.exit(f"无法读取运行记录：{e}")
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for key, value in data.items():
            if key == "text":
                print(f"text（末尾）：\n{value}")
            elif isinstance(value, (dict, list)):
                print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                print(f"{key}: {value}")


def cmd_options(a):
    if a.cli not in AGENTS:
        sys.exit(f"未知 agent：{a.cli}，可选 {', '.join(AGENTS)}")
    cwd = Path(a.cwd or os.getcwd()).resolve()
    s = Session(_ns(cli=a.cli, cwd=a.cwd, protocol=a.protocol), cwd)
    clean_litter = _litter_guard(a.cli, cwd)
    try:
        s.start(_new_run_dir(a.cli))
        s.open()
        out = {"protocol_version": s.version, "configOptions": [
            {"id": s._opt_id(o), "category": o.get("category"), "current": o.get("currentValue"),
             "values": _flat_values(o) if o.get("type") != "boolean" else [True, False]} for o in s.config]}
        if s.modes:
            out["modes"] = [m.get("id") for m in s.modes.get("availableModes") or []]
        if s.models and not any(o.get("category") == "model" for o in s.config):
            out["models"] = [m.get("modelId") for m in s.models.get("availableModels") or []]
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except (RpcError, RuntimeError, TimeoutError) as e:
        sys.exit(f"失败：{e}")
    finally:
        if s.conn:
            s.close()
        clean_litter()


def cmd_install(a):
    if a.cli != "agy":
        sys.exit("只有 agy 需要单独安装 ACP server；其余走本机 CLI 或 npx")
    key = _platform_key()
    if key not in AGY_ACP["archives"]:
        sys.exit(f"ACP 注册表没有 {key} 的 agy ACP server")
    url, sha, _ = AGY_ACP["archives"][key]
    dest = STATE_DIR / "agents" / "agy" / AGY_ACP["version"]
    dest.mkdir(parents=True, exist_ok=True)
    data = urllib.request.urlopen(url, timeout=300).read()
    if hashlib.sha256(data).hexdigest() != sha:
        sys.exit("sha256 校验失败，没有安装")
    archive = dest / "server.zip"
    archive.write_bytes(data)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            z.extract(info, dest)
            mode = info.external_attr >> 16  # zipfile 不保留权限，按归档里的位补回可执行
            if mode & 0o111:
                (dest / info.filename).chmod(mode & 0o777)
    archive.unlink()
    print(json.dumps({"installed": str(dest / AGY_ACP["cmd"]), "version": AGY_ACP["version"]}, ensure_ascii=False))


def cmd_outdated(a):
    """对照 ACP 注册表看钉住的适配器；本机自带 ACP 的 CLI（grok / opencode / mcode / hermes / dsh）由它们自己升级。"""
    req = urllib.request.Request(REGISTRY_URL, headers={"User-Agent": f"agent-relay/{CLIENT_INFO['version']}"})
    reg = json.loads(urllib.request.urlopen(req, timeout=60).read())  # 默认的 Python-urllib UA 会被 CDN 拒
    entries = {e["id"]: e for e in reg.get("agents") or []}
    out = []
    for cli, spec in AGENTS.items():
        e = entries.get(spec.get("registry"))
        if not e:
            continue
        if cli == "agy":
            pinned = AGY_ACP["version"]
            update = {"version": e["version"], "archives": {
                k: (v["archive"], v["sha256"], v.get("args") or []) for k, v in e["distribution"]["binary"].items()
                if k in AGY_ACP["archives"] or k.startswith(("darwin", "linux"))}}
        else:
            pinned = spec["cmd"][-1].rsplit("@", 1)[1]
            update = {"cmd": ["npx", "-y", e["distribution"]["npx"]["package"]]}
        row = {"cli": cli, "pinned": pinned, "latest": e["version"], "outdated": pinned != e["version"]}
        if row["outdated"]:
            row["update"] = update  # 改 AGENTS / AGY_ACP 后跑 check，agy 还要重新 install
        out.append(row)
    print(json.dumps(out, ensure_ascii=False, indent=2))


def _per_cli(values, cli):
    """--model / --effort 可写 M（所有 agent 共用）或 CLI=M（只给这一家）。"""
    plain = [v for v in values if v.split("=", 1)[0] not in AGENTS]
    scoped = [v.split("=", 1)[1] for v in values if v.split("=", 1)[0] == cli]
    return (scoped or plain or [None])[-1]


def cmd_run(a):
    clis = a.cli.split(",")
    for cli in clis:
        if cli not in AGENTS:
            sys.exit(f"未知 agent：{cli}，可选 {', '.join(AGENTS)}")
        if not _installed(cli):
            hint = f"，先运行 relay.py install {AGENTS[cli]['install']}" if AGENTS[cli].get("install") else ""
            sys.exit(f"{cli} 的 ACP server 不可用{hint}")
    if len(clis) > 1 and a.resume:
        sys.exit("--resume 只能接一家的会话")
    prompt = a.prompt
    if a.prompt_file:
        prompt = Path(a.prompt_file).read_text()
    elif prompt in (None, "-"):
        prompt = sys.stdin.read()
    if not prompt or not prompt.strip():
        sys.exit("prompt 为空")
    for f in a.files:
        if not Path(f).expanduser().exists():
            sys.exit(f"附件不存在：{f}")
    if any("=" not in x for x in a.answer):
        sys.exit("--answer 要写成 字段=取值")
    a.answers = dict(x.split("=", 1) for x in a.answer)

    def one(cli):
        ns = argparse.Namespace(**{**vars(a), "cli": cli, "model": _per_cli(a.model, cli),
                                   "effort": _per_cli(a.effort, cli)})
        return execute(ns, prompt, git_diff=len(clis) == 1)
    if len(clis) == 1:
        result = one(clis[0])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["ok"] else 1)
    with ThreadPoolExecutor(max_workers=len(clis)) as pool:
        results = [{"cli": c, **r} for c, r in zip(clis, pool.map(one, clis))]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    sys.exit(0 if all(r["ok"] for r in results) else 1)


def main():
    p = argparse.ArgumentParser(description="通过 ACP 调用其他 agent 并统一输出")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="运行一轮任务")
    r.add_argument("cli", help=" / ".join(AGENTS) + "；逗号分隔多家时并行跑同一个 prompt，输出数组")
    r.add_argument("prompt", nargs="?", help="任务文本；写 - 或省略则从 stdin 读")
    r.add_argument("--prompt-file", help="从文件读任务文本")
    r.add_argument("--model", action="append", default=[],
                   help="模型，匹配会话 config option 的取值或名称；多家时可重复写 CLI=模型")
    r.add_argument("--effort", action="append", default=[],
                   help="推理强度，匹配 thought_level 类 config option 的取值；多家时可重复写 CLI=强度")
    r.add_argument("--resume", help="上一轮返回的 session_id")
    r.add_argument("--file", dest="files", action="append", default=[],
                   help="附件，可重复：图片内联，文本文件按对端能力嵌入或发链接")
    r.add_argument("--answer", action="append", default=[],
                   help="代答 agent 的反问，写成 字段=取值，可重复；字段名见上一轮输出的 questions")
    r.add_argument("--auto-answer", choices=("recommended", "first"), help="自动选择推荐选项；first 在没有推荐时选第一项")
    r.add_argument("--cwd", help="工作目录，默认当前目录")
    r.add_argument("--timeout", type=int, default=1200, help="秒，默认 1200")
    r.add_argument("--idle-timeout", type=int, default=300,
                   help="连续多少秒没有任何输出、也没有工具在跑就判定卡住，默认 300，0 关闭")
    r.add_argument("--work-timeout", type=int, default=900,
                   help="连续多少秒只读或思考、没有写入或执行进展就判定空转，默认 900，0 关闭")
    r.add_argument("--asks", choices=("allow", "deny"), default="allow",
                   help="agent 按本机配置来问权限时：allow 代为放行（默认），deny 当成拒绝")
    r.add_argument("--full", action="store_true", help="输出里附上完整过程 steps：消息、思考、工具调用")
    show = sub.add_parser("show", help="查看运行结果或当前进度")
    show.add_argument("path", nargs="?", help="结果 JSON 或运行目录")
    show.add_argument("--latest", nargs="?", const="", metavar="CLI", help="查看最近一次运行，可按 agent 筛选")
    show.add_argument("--tail", type=int, default=2000, help="回答末尾字符数，默认 2000")
    show.add_argument("--json", action="store_true", help="输出精简 JSON")
    o = sub.add_parser("options", help="列出 agent 的模型、推理强度、模式等配置项")
    o.add_argument("cli")
    o.add_argument("--cwd")
    c = sub.add_parser("check", help="冒烟测试：回复、续会话、写文件、附件；agent 升级后跑一遍")
    c.add_argument("cli", nargs="*", help="要测的 agent，默认测本机可用的全部")
    c.add_argument("--model", help="测试用的模型，省钱可指定便宜的")
    c.add_argument("--timeout", type=int, default=300, help="每次调用的超时秒数，默认 300")
    i = sub.add_parser("install", help="安装需要单独下载的 ACP server（目前只有 agy）")
    i.add_argument("cli")
    sub.add_parser("outdated", help="对照 ACP 注册表，列出钉住的适配器有没有新版本")
    for sp in (r, o, c):
        sp.add_argument("--protocol", type=int, choices=(1, 2), default=LATEST_PROTOCOL,
                        help="请求的 ACP 协议版本，默认 2（v2 草案），对端只支持 v1 时自动回落")
    a = p.parse_args()
    if a.command in ("run", "check"):
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, _on_signal)
    {"run": cmd_run, "show": cmd_show, "check": cmd_check, "options": cmd_options, "install": cmd_install,
     "outdated": cmd_outdated}[a.command](a)


if __name__ == "__main__":
    main()
