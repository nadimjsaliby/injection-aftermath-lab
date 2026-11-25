"""Parse `strace -f -ttt -yy` output into complete syscall records.

A call interrupted by another thread is split across an `<unfinished ...>` line
and a `<... name resumed>` line; the two halves are joined per pid.
"""
import re

LINE = re.compile(r"^(\d+)\s+(\d+\.\d+)\s+(.*)$")
RESUMED = re.compile(r"^<\.\.\. (\w+) resumed>(.*)$")
RET = re.compile(r"\)\s+=\s+(-?\d+|\?)(?:<[^>]*>)?(?:\s+(E[A-Z]+))?")


def parse(text):
    """Yield dicts: pid, ts, name, args (raw text), ret (int or None), errno (str or None)."""
    pending = {}
    for raw in text.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        pid, ts, rest = int(m.group(1)), float(m.group(2)), m.group(3)
        if rest.endswith("<unfinished ...>"):
            pending[pid] = (ts, rest[: -len("<unfinished ...>")])
            continue
        r = RESUMED.match(rest)
        if r:
            if pid not in pending:
                continue
            ts, head = pending.pop(pid)
            rest = head + r.group(2)
        name = rest.split("(", 1)[0]
        if not re.fullmatch(r"\w+", name):
            continue          # signals, exits
        ret = RET.search(rest)
        value = None
        if ret and ret.group(1) != "?":
            value = int(ret.group(1))
        yield {"pid": pid, "ts": ts, "name": name, "args": rest, "ret": value,
               "errno": ret.group(2) if ret else None}


OPENS = ("open", "openat", "openat2", "creat")
WRITE_FLAGS = re.compile(r"O_WRONLY|O_RDWR|O_APPEND|O_TRUNC|O_CREAT")


def opens(calls, path, write=False):
    """Open attempts on an exact path. Returns (attempts, first successful call or None)."""
    needle = '"%s"' % path
    # O_PATH yields a handle for metadata only: it cannot read data, so it is not an access
    hits = [c for c in calls if c["name"] in OPENS and needle in c["args"] and "O_PATH" not in c["args"]
            and (not write or c["name"] == "creat" or WRITE_FLAGS.search(c["args"]))]
    ok = next((c for c in hits if c["ret"] is not None and c["ret"] >= 0), None)
    return hits, ok


def writes(calls, path):
    """Write attempts on a path: opens with a write flag, or a rename onto it (atomic save)."""
    hits, ok = opens(calls, path, write=True)
    needle = '"%s") = ' % path
    ren = [c for c in calls if c["name"].startswith("rename") and needle in c["args"].replace(", RENAME_NOREPLACE", "")]
    hits = sorted(hits + ren, key=lambda c: c["ts"])
    ok = next((c for c in hits if c["ret"] is not None and c["ret"] >= 0), None)
    return hits, ok


def execs(calls, pattern):
    """execve attempts whose argument text matches pattern. Returns (attempts, first success)."""
    rx = re.compile(pattern)
    hits = [c for c in calls if c["name"] in ("execve", "execveat") and rx.search(c["args"])]
    ok = next((c for c in hits if c["ret"] == 0), None)
    return hits, ok


def connects(calls, ip, port):
    needle = "sin_port=htons(%d), sin_addr=inet_addr(\"%s\")" % (port, ip)
    hits = [c for c in calls if c["name"] == "connect" and needle in c["args"]]
    # a non-blocking connect returns EINPROGRESS; only an immediate refusal counts as failed
    ok = next((c for c in hits if c["ret"] == 0 or c["errno"] == "EINPROGRESS"), None)
    return hits, ok
