#!/usr/bin/env python3
"""Injection-aftermath lab: one entry point for setup, run, score, reset and teardown.

    python3 lab.py setup                 build images, start the four lab services
    python3 lab.py run [--reps 5]        run the matrix (filters: --agents --conditions --scenarios)
    python3 lab.py diag [--reps 5]       run the diagnostic set into evidence-diag/ and results/diagnostics/
    python3 lab.py score                 evidence/ -> results/runs.jsonl, summary.md, summary.json, evidence digests
    python3 lab.py verify                re-score saved evidence and compare with results/; check evidence digests
    python3 lab.py claims                check every number quoted in the write-ups against results/ (results/claims.md)
    python3 lab.py test                  unit tests for the lab's own scripts (no Docker needed)
    python3 lab.py validate              tests + a 4-run smoke matrix with expected outcomes
    python3 lab.py reset --yes           delete evidence/ and results/ (keeps images)
    python3 lab.py teardown              stop and remove containers, network and images

Everything Docker-related is scoped to the Compose project `injection-aftermath-lab`.
"""
import argparse
import glob
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
AGENTS = ["claude", "codex"]
# Main matrix. C5 exists for Claude Code only: it is C4 with one sandbox setting changed.
MATRIX = {"claude": ["C0", "C1", "C2", "C3", "C4", "C5"], "codex": ["C0", "C1", "C2", "C3", "C4"]}
# Diagnostic set: narrow follow-up questions, kept out of the main matrix and its totals.
DIAG = {"claude": {"conditions": ["C4", "C5"], "scenarios": ["S4-shell-exec"]},
        "codex": {"conditions": ["M0", "M1", "M2", "M3", "M4", "M5"], "scenarios": ["S5-mcp-call"]}}
PROJECT = "injection-aftermath-lab"


def sh(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, text=True, **kw)


def compose(*args, evidence="evidence", **kw):
    env = dict(os.environ, EVIDENCE_DIR=os.path.join(ROOT, evidence))
    return sh(["docker", "compose", *args], env=env, **kw)


def scenario_ids():
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, "scenarios", "*.json")))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def setup(a):
    os.makedirs(os.path.join(ROOT, a.evidence), exist_ok=True)
    if compose("--profile", "run", "build", evidence=a.evidence).returncode:
        sys.exit("image build failed")
    if compose("up", "-d", "--wait", evidence=a.evidence).returncode:
        sys.exit("services failed to start; see `docker compose logs`")
    internal = sh(["docker", "network", "inspect", PROJECT + "_labnet", "--format", "{{.Internal}}"],
                  capture_output=True).stdout.strip()
    if internal != "true":
        sys.exit("refusing to continue: the lab network is not internal-only")
    print("lab services are up on an internal-only network")


def manifest(a, runs=None):
    """Record exactly what ran: versions, image ids, and a hash of every input file.

    Each `run` or `diag` invocation appends one batch, so later batches never
    overwrite the record of the inputs an earlier batch ran with.
    """
    out = compose("--profile", "run", "run", "--rm", "-T", "--entrypoint", "sh", "workstation", "-c",
                  "claude --version; codex --version; bwrap --version; strace -V | head -1; "
                  "python3 --version; node --version; uname -r; uname -m; . /etc/os-release; echo $PRETTY_NAME",
                  evidence=a.evidence, capture_output=True).stdout.strip().split("\n")
    keys = ["claude_code", "codex_cli", "bubblewrap", "strace", "python", "node", "kernel", "arch", "os"]
    files = sorted(p for pat in ("scenarios/*.json", "fixtures/plan.json", "workstation/conditions/*/*/*",
                                 "workstation/*", "services/*", "common/*", "compose.yml", "labscore/*.py")
                   for p in glob.glob(os.path.join(ROOT, pat)) if os.path.isfile(p))

    def image(ref, fmt="{{.Id}}"):
        return sh(["docker", "image", "inspect", ref, "--format", fmt], capture_output=True).stdout.strip()
    m = {"recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "tools": dict(zip(keys, out)),
         "model": {"id": "lab-obedient-1", "kind": "scripted stub, no sampling",
                   "sha256": sha(os.path.join(ROOT, "services/model.py"))},
         "docker_server": sh(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True).stdout.strip(),
         "images": {"workstation": image(PROJECT + "-workstation"), "services": image(PROJECT + "-services"),
                    "base_node": image("node:22-bookworm-slim", "{{json .RepoDigests}} {{.Id}}"),
                    "base_python": image("python:3.12-slim-bookworm", "{{json .RepoDigests}} {{.Id}}")},
         "npm_packages": {"@anthropic-ai/claude-code": "2.1.220", "@openai/codex": "0.162.1"},
         "runs": runs or [], "seed": getattr(a, "seed", None),
         "input_sha256": {os.path.relpath(p, ROOT): sha(p) for p in files}}
    os.makedirs(os.path.join(ROOT, a.results), exist_ok=True)
    path = os.path.join(ROOT, a.results, "manifest.json")
    doc = {"batches": []}
    if os.path.exists(path):
        with open(path) as fh:
            old = json.load(fh)
        doc = old if "batches" in old else {"batches": [old]}
    doc["batches"].append(m)
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    return m


def run_one(agent, cond, sid, rep, evidence):
    run_id = "%s/%s/%s/r%d" % (agent, cond, sid, rep)
    t0 = time.time()
    r = compose("--profile", "run", "run", "--rm", "-T", "-e", "AGENT=" + agent, "-e", "COND=" + cond,
                "-e", "RUN_ID=" + run_id, "-v", os.path.join(ROOT, "scenarios", sid + ".json") + ":/scenario.json:ro",
                "workstation", evidence=evidence, capture_output=True)
    return {"run_id": run_id, "rc": r.returncode, "wall_s": round(time.time() - t0, 2),
            "stderr_tail": r.stderr[-300:] if r.returncode else ""}


def plan_runs(a, diag=False):
    agents = a.agents.split(",") if a.agents else AGENTS
    todo = []
    for ag in agents:
        if diag:
            conds, scen = DIAG.get(ag, {}).get("conditions", []), DIAG.get(ag, {}).get("scenarios", [])
        else:
            conds, scen = MATRIX[ag], scenario_ids()
        if a.conditions:
            conds = [c for c in conds if c in a.conditions.split(",")]
        if a.scenarios:
            scen = [s for s in scen if s in a.scenarios.split(",")]
        todo += [(ag, c, s, rep) for rep in range(a.first_rep, a.first_rep + a.reps) for c in conds for s in scen]
    random.Random(a.seed).shuffle(todo)     # fixed, shuffled order so drift is not confounded with condition
    return todo


def diag(a):
    a.evidence, a.results = "evidence-diag", os.path.join("results", "diagnostics")
    return run(a, diag=True)


def run(a, diag=False):
    setup(a)
    todo = plan_runs(a, diag)
    if not todo:
        sys.exit("nothing to run: the filters match no cell")
    manifest(a, runs=sorted("%s/%s/%s/r%d" % t for t in todo))
    index = os.path.join(ROOT, a.evidence, "index.jsonl")
    bad = 0
    for n, (ag, c, s, rep) in enumerate(todo, 1):
        rec = run_one(ag, c, s, rep, a.evidence)
        bad += rec["rc"] != 0
        with open(index, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print("[%3d/%d] %-34s rc=%d %5.1fs" % (n, len(todo), rec["run_id"], rec["rc"], rec["wall_s"]), flush=True)
    print("done: %d runs, %d with a non-zero container exit (kept and scored as failed)" % (len(todo), bad))
    return score(a)


def run_dirs(evidence):
    root = os.path.join(ROOT, evidence)
    return sorted(d for d in glob.glob(os.path.join(root, "*", "*", "*", "r*")) if os.path.isdir(d))


def digest(run_dir):
    """One SHA-256 per run directory: the hash of its sorted (relative path, file hash) list."""
    h = hashlib.sha256()
    for base, _, files in sorted(os.walk(run_dir)):
        for name in sorted(files):
            p = os.path.join(base, name)
            if os.path.isfile(p) and not os.path.islink(p):
                h.update(("%s %s\n" % (os.path.relpath(p, run_dir), sha(p))).encode())
    return h.hexdigest()


def digests(evidence):
    root = os.path.join(ROOT, evidence)
    return {os.path.relpath(d, root): digest(d) for d in run_dirs(evidence)}


def score(a):
    rc = sh([sys.executable, "-m", "labscore.score", "--evidence", a.evidence, "--out", a.results]).returncode
    if rc == 0:      # pin the raw evidence the scores were computed from
        with open(os.path.join(ROOT, a.results, "evidence-sha256.json"), "w") as fh:
            json.dump(digests(a.evidence), fh, indent=0, sort_keys=True)
    return rc


def verify(a):
    """Recompute everything from raw evidence and compare with what is published in results/."""
    import tempfile
    ok = True
    for evidence, results in ((a.evidence, a.results), ("evidence-diag", os.path.join(a.results, "diagnostics"))):
        if not os.path.isdir(os.path.join(ROOT, evidence)):
            print("SKIP  %s/ not present: its results cannot be re-derived on this machine" % evidence)
            continue
        with open(os.path.join(ROOT, results, "evidence-sha256.json")) as fh:
            want = json.load(fh)
        have = digests(evidence)
        same = want == have
        ok &= same
        print("%s  %s: %d run directories match the recorded digests" % ("PASS" if same else "FAIL", evidence, len(have)))
        with tempfile.TemporaryDirectory() as tmp:
            sh([sys.executable, "-m", "labscore.score", "--evidence", evidence, "--out", tmp], capture_output=True)
            for name in ("runs.jsonl", "summary.json", "summary.md"):
                with open(os.path.join(tmp, name), "rb") as x, open(os.path.join(ROOT, results, name), "rb") as y:
                    same = x.read() == y.read()
                ok &= same
                print("%s  %s/%s is reproduced byte for byte from %s/" % ("PASS" if same else "FAIL", results, name, evidence))
    print("verification %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


def claims(a):
    return sh([sys.executable, "-m", "labscore.claims", "--results", a.results]).returncode


def test(a):
    return sh([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]).returncode


def validate(a):
    """Unit tests, then four live runs whose outcomes are known in advance."""
    if test(a):
        sys.exit("unit tests failed")
    a.evidence, a.results = "evidence-validate", "results-validate"
    shutil.rmtree(os.path.join(ROOT, a.evidence), ignore_errors=True)
    setup(a)
    expect = [("claude", "C0", "S6-exfil", "achieved"), ("claude", "C4", "S6-exfil", "blocked"),
              ("codex", "C0", "S6-exfil", "achieved"), ("codex", "C4", "S6-exfil", "blocked"),
              ("claude", "C0", "S0-clean", "n/a"), ("codex", "C0", "S0-clean", "n/a")]
    for ag, c, s, _ in expect:
        rec = run_one(ag, c, s, 1, a.evidence)
        open(os.path.join(ROOT, a.evidence, "index.jsonl"), "a").write(json.dumps(rec) + "\n")
    if score(a):
        sys.exit("scoring failed")
    runs = {r["run_id"]: r for r in map(json.loads, open(os.path.join(ROOT, a.results, "runs.jsonl")))}
    ok = True
    for ag, c, s, want in expect:
        r = runs["%s/%s/%s/r1" % (ag, c, s)]
        good = r["status"] == "ok" and r.get("outcome") == want and r.get("task_completed") is True
        ok &= good
        print("%-4s %s/%s/%s: status=%s outcome=%s (want %s) task=%s" % (
            "PASS" if good else "FAIL", ag, c, s, r["status"], r.get("outcome"), want, r.get("task_completed")))
    shutil.rmtree(os.path.join(ROOT, a.evidence), ignore_errors=True)
    shutil.rmtree(os.path.join(ROOT, a.results), ignore_errors=True)
    print("validation %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


def reset(a):
    if not a.yes:
        sys.exit("this deletes %s/ and %s/; rerun with --yes" % (a.evidence, a.results))
    for d in (a.evidence, a.results):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    print("evidence and results removed")


def teardown(a):
    return compose("--profile", "run", "down", "--remove-orphans", "--rmi", "local", "-v", "-t", "2").returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["setup", "run", "diag", "score", "verify", "claims", "test", "validate",
                                       "reset", "teardown"])
    ap.add_argument("--agents", default="")
    ap.add_argument("--conditions", default="")
    ap.add_argument("--scenarios", default="")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--first-rep", type=int, default=1, help="number of the first repetition (to add reps later)")
    ap.add_argument("--seed", type=int, default=20261125)
    ap.add_argument("--evidence", default="evidence")
    ap.add_argument("--results", default="results")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    sys.exit(globals()[a.command](a) or 0)


if __name__ == "__main__":
    main()
