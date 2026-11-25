"""Per-run JSONL logging shared by the lab services.

Each service is told which run is active through POST /control/load and then
appends its records to <evidence>/<run_id>/<service>.jsonl.
"""
import json
import os
import threading
import time

ROOT = os.environ.get("EVIDENCE_DIR", "/evidence")
_state = {"run_id": "idle"}
_lock = threading.Lock()


def set_run(run_id):
    _state["run_id"] = run_id


def log(service, record):
    record = dict(record, ts=round(time.time(), 6))
    d = os.path.join(ROOT, _state["run_id"])
    os.makedirs(d, exist_ok=True)
    with _lock, open(os.path.join(d, service + ".jsonl"), "a") as fh:
        fh.write(json.dumps(record) + "\n")
