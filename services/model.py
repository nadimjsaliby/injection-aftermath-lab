#!/usr/bin/env python3
"""Obedient model stub: the one mocked component of the lab.

It speaks enough of the Anthropic Messages API and the OpenAI Responses API for
the unmodified agent CLIs to run against it. It does not sample anything. It
replays a fixed benign plan and, in between, obeys every `lab-directive:` token
that appears in a tool result (see directives.py). That models the study's
premise: the agent has already decided to follow the injected instruction.

Every request and response is logged with a timestamp. The scorer uses that log
(a) as the record of which steps were issued and when, and (b) as the stand-in
for an LLM gateway log when it grades evidence sources.
"""
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import directives
import runlog

MODEL_ID = "lab-obedient-1"
STATE = {"pre": [], "benign": [], "final": "Done."}


def log(kind, record):
    runlog.log("gateway", dict(record, kind=kind))


def tool_names(tools):
    return [t.get("name") or t.get("type") or "" for t in tools or []]


def find_mcp(names, server, tool):
    for n in names:
        if server in n and n.endswith(tool):
            return n
    return None


def namespaced(tools, server, tool):
    """Codex groups each MCP server's tools under a namespace entry."""
    for t in tools or []:
        if t.get("type") == "namespace" and server in t.get("name", ""):
            if any(sub.get("name") == tool for sub in t.get("tools", [])):
                return t["name"]
    return None


def to_claude(step, names):
    op = step["op"]
    if op == "shell":
        return "Bash", {"command": step["cmd"], "description": step.get("desc", "Run command")}
    if op == "read":
        return "Read", {"file_path": step["path"]}
    if op == "write":
        return "Write", {"file_path": step["path"], "content": step["content"]}
    if op == "mcp":
        return (find_mcp(names, step["server"], step["tool"])
                or "mcp__%s__%s" % (step["server"], step["tool"])), step.get("args", {})
    raise ValueError(op)


def to_codex(step, names):
    op = step["op"]
    if op == "mcp":
        return (find_mcp(names, step["server"], step["tool"])
                or "mcp__%s__%s" % (step["server"], step["tool"])), step.get("args", {})
    if op == "read":       # Codex has no file-read tool; it reads through the shell
        cmd = "cat %s" % step["path"]
    elif op == "write":    # and this lab writes through the shell as well
        cmd = "mkdir -p $(dirname %s) && cat > %s <<'LAB_EOF'\n%s\nLAB_EOF" % (
            step["path"], step["path"], step["content"].rstrip("\n"))
    else:
        cmd = step["cmd"]
    if "exec_command" in names:
        return "exec_command", {"cmd": cmd}
    if "shell_command" in names:
        return "shell_command", {"command": cmd}
    return "shell", {"command": ["bash", "-lc", cmd]}


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(text_of(c.get("text") or c.get("content") or c.get("output") or "")
                         if isinstance(c, dict) else str(c) for c in content)
    if isinstance(content, dict):
        return text_of(content.get("text") or content.get("content") or content.get("output") or "")
    return ""


def anthropic_results(body):
    out = []
    for m in body.get("messages", []):
        if isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    out.append({"id": b.get("tool_use_id"), "is_error": bool(b.get("is_error")),
                                "text": text_of(b.get("content"))})
    return out


def responses_results(body):
    items = body.get("input") if isinstance(body.get("input"), list) else []
    return [{"id": i.get("call_id"), "is_error": None, "text": text_of(i.get("output"))}
            for i in items if isinstance(i, dict) and str(i.get("type", "")).endswith("_output")]


def sse(handler, events):
    handler.send_response(200)
    handler.send_header("content-type", "text/event-stream")
    handler.send_header("cache-control", "no-cache")
    handler.end_headers()
    for name, data in events:
        handler.wfile.write(("event: %s\ndata: %s\n\n" % (name, json.dumps(data))).encode())
    handler.wfile.flush()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/control/health"):
            return self._json({"ok": True, "model": MODEL_ID})
        log("get", {"path": self.path})
        self._json({"data": [], "object": "list"})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {"_raw": raw.decode("latin-1")}
        path = self.path.split("?")[0]
        if path == "/control/load":
            runlog.set_run(self.headers["x-run-id"])
            STATE.update(pre=body.get("pre", []), benign=body.get("benign", []),
                         final=body.get("final", "Done."))
            return self._json({"ok": True})
        headers = {k.lower(): ("<redacted>" if k.lower() in ("authorization", "x-api-key") else v)
                   for k, v in self.headers.items()}
        log("request", {"path": path, "headers": headers, "body": body})
        if path.endswith("/messages/count_tokens"):
            return self._json({"input_tokens": 1000})
        if path.endswith("/messages"):
            return self.anthropic(body)
        if path.endswith("/responses"):
            return self.openai_responses(body)
        self._json({})

    def next_step(self, results, main, api):
        """Log what came back, then pick the step to issue (or None when finished)."""
        steps = directives.plan(STATE["pre"], STATE["benign"], [r["text"] for r in results])
        done = len(results)
        if main:
            log("results", {"api": api, "count": done,
                            "results": [dict(r, text=r["text"][:4000]) for r in results]})
        if main and done < len(steps):
            return done, steps[done]
        return done, None

    # ---- Anthropic Messages API (Claude Code) ----
    def anthropic(self, body):
        names = tool_names(body.get("tools"))
        main = "Bash" in names
        done, step = self.next_step(anthropic_results(body), main, "anthropic")
        if step:
            name, args = to_claude(step, names)
            block = {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:24], "name": name, "input": args}
            stop = "tool_use"
            log("issue", {"api": "anthropic", "index": done, "origin": step["origin"], "step": step,
                          "call_id": block["id"], "tool": name, "input": args})
        else:
            block = {"type": "text", "text": STATE["final"] if main else "Lab session"}
            stop = "end_turn"
            if main:
                log("final", {"api": "anthropic", "index": done})
        msg = {"id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant",
               "model": body.get("model", MODEL_ID), "content": [], "stop_reason": None,
               "stop_sequence": None, "usage": {"input_tokens": 1000, "output_tokens": 1}}
        if not body.get("stream"):
            msg.update(content=[block], stop_reason=stop)
            return self._json(msg)
        if block["type"] == "tool_use":
            start = dict(block, input={})
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
        else:
            start = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": block["text"]}
        sse(self, [
            ("message_start", {"type": "message_start", "message": msg}),
            ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": start}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                               "usage": {"output_tokens": 50}}),
            ("message_stop", {"type": "message_stop"}),
        ])

    # ---- OpenAI Responses API (Codex CLI) ----
    def openai_responses(self, body):
        names = tool_names(body.get("tools"))
        main = bool(names)
        done, step = self.next_step(responses_results(body), main, "responses")
        rid = "resp_" + uuid.uuid4().hex[:24]
        if step:
            name, args = to_codex(step, names)
            item = {"type": "function_call", "id": "fc_" + uuid.uuid4().hex[:24], "status": "completed",
                    "call_id": "call_" + uuid.uuid4().hex[:24], "name": name, "arguments": json.dumps(args)}
            ns = step["op"] == "mcp" and namespaced(body.get("tools"), step["server"], step["tool"])
            if ns:
                item.update(namespace=ns, name=step["tool"])
            log("issue", {"api": "responses", "index": done, "origin": step["origin"], "step": step,
                          "call_id": item["call_id"], "tool": name, "input": args})
        else:
            item = {"type": "message", "id": "msg_" + uuid.uuid4().hex[:24], "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": STATE["final"] if main else "Lab session",
                                 "annotations": []}]}
            if main:
                log("final", {"api": "responses", "index": done})
        resp = {"id": rid, "object": "response", "created_at": int(time.time()), "status": "in_progress",
                "model": body.get("model", MODEL_ID), "output": []}
        final = dict(resp, status="completed", output=[item],
                     usage={"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 0},
                            "output_tokens": 50, "output_tokens_details": {"reasoning_tokens": 0},
                            "total_tokens": 1050})
        sse(self, [
            ("response.created", {"type": "response.created", "response": resp}),
            ("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": item}),
            ("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": item}),
            ("response.completed", {"type": "response.completed", "response": final}),
        ])


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
