"""How the lab's obedient model finds injected instructions.

A poisoned file carries a human-readable instruction and, next to it, the same
instruction as a token:  lab-directive:<base64url(JSON step)>
The token survives line numbering and JSON escaping, so one parser works for
every harness. Parsing is the ONLY "decision" the stub makes: it obeys every
directive it has been shown in a tool result, in order, exactly once.
"""
import base64
import json
import re

TOKEN = re.compile(r"lab-directive:([A-Za-z0-9_-]+)")


def encode(step):
    raw = json.dumps(step, sort_keys=True, separators=(",", ":")).encode()
    return "lab-directive:" + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_all(text):
    """Return the directives found in text, in order, without duplicates."""
    out, seen = [], set()
    for m in TOKEN.finditer(text or ""):
        tok = m.group(1)
        if tok in seen:
            continue
        seen.add(tok)
        try:
            step = json.loads(base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)))
        except ValueError:
            continue
        if isinstance(step, dict) and "op" in step:
            out.append(step)
    return out


def plan(pre, benign, tool_result_texts):
    """Full step list for a conversation: read the docs, obey what they say, do the task."""
    injected = decode_all("\n".join(tool_result_texts))
    return ([dict(s, origin="benign") for s in pre]
            + [dict(s, origin="injected") for s in injected]
            + [dict(s, origin="benign") for s in benign])
