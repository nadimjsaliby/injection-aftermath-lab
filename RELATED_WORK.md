# Related work

Compiled on 2026-11-25. Each entry was opened at the URL given during a single literature
pass, and every link was re-checked on the same date to resolve to the work named. Venues are stated only where the page showed them. Summaries describe what the source
says about itself; none of the numbers below were reproduced here.

## Closest prior work

| Work | What it does | How this study differs |
|---|---|---|
| Zhu et al., "HarnessSecurity-Bench: Do Security Mechanisms Really Protect Coding Agent Harnesses?", 2026. [arXiv:2610.07639](https://arxiv.org/abs/2610.07639) | Six harnesses including Claude Code and Codex CLI, attacks delivered through content the agent reads, security mechanisms toggled, oracles outside the agent | Does not condition on obedience; file and canary oracles instead of syscall and packet records; audit logging is in its taxonomy but outside its experiments |
| Davidovich et al., "Permission Denied: Policy-Graded Evaluation of Coding Agents in Hardened Environments", 2026. [arXiv:2608.02670](https://arxiv.org/abs/2608.02670) | Task success of model and harness bundles under three policy levels | Utility cost of hardening on benign tasks; no injection |
| Commey, "Names Are Not Objects: Object-Bound Confinement for Compromised AI Coding Agents", 2026. [arXiv:2610.14488](https://arxiv.org/abs/2610.14488) | Assumes a compromised agent; compares a new confinement broker with allowlist and sandbox baselines | Proposes a mechanism; baselines are generic rather than the shipped controls; no evidence analysis |
| Ji et al., "Measuring the Permission Gate: A Stress-Test Evaluation of Claude Code's Auto Mode", 2026. [arXiv:2604.04978](https://arxiv.org/abs/2604.04978) | False negative rate of an automatic permission classifier | Injection and the sandbox are out of its scope; auto mode is out of ours |
| Gruber and Hilgert, "Foundations for Investigations of Agentic AI Systems from the Forensic Analysis of OpenClaw", 2026. [arXiv:2604.05589](https://arxiv.org/abs/2604.05589) | Differential forensic analysis and an artifact taxonomy for an agent | Personal assistant, not coding agents; no attack or control variable |
| Qin et al., "LLM Agents Can Easily Tamper With Their Own Traces", 2026. [arXiv:2609.30266](https://arxiv.org/abs/2609.30266) | Agents deleting their own traces on request | Motivates evidence the agent cannot write to; does not measure completeness |
| Yun et al., "Correct Answers, Unsupported Findings: Evidence Binding in Forensic Reconstruction of LLM Agent Logs", 2026. [arXiv:2610.09581](https://arxiv.org/abs/2610.09581) | LLM readers reconstructing incidents from saved agent logs | Tests the reader, with a reference derived from the same records |

## Indirect prompt injection and agent benchmarks

- Greshake et al., "Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection", 2023. [arXiv:2302.12173](https://arxiv.org/abs/2302.12173)
- Zhan et al., "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents", 2024. [arXiv:2403.02691](https://arxiv.org/abs/2403.02691)
- Debenedetti et al., "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents", 2024. [arXiv:2406.13352](https://arxiv.org/abs/2406.13352)
- Zhang et al., "Agent Security Bench (ASB)", ICLR 2025. [arXiv:2410.02644](https://arxiv.org/abs/2410.02644)
- Guo et al., "RedCode: Risky Code Execution and Generation Benchmark for Code Agents", NeurIPS 2024 Datasets and Benchmarks. [arXiv:2411.07781](https://arxiv.org/abs/2411.07781)
- Liu et al., "'Your AI, My Shell': Demystifying Prompt Injection Attacks on Agentic AI Coding Editors", 2025. [arXiv:2509.22040](https://arxiv.org/abs/2509.22040)
- Schmotz et al., "Skill-Inject: Measuring Agent Vulnerability to Skill File Attacks", 2026. [arXiv:2602.20156](https://arxiv.org/abs/2602.20156)
- Isbarov et al., "GitInject: Real-World Prompt Injection Attacks in AI-Powered CI/CD Pipelines", 2026. [arXiv:2606.09935](https://arxiv.org/abs/2606.09935)
- He et al., "When Context Gets Root: Privilege Escalation in LLM Harnesses", 2026. [arXiv:2608.27299](https://arxiv.org/abs/2608.27299)
- Maloyan and Namiot, "Prompt Injection Attacks on Agentic Coding Assistants: A Systematic Analysis", 2026. [arXiv:2601.17548](https://arxiv.org/abs/2601.17548)
- Karliner, "New Vulnerability in GitHub Copilot and Cursor: How Hackers Can Weaponize Code Agents", Pillar Security, 2025. [pillar.security](https://www.pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents)

These measure whether an agent obeys. This study starts from the point where it has.

## Defense by system design

- Debenedetti et al., "Defeating Prompt Injections by Design" (CaMeL), 2025. [arXiv:2503.18813](https://arxiv.org/abs/2503.18813)
- Beurer-Kellner et al., "Design Patterns for Securing LLM Agents against Prompt Injections", 2025. [arXiv:2506.08837](https://arxiv.org/abs/2506.08837)
- Wu et al., "IsolateGPT: An Execution Isolation Architecture for LLM-Based Agentic Systems", NDSS 2025. [arXiv:2403.04960](https://arxiv.org/abs/2403.04960)
- Wu, Cecchetti and Xiao, "System-Level Defense against Indirect Prompt Injection Attacks: An Information Flow Control Perspective", 2024. [arXiv:2409.19091](https://arxiv.org/abs/2409.19091)
- Willison, "The lethal trifecta for AI agents: private data, untrusted content, and external communication", 2025. [simonwillison.net](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)
- Meta, "Agents Rule of Two: A Practical Approach to AI Agent Security", 2025. [ai.meta.com](https://ai.meta.com/blog/practical-ai-agent-security/)
- Rashidi, "The Balkanization of Execution-Security Research for AI Coding Agents", 2026. [arXiv:2607.05743](https://arxiv.org/abs/2607.05743)

## Vendor documentation used to configure the conditions

- Anthropic, "Beyond permission prompts: making Claude Code more secure and autonomous", 2025. [anthropic.com/engineering/claude-code-sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing)
- Anthropic, "How we contain Claude across products", 2026. [anthropic.com/engineering/how-we-contain-claude](https://www.anthropic.com/engineering/how-we-contain-claude)
- Claude Code documentation: [permissions](https://code.claude.com/docs/en/permissions), [permission modes](https://code.claude.com/docs/en/permission-modes), [sandboxing](https://code.claude.com/docs/en/sandboxing), [monitoring](https://code.claude.com/docs/en/monitoring-usage), [security](https://code.claude.com/docs/en/security)
- Anthropic sandbox-runtime. [github.com/anthropics/sandbox-runtime](https://github.com/anthropics/sandbox-runtime)
- OpenAI Codex documentation on approvals, sandboxing, rules, MCP and non-interactive mode. Page used: [approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security). On the review date `developers.openai.com/codex` redirected to `learn.chatgpt.com/docs`.
- Codex Linux sandbox README. [github.com/openai/codex](https://github.com/openai/codex/blob/main/codex-rs/linux-sandbox/README.md)

The Claude Code pages describe a newer release than the 2.1.220 tested here, and the Codex
pages are unversioned. Where the documentation and the observed behaviour of the pinned
versions differ, the posts report the observation and say so.

## Observability, audit and forensics

- Zheng et al., "AgentSight: System-Level Observability for AI Agents Using eBPF", 2025. [arXiv:2508.02736](https://arxiv.org/abs/2508.02736)
- Chan et al., "Visibility into AI Agents", FAccT 2024. [arXiv:2401.13138](https://arxiv.org/abs/2401.13138)
- Ezell et al., "Incident Analysis for AI Agents", AIES 2025. [arXiv:2508.14231](https://arxiv.org/abs/2508.14231)
- Dehghantanha and Homayoun, "AI Forensics Across White-, Grey-, and Black-Box Access", 2026. [arXiv:2608.03520](https://arxiv.org/abs/2608.03520)
- Rowlingson, "A Ten Step Process for Forensic Readiness", International Journal of Digital Evidence 2(3), 2004. [PDF](https://www.utica.edu/academic/institutes/ecii/publications/articles/A0B13342-B4E0-1F6A-156F501C49CF5F51.pdf)
- Kent et al., NIST SP 800-86, "Guide to Integrating Forensic Techniques into Incident Response", 2006. [csrc.nist.gov](https://csrc.nist.gov/pubs/sp/800/86/final)
- OpenTelemetry semantic conventions for generative AI. [opentelemetry.io](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (on the review date this page was a notice that the conventions have moved to a separate repository)

## Taxonomies

- OWASP Top 10 for LLM Applications 2025: [LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), [LLM06 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
- OWASP Top 10 for Agentic Applications for 2026. [genai.owasp.org](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- Vassilev et al., NIST AI 100-2 E2025, "Adversarial Machine Learning: A Taxonomy and Terminology of Attacks and Mitigations". [csrc.nist.gov](https://csrc.nist.gov/pubs/ai/100/2/e2025/final)
- MITRE ATLAS lists LLM prompt injection as AML.T0051 with an indirect sub-technique. The official ATLAS page could not be opened during the review, so no link is given.

## Novelty statement

No single work was found that measures both containment by shipped harness controls and
post-incident evidence completeness for coding agents against independent ground truth.
Evaluating harness controls under content-borne attacks is **not** new (HarnessSecurity-Bench).
The contribution claimed here is the combination: obedience fixed by construction, kernel
and network level ground truth, and evidence sources graded on the same runs. The search was
one pass over a field publishing several papers a month, so this is a statement about what
was found, not proof of absence.
