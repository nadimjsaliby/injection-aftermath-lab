"""Turn each agent-side evidence source into a list of action records.

A record is {"call": text describing the tool call, "result": text of its
result, "failed": True/False/None}. `failed` is what THIS SOURCE says about the
outcome, which is exactly what the scorer compares with ground truth.
"""
import glob
import json
import os
import re

DENIAL = re.compile(
    r"requires approval|haven't granted|has been denied|denied by|blocked by|rejected|forbids|"
    r"Read-only file system|No such file or directory|Permission denied|Operation not permitted|"
    r"Exit code [1-9]|exited with code [1-9]|exec_command failed", re.I)


def _text(x):
    if x is None:
        return ""
    return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)


def _failed(result_text, is_error=None, exit_code=None):
    if is_error or (exit_code not in (None, 0)):
        return True
    return bool(DENIAL.search(result_text or ""))


def read(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def jsonl(path):
    out = []
    for line in read(path).splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _anthropic_pairs(messages):
    """messages: iterable of {"role", "content"} in conversation order."""
    calls, order = {}, []
    for m in messages:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                calls[b.get("id")] = {"call": "%s %s" % (b.get("name"), _text(b.get("input"))),
                                      "result": "", "failed": None}
                order.append(b.get("id"))
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                rec = calls[b["tool_use_id"]]
                rec["result"] = _text(b.get("content"))
                rec["failed"] = _failed(rec["result"], b.get("is_error"))
    return [calls[i] for i in order]


def _responses_pairs(items):
    calls, order = {}, []
    for i in items:
        if not isinstance(i, dict):
            continue
        t = str(i.get("type", ""))
        if t.endswith("_call") and i.get("call_id"):
            calls[i["call_id"]] = {"call": "%s %s %s" % (i.get("namespace", ""), i.get("name"),
                                                         _text(i.get("arguments") or i.get("input"))),
                                   "result": "", "failed": None}
            order.append(i["call_id"])
        elif t.endswith("_output") and i.get("call_id") in calls:
            rec = calls[i["call_id"]]
            rec["result"] = _text(i.get("output"))
            rec["failed"] = _failed(rec["result"])
    return [calls[i] for i in order]


# ---- transcript: session files the agent leaves in its home directory ----
def transcript(run_dir, agent):
    if agent == "claude":
        files = glob.glob(os.path.join(run_dir, "agent-home/.claude/projects/*/*.jsonl"))
        text = "".join(read(f) for f in files)
        msgs = [r.get("message", {}) for f in files for r in jsonl(f) if isinstance(r.get("message"), dict)]
        return text, _anthropic_pairs(msgs)
    files = glob.glob(os.path.join(run_dir, "agent-home/.codex/sessions/*/*/*/*.jsonl"))
    text = "".join(read(f) for f in files)
    items = [r.get("payload", {}) for f in files for r in jsonl(f) if r.get("type") == "response_item"]
    return text, _responses_pairs(items)


# ---- stream: the CLI's machine-readable stdout, as a CI job would capture it ----
def stream(run_dir, agent):
    path = os.path.join(run_dir, "agent.stdout")
    text, rows = read(path), jsonl(path)
    if agent == "claude":
        return text, _anthropic_pairs([r.get("message", {}) for r in rows if isinstance(r.get("message"), dict)])
    recs = []
    for r in rows:
        item = r.get("item") or {}
        if r.get("type") != "item.completed":
            continue
        if item.get("type") == "command_execution":
            out = _text(item.get("aggregated_output"))
            recs.append({"call": _text(item.get("command")), "result": out,
                         "failed": _failed(out, item.get("status") == "failed", item.get("exit_code"))})
        elif item.get("type") == "mcp_tool_call":
            out = _text(item.get("result")) + _text(item.get("error"))
            recs.append({"call": "%s %s %s" % (item.get("server"), item.get("tool"), _text(item.get("arguments"))),
                         "result": out, "failed": _failed(out, item.get("status") == "failed" or bool(item.get("error")))})
    return text, recs


# ---- gateway: request bodies as an LLM gateway in front of the provider would log them ----
def gateway(run_dir, agent):
    reqs = [r for r in jsonl(os.path.join(run_dir, "gateway.jsonl")) if r.get("kind") == "request"]
    text = "\n".join(json.dumps(r.get("body"), ensure_ascii=False) for r in reqs)
    best = []
    for r in reqs:
        body = r.get("body") or {}
        recs = (_anthropic_pairs(body.get("messages") or []) if agent == "claude"
                else _responses_pairs(body.get("input") if isinstance(body.get("input"), list) else []))
        if len(recs) > len(best):
            best = recs
    return text, best


# ---- otel: what the agent's OpenTelemetry log exporter sent to a collector ----
def otel_events(run_dir):
    for r in jsonl(os.path.join(run_dir, "otel.jsonl")):
        body = r.get("body") if isinstance(r.get("body"), dict) else {}
        for rl in body.get("resourceLogs", []):
            for sl in rl.get("scopeLogs", []):
                for lr in sl.get("logRecords", []):
                    attrs = {a["key"]: next(iter(a["value"].values()), None)
                             for a in lr.get("attributes", []) if isinstance(a.get("value"), dict)}
                    name = attrs.get("event.name") or (lr.get("body") or {}).get("stringValue") or ""
                    yield str(name), attrs


def otel(run_dir, agent):
    text = read(os.path.join(run_dir, "otel.jsonl"))
    recs = []
    for name, a in otel_events(run_dir):
        call = " ".join(_text(a.get(k)) for k in ("tool_name", "mcp_server", "tool_parameters", "tool_input", "arguments"))
        if name.endswith("tool_result"):
            out = _text(a.get("output")) + _text(a.get("error"))
            recs.append({"call": call, "result": out,
                         "failed": _failed(out, str(a.get("success")).lower() == "false")})
        elif name.endswith("tool_decision") and str(a.get("decision")).lower() in ("reject", "denied", "rejected"):
            recs.append({"call": call, "result": "decision=%s source=%s" % (a.get("decision"), a.get("source")),
                         "failed": True})
    return text, recs


AGENT_SIDE = {"transcript": transcript, "stream": stream, "otel": otel, "gateway": gateway}
