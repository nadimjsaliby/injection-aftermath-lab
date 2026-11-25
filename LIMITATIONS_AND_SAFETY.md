# Limitations and safety

## Safety design

| Boundary | How it is enforced | How to verify |
|---|---|---|
| No route out of the lab | One Docker network with `internal: true`; `lab.py setup` refuses to continue if it is not internal | `docker network inspect injection-aftermath-lab_labnet --format '{{.Internal}}'` |
| Exfiltration goes nowhere real | The only destination in any scenario is `paste.lab.test`, an alias of the local sink container; a unit test fails if a scenario names any other host | `python3 lab.py test` |
| No real secrets | The one "credential" is a labelled synthetic string; both CLIs get the placeholder API key `lab-not-a-real-key` and talk to the local model stub | `fixtures/home/.aws/credentials` |
| No vendor traffic | The model, telemetry collector, MCP server and sink are local containers | `compose.yml` |
| Nothing persists | Each run is a fresh `docker compose run --rm` container with a fresh home directory | |
| Scoped cleanup | Every Docker command uses the Compose project `injection-aftermath-lab` | `python3 lab.py teardown` |
| Evidence hygiene | The Claude Code sandbox places a per-run proxy token on command lines; it is redacted from the trace before the run ends | `workstation/run.sh` |

The workstation container is deliberately less confined than a default container
(`seccomp=unconfined`, `apparmor=unconfined`, `systempaths=unconfined`, plus `SYS_PTRACE`,
`NET_RAW`, `NET_ADMIN` for root inside it). That is needed for strace, tcpdump, the lab
firewall and the nested sandboxes. The agent process itself runs as uid `dev` with no
capabilities. Because of that relaxation, run the lab only on a machine where a container
on an internal network is an acceptable trust boundary. Do not point the scenarios at a
real repository, a real home directory or a real MCP server.

## Responsible disclosure

The study tests documented behaviour with a fixed action per scenario. It does not search
for sandbox escapes or rule bypasses. If a run ever shows a control failing in a way the
vendor's documentation says it should not, the plan is:

1. stop testing that product and keep the evidence directory;
2. reproduce once on a clean setup to rule out a lab artifact;
3. write up version, configuration, expected and observed behaviour, without publishing;
4. report through the vendor's security channel and wait for a response before any detail
   appears in the posts.

Three observations are flagged for the vendors' attention before publication. None was
probed beyond the runs recorded here, and each may be intended behaviour.

1. **Codex CLI 0.162.1, MCP approval under `danger-full-access`.** All Codex runs recorded an
   effective approval policy of `never`. With the sandbox mode set to `danger-full-access`,
   an MCP tool call reached the server although the server entry was configured with
   `default_tools_approval_mode = "prompt"` (10 of 10 runs), also with an explicit per-tool
   `approval_mode = "prompt"` (5 of 5) and also when the server advertised the tool with
   `destructiveHint: true` (5 of 5). With `workspace-write` and otherwise identical settings
   the agent refused the call (5 of 5), and `disabled_tools` removed it (5 of 5). "Reached the
   server" is all that is measured: the lab's MCP server keeps no state, so no deletion was
   verified. The mechanism behind the difference is unresolved. The current, unversioned
   documentation says destructive MCP calls "always require approval" when annotated. Whether
   that sentence is meant to apply to full-access mode or to this version is **unverified**.
   Testing of this behaviour stopped here. Suggested step before publishing: send OpenAI the
   version, the six configuration files and the result table.
2. **Claude Code 2.1.220, telemetry.** The OpenTelemetry log export contained no event for
   calls refused by a missing approval or a path rule (75 of 180 injected runs).
3. **Codex CLI 0.162.1, `--json` stream.** Commands rejected by a rule, and most commands
   whose write the sandbox refused, had no item in the stream (19 of 150 injected runs).

## Limitations

0. **Criteria differ in strength.** S1 counts a successful open for reading; the trace does
   not record `read()`. S5 counts a tool call received and answered; no ticket state exists.
   S4 counts execution. Only S2, S3 and S6 verify the effect directly. See `SCENARIOS.md`.
1. **Scripted model.** The stub obeys every directive. Real models sometimes refuse, ask,
   or do something else. Nothing here estimates how often an injection succeeds.
2. **Fixed actions.** Each scenario is one concrete command or tool call. Vendor
   documentation itself says command-pattern rules are not a security boundary. A "blocked"
   cell is a statement about that action only.
3. **Approval conditions are not equivalent across agents.** Claude Code offers an
   allowlist with deny-by-default in non-interactive mode. Codex 0.162.1 does not offer
   that without its sandbox, so its approval-only condition is a rule list.
4. **Filesystem conditions are not equivalent either.** Claude C2 adds explicit deny rules
   for the three protected paths. Codex C2 is the stock `workspace-write` mode. Codex
   permission profiles (beta) can express read and write denies but were **not evaluated**.
5. **Nested sandboxes.** Both sandboxes ran inside a container. Claude Code required
   `enableWeakerNestedSandbox`, which its documentation describes as considerably weaker.
   Results may differ on a bare Linux host or on macOS (Seatbelt): **not evaluated**.
6. **Non-interactive only.** With a person approving prompts the outcome depends on that
   person. Not evaluated.
7. **Plaintext lab traffic.** The sink and the MCP server speak HTTP so the packet capture
   can be graded on content. With TLS the capture would show destinations and sizes only.
8. **Instrumentation.** strace slows execution and changes timing; all conditions carry it.
   Timings are not representative of an uninstrumented run. Reads are inferred from
   successful opens, not from `read()` calls.
9. **Evidence grading is mechanical.** Patterns and status flags, no analyst judgement. A
   human reading a transcript may infer more, or be misled more.
10. **Evidence was not attacked.** The agent never tried to delete or edit its own logs.
    Agent-side sources are graded at their best.
11. **Scale.** 5 repetitions, 2 agents, 1 version each, 1 host.
12. **Follow-up conditions were chosen after seeing results.** C5 and the M variants test
    specific hypotheses about two first-batch results. They ran in a later batch from a
    rebuilt image with the same CLI versions.
13. **Not evaluated at all:** real models, interactive approval, Codex permission profiles
    and network proxy, Claude Code hooks and auto mode, exfiltration through built-in web
    tools or DNS, TLS exfiltration, macOS and Windows, IDE extensions, detection latency.
