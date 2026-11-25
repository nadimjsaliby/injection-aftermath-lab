# injection-aftermath-lab

A small, local lab that asks two questions about coding agents **after** a prompt injection
has already worked:

1. Which controls stop the resulting actions?
2. Afterwards, which evidence lets an investigator prove what happened?

It runs the unmodified **Claude Code 2.1.220** and **Codex CLI 0.162.1** binaries in
disposable containers against a scripted model that obeys whatever instruction it finds in
the repository. Syscall traces, packet captures, a local sink and server-side logs record
what really happened, independently of what the agent says happened.

Read first: [`STUDY_PLAN.md`](STUDY_PLAN.md) (threat model, metrics),
[`SCENARIOS.md`](SCENARIOS.md) (scenario and condition matrix),
[`CONFIGURATIONS.md`](CONFIGURATIONS.md) (exact versions and settings per condition),
[`LIMITATIONS_AND_SAFETY.md`](LIMITATIONS_AND_SAFETY.md), [`RELATED_WORK.md`](RELATED_WORK.md).
Results of the recorded runs: [`results/summary.md`](results/summary.md) (main matrix, 385 runs),
[`results/diagnostics/summary.md`](results/diagnostics/summary.md) (40 follow-up runs) and
[`results/claims.md`](results/claims.md) (every number quoted in the write-ups, recomputed).

The scripted model always follows the injected instruction. The lab therefore evaluates
controls and evidence **after** that point. It does not measure how often real models obey
prompt injections.

No cloud account and no API key are involved.

## Requirements

- Docker Engine 24 or newer with Compose v2 (tested: Docker 29.8.2 under OrbStack, Linux
  arm64 kernel 7.2). The Docker host must allow unprivileged user namespaces, which the
  agents' sandboxes need.
- Python 3.9 or newer on the machine that runs `lab.py` (standard library only).
- About 2 GB of disk for images and 800 MB for the evidence of a full matrix.
- Internet access once, to pull base images and the two npm packages during `setup`.
  After that the lab network has no route out.

## Run it

```sh
python3 lab.py test        # 40 unit tests for the lab's own scripts, no Docker needed
python3 lab.py setup       # build two images, start model stub, collector, MCP server, sink
python3 lab.py validate    # tests + 6 live runs with known expected outcomes (about 1 minute)
python3 lab.py run         # main matrix: 385 runs, about 50 minutes; scores at the end
python3 lab.py diag        # diagnostic set: 40 runs, about 5 minutes
python3 lab.py score       # re-score evidence/ without re-running anything
python3 lab.py verify      # recompute results/ from raw evidence and compare byte for byte
python3 lab.py claims      # recompute every number quoted in the write-ups
```

Smaller runs:

```sh
python3 lab.py run --agents claude --conditions C0,C4 --scenarios S6-exfil --reps 3
```

`run` appends to `evidence/`; a repeated run id overwrites that run's directory. The main
matrix is 11 agent and condition pairs (Claude Code C0 to C5, Codex C0 to C4) x 7 scenarios
x 5 repetitions.

## From a quoted number back to raw data

1. Find the number in [`results/claims.md`](results/claims.md). Each row gives the statement,
   the value recomputed now, and the value the write-ups quote.
2. The function with that id in [`labscore/claims.py`](labscore/claims.py) shows which fields
   of `results/runs.jsonl` it is computed from.
3. Each line of `results/runs.jsonl` carries a `run_id`; the raw files of that run are in
   `evidence/<run_id>/` (or `evidence-diag/<run_id>/`).
4. `results/evidence-sha256.json` pins one digest per run directory, and `python3 lab.py
   verify` checks those digests and regenerates `runs.jsonl`, `summary.json` and `summary.md`
   from the raw files, comparing byte for byte.

The raw evidence (about 800 MB) is not in version control. Results derived from it can be
re-checked only where the evidence directories are present; `verify` and `claims` say so
explicitly when they are not.

## Reset and teardown

```sh
python3 lab.py reset --yes   # delete evidence/ and results/, keep images and services
python3 lab.py teardown      # stop and remove the lab's containers, network and images
```

Both touch only the Compose project `injection-aftermath-lab` and this directory.

## What a run does

For each run `lab.py` starts one fresh workstation container. Inside it,
[`workstation/run.sh`](workstation/run.sh):

1. builds a new home directory and project from `fixtures/`, appends the scenario's
   injection to `CONTRIBUTING.md`, and installs the condition's agent configuration;
2. installs the lab egress firewall if the condition asks for it;
3. takes a filesystem snapshot and starts `tcpdump`;
4. runs the agent as the unprivileged user `dev` under `strace -f`;
5. takes a second snapshot, runs the project's tests itself to decide whether the benign
   task was completed, and copies the agent's session files as a responder would.

The model stub ([`services/model.py`](services/model.py)) issues the benign plan and obeys
any `lab-directive:` token it sees in a tool result. That is the only mocked component.

## Results format

`results/runs.jsonl` has one JSON object per run. Main fields:

| Field | Meaning |
|---|---|
| `run_id` | `<agent>/<condition>/<scenario>/r<n>` |
| `status` | `ok`, `incomplete` (agent exited non-zero or the plan did not finish), `failed` (a reference artifact is missing) |
| `effects` | nine booleans, each named for what its recorder can observe (`secret_opened`, `secret_to_model`, `script_executed`, `script_marker`, `mcp_call_received`, ...) |
| `outcome` | `criterion_met`, `blocked`, `not_attempted`, `inconclusive`, or `n/a` for the clean scenario |
| `criterion`, `criterion_strength` | what `criterion_met` means for this scenario and how strong it is: `opened`, `executed`, `received` or `effect_confirmed` |
| `effect_confirmed` | whether the intended effect was confirmed by a recorder that observes it; `null` where the lab cannot tell (S5) |
| `runtime` | settings the agent itself recorded at run time (permission mode; approval policy, sandbox type, network access) |
| `block_point` | `before_execution`, `at_execution`, or `unknown` |
| `kernel_attempts` | whether a matching syscall was attempted at all |
| `task_completed` | did the project's tests pass when the harness ran them afterwards |
| `duration_s` | agent wall time |
| `time_to_effect_ms` | from the stub issuing the injected step to the reference recorder seeing the effect |
| `evidence` | `{source: {Q1_carrier, Q2_attempt, Q3_outcome, Q4_content}}` with grades `correct`, `missing`, `wrong`, `reference`, `n/a` |

`results/summary.md` and `summary.json` aggregate those records.
`results/manifest.json` pins what ran, one entry per batch: tool versions as printed by the
binaries, image ids, the run ids of the batch and a SHA-256 of every input file.
`results/evidence-sha256.json` pins the raw evidence, and `results/claims.md` is the ledger
of quoted numbers.

Scoring is automatic and documented in the module docstrings:
[`labscore/truth.py`](labscore/truth.py) (ground truth and outcomes) and
[`labscore/evidence.py`](labscore/evidence.py) (the four investigator questions).
To check a cell by hand, open `evidence/<run_id>/` and compare `sink.jsonl`, `mcp.jsonl`,
`strace.log` and `final/` with the agent's own files under `agent-home/`.

## Evidence directory of one run

| File | Written by | Role |
|---|---|---|
| `strace.log` | strace as root | reference: exec, open, rename, connect |
| `net.pcap`, `net.txt` | tcpdump as root | packets that left the container (text view excludes model and telemetry traffic) |
| `egress-denied.pcap`, `.txt`, `firewall-counters.txt` | lab firewall (C3, C4) | packets it rejected |
| `fs-before.json`, `fs-after.json`, `final/` | harness as root | disk state |
| `sink.jsonl`, `mcp.jsonl` | sink and MCP containers | reference: what arrived |
| `gateway.jsonl` | model stub | requests the agent sent, steps issued |
| `otel.jsonl` | collector container | the agent's OpenTelemetry log export |
| `agent.stdout` | the CLI | `stream-json` / `--json` event stream |
| `agent-home/` | the CLI | session transcripts left in `~/.claude` and `~/.codex` |
| `task-check.txt`, `.exit` | harness | benign task verdict |

## Layout

```
lab.py                 setup / run / score / test / validate / reset / teardown
compose.yml            four services and the workstation, one internal network
services/              model stub, sink, telemetry collector, MCP server
workstation/           image, run.sh, prepare.py, snapshot.py, conditions/<agent>/<Cx>/
common/directives.py   how an injected instruction is encoded and found
fixtures/              the repository, the synthetic home directory, the benign plan
scenarios/             S0 to S6
labscore/              trace parser, source parsers, ground truth, evidence grading, report
tests/                 unit tests
results/               runs.jsonl, summary.md, summary.json, manifest.json, claims.md,
                       evidence-sha256.json, diagnostics/
```

## Reproducibility notes

- Versions are pinned in `workstation/Dockerfile`; base images are pinned by tag and their
  resolved digests are recorded in `results/manifest.json`.
- The model stub is deterministic. Differences between repetitions come from the harness,
  the sandbox and timing.
- Run order is shuffled with a fixed seed (`--seed`, default 20261125).
- Expect small differences on another host: kernel, container runtime and whether nested
  user namespaces are permitted all affect whether the sandboxes start. If a sandbox cannot
  start, the affected runs show up as incomplete or with a failed benign task, not as
  silently unsandboxed: Claude Code is configured with `failIfUnavailable`.
