#!/usr/bin/env python3
"""Filesystem snapshot (path, size, times, sha256) taken as root, outside the agent.

Usage: snapshot.py <out.json> <root>...   Agent state and caches are skipped.
"""
import hashlib
import json
import os
import sys

SKIP = ("/home/dev/.claude", "/home/dev/.codex", "/home/dev/.npm", "/home/dev/.cache",
        "/home/dev/project/.git/")


def snapshot(roots):
    out = {}
    for root in roots:
        for d, _, files in os.walk(root):
            for name in files:
                p = os.path.join(d, name)
                if p.startswith(SKIP):
                    continue
                try:
                    st = os.lstat(p)
                    digest = None
                    if os.path.isfile(p) and not os.path.islink(p) and st.st_size <= 1 << 20:
                        with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOATIME), "rb") as fh:
                            digest = hashlib.sha256(fh.read()).hexdigest()
                    out[p] = {"size": st.st_size, "mtime": st.st_mtime, "atime": st.st_atime,
                              "ctime": st.st_ctime, "sha256": digest}
                except OSError:
                    continue
    return out


if __name__ == "__main__":
    with open(sys.argv[1], "w") as fh:
        json.dump(snapshot(sys.argv[2:]), fh, indent=1, sort_keys=True)
