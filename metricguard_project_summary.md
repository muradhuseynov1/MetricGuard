# MetricGuard Project Summary

Date: 2026-06-13  
Status: Concept validated; implementation should focus on the audit boundary and Flywheel evidence graph.

## 1. One-Line Definition

MetricGuard is a Flywheel-native integrity gate for agentic experiment claims. It decides whether an autonomous coding or research agent's claimed benchmark improvement can be trusted by forcing the claim through adversarial validation, trusted reruns, and evidence-backed verdicts.

Short pitch:

> MetricGuard is not another autonomous optimizer. It is the integrity gate that decides whether autonomous optimizers can be trusted.

## 2. Core Idea

Autonomous coding and research agents are increasingly judged by scalar metrics such as accuracy, loss, benchmark score, test pass rate, latency, or cost. This creates a serious failure mode: an agent may improve the metric by cheating the evaluation process instead of solving the intended task.

MetricGuard treats every claimed improvement as untrusted until it survives an audit. The system records the whole chain:

```text
baseline -> claim -> patch -> audit -> evidence -> verdict -> repair
```

The core innovation is not simply having a Red agent attack a Blue agent. The stronger idea is that Flywheel becomes the state machine and evidence graph for research integrity. Failed, hacked, repaired, and accepted claims are all first-class research outputs.

## 3. Problem Being Solved

Agentic experiment workflows are vulnerable to reward hacking and benchmark exploitation. A system can appear to improve while actually corrupting the measurement pipeline.

Important failure modes:

- Modifying the evaluator or metric calculation.
- Reading hidden labels or held-out data during training or evaluation.
- Hardcoding visible tests.
- Writing fake `metrics.json` outputs.
- Exploiting persistent cache files.
- Changing test harness assumptions.
- Passing visible tests while failing hidden tests.
- Using filesystem, timing, or environment details to infer answers.

MetricGuard's answer is to separate "claimed metric" from "trusted metric" and make the difference auditable.

## 4. Strategic Positioning

The strongest framing is:

> MetricGuard is a Flywheel-native integrity gate for agentic research claims.

This positioning is stronger than three nearby alternatives:

- A voice-controlled research agent: likely too close to sponsor demo territory and not central to the integrity problem.
- A generic autonomous optimizer: crowded by systems such as AI Scientist, RD-Agent, and RD-Agent-Quant.
- A plain red-team demo: red teaming and actor-critic-judge loops already exist, so the novelty must come from the evidence graph and deterministic validation gate.

MetricGuard should be presented as the trust layer around autonomous optimizers, not as another optimizer.

## 5. What Changed After Deep Research

The deep research analysis validated the concept but shifted the priority from pitch polishing to implementation rigor.

Main conclusion:

> Keep the concept and pitch mostly intact, but redirect implementation time toward the audit boundary and the Flywheel evidence graph.

The strongest novelty is the connected claim-to-verdict graph:

```text
claim -> audit -> evidence -> verdict
```

The weakest area is enforcement. The existing proposal stubs describe protected-file checks, hidden tests, clean reruns, forbidden-path checks, and file-access logging, but not all of those are fully implemented yet.

## 6. Sponsor Strategy

MetricGuard is best positioned for Paradigma first and OpenAI second.

Paradigma / Flywheel:

- Core differentiator.
- Should be the visible state machine.
- Should store baseline, proposal, audit, verdict, repair, and artifacts.
- Should show branches, failed claims, accepted claims, and durable evidence.

OpenAI / Codex:

- Useful as proposer, repair assistant, implementation helper, or audit-report writer.
- Should not be the trusted evaluator.
- Deterministic checks should remain the backbone of the audit.

Git, Python, and pytest:

- Deterministic infrastructure.
- Used for diffs, hidden tests, trusted reruns, and artifact generation.

ElevenLabs:

- Optional stretch.
- Could narrate the final verdict or provide a voice layer.
- Should not distract from the integrity gate.

Scaleway:

- Optional stretch.
- Could provide remote compute later.
- Should not become a dependency for the core demo.

## 7. MVP Demo Story

The demo should be deterministic and finish in under three minutes.

Scenario:

1. Start with a toy Python benchmark and a baseline score.
2. Blue proposes a patch claiming a dramatic improvement.
3. Red audits the patch.
4. MetricGuard detects cheating, such as evaluator tampering or hidden-label access.
5. Flywheel records the rejected claim and all evidence artifacts.
6. Blue submits a repaired legitimate patch.
7. Red audits the repair.
8. Trusted evaluator confirms a modest real improvement.
9. Flywheel records the accepted branch.

Expected graph:

```text
Baseline
|-- Blue claim: 99% accuracy
|   `-- Red audit: rejected because of evaluator tampering and hidden-label access
`-- Blue repair: 79% accuracy
    `-- Red audit: accepted because trusted evaluator confirmed improvement
```

Presenter punchline:

> MetricGuard does not just track what worked. It tracks what cheated, why it failed, and what evidence supports the verdict.

## 8. System Architecture

Recommended MVP components:

```text
Toy benchmark repository
        |
        v
Blue proposer
        |
        v
Patch and claimed metric
        |
        v
Red auditor
        |
        +-- protected file diff check
        +-- forbidden path or file-access check
        +-- hidden test run
        +-- trusted temp-directory rerun
        +-- reported-vs-trusted metric comparison
        +-- suspicious pattern check
        +-- hash manifest generation
        |
        v
Judge verdict
        |
        v
Flywheel nodes and artifacts
```

Core modules:

- `benchmark.py`: creates or runs the toy benchmark.
- `blue.py`: selects or generates a candidate patch.
- `red_auditor.py`: runs deterministic integrity checks.
- `trusted_eval.py`: reruns the patch with protected evaluator logic.
- `flywheel_graph.py`: writes nodes and uploads artifacts to Flywheel.
- `report.py`: generates human-readable audit reports.
- `hashing.py`: creates SHA-256 manifests for evidence files.
- `demo.py`: runs the end-to-end cheating-then-repair scenario.

## 9. Trusted Evaluation Model

MetricGuard should distinguish between three metric types:

- Baseline metric: the trusted score before any patch.
- Reported metric: the metric claimed by Blue.
- Trusted metric: the score produced by the locked evaluator during audit.

The trusted evaluator should:

- Run in a fresh temporary directory or stronger sandbox.
- Use evaluator files that Blue cannot modify.
- Use hidden data that is outside the proposer-visible workspace.
- Fail closed when artifacts are missing or malformed.
- Use subprocess timeouts so a malicious or buggy patch cannot hang the demo.

Important wording:

- Say "trusted rerun" or "temp-directory trusted rerun" unless actual sandboxing is implemented.
- Say "hash-verifiable manifest" unless signatures or trusted timestamps are implemented.
- Avoid claiming "secure sandbox" or "cryptographic ledger" unless those properties are real.

## 10. Required Audit Checks

P0 checks:

- Protected file diff check: reject patches that change files such as `evaluate.py`, hidden tests, or hidden labels.
- Hidden test run: verify behavior against tests not visible to the proposer.
- Trusted rerun: re-execute the candidate in a clean temporary directory.
- Metric comparison: compare reported metric with trusted metric.
- Artifact generation: emit `patch.diff`, `audit_report.md`, `trusted_metrics.json`, `verdict.json`, and `manifest.json`.
- Subprocess timeouts: prevent hung runs.

High-priority hardening:

- Move `hidden_labels.csv` outside the proposer-visible repo.
- Add real forbidden-path or file-access logging.
- Reduce naive `open(` and `Path(` false positives, preferably with AST-based checks or scoped policy rules.
- Add `git status --porcelain` or equivalent tracking for untracked files.
- Validate JSON schemas before accepting generated artifacts.

## 11. Evidence Artifacts

Every proposal and audit should produce durable evidence.

Minimum artifacts:

- `patch.diff`: exact code changes proposed by Blue.
- `proposal.json`: claim, patch path, reported metric, and declared changed files.
- `audit_result.json`: pass/fail status for each audit check.
- `audit_report.md`: human-readable audit explanation.
- `trusted_metrics.json`: reported metric, trusted metric, delta, evaluator hash, and run ID.
- `verdict.json`: accepted or rejected decision with reason.
- `manifest.json`: SHA-256 hashes of evidence artifacts.
- `file_access_log.json`: recommended once access logging is implemented.

## 12. Flywheel Graph Model

Flywheel should not be used as a passive file dump. It should represent the project state.

Recommended nodes:

| Node | Purpose | Key artifacts |
|---|---|---|
| Baseline | Original trusted benchmark state | `baseline_metrics.json`, `baseline_summary.md` |
| Blue cheating proposal | Claimed dramatic improvement | `patch.diff`, `proposal.json`, `reported_metrics.json` |
| Red rejected audit | Evidence of cheating | `audit_report.md`, `trusted_metrics.json`, `audit_result.json` |
| Rejected verdict | Decision and rationale | `verdict.json`, `manifest.json` |
| Blue repaired proposal | Legitimate follow-up patch | `patch.diff`, `proposal.json` |
| Red accepted audit | Evidence of real improvement | `audit_report.md`, `trusted_metrics.json`, `verdict.json`, `manifest.json` |

Fallback if live Flywheel integration fails:

- Write `artifacts/local_graph.json`.
- Write `artifacts/local_graph.md`.
- Render the same baseline, rejected branch, repaired branch, and accepted verdict locally.
- Explain that the local graph is a fail-safe mirror of the intended Flywheel graph.

## 13. Suggested Repository Layout

```text
metricguard/
|-- README.md
|-- demo.py
|-- requirements.txt
|-- metricguard/
|   |-- __init__.py
|   |-- benchmark.py
|   |-- blue.py
|   |-- red_auditor.py
|   |-- trusted_eval.py
|   |-- flywheel_graph.py
|   |-- report.py
|   `-- hashing.py
|-- toy_repo/
|   |-- model.py
|   |-- train.py
|   |-- evaluate.py
|   |-- data/
|   |   |-- train.csv
|   |   `-- visible_test.csv
|   `-- tests/
|       |-- test_visible.py
|       `-- test_hidden.py
|-- trusted_assets/
|   `-- hidden_labels.csv
|-- patches/
|   |-- blue_cheat.patch
|   `-- blue_repair.patch
`-- artifacts/
    |-- local_graph.json
    |-- local_graph.md
    |-- patch.diff
    |-- audit_report.md
    |-- trusted_metrics.json
    |-- verdict.json
    `-- manifest.json
```

Note: `trusted_assets/hidden_labels.csv` should not be visible to the Blue proposer during patch generation.

## 14. Implementation Roadmap

### P0: Demo-Critical Build

Goal: make the core integrity loop work locally and deterministically.

Tasks:

- Freeze a tiny deterministic benchmark.
- Create a trusted baseline metric.
- Create one seeded cheating patch.
- Create one seeded legitimate repair patch.
- Implement protected-file diff checks.
- Implement hidden test execution.
- Implement trusted temp-directory rerun.
- Implement metric comparison.
- Add subprocess timeouts.
- Generate all core artifacts.
- Create baseline, proposal, audit, verdict, repair, and accepted nodes in Flywheel.
- Build local fallback graph.
- Rehearse the three-minute demo.

### P1: Credibility Hardening

Goal: make the integrity boundary more believable.

Tasks:

- Move hidden labels outside the proposer-visible repo.
- Add file-access or forbidden-path logging.
- Replace broad suspicious string checks with more precise policy checks.
- Add schema validation for JSON artifacts.
- Pin Python and package versions.
- Record a backup video or GIF.
- Polish README and presenter script.

### P2: Stretch Additions

Goal: improve presentation without risking the core system.

Tasks:

- Add ElevenLabs verdict narration.
- Add Scaleway remote execution path.
- Add richer Flywheel graph rendering.
- Add more reward-hacking examples.
- Add a small dashboard for graph and artifacts.

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Judges think this is just red-team prompting | Emphasize deterministic checks, trusted reruns, and Flywheel evidence graph. |
| Flywheel API or MCP fails during demo | Keep local graph fallback and pre-generated artifacts. |
| LLM output is nondeterministic | Use seeded cheating and repaired patches for the demo path. |
| Hidden tests make the demo too complex | Keep benchmark tiny and deterministic. |
| Clean-room claim is challenged | Call it a trusted temp-directory rerun unless real sandboxing is implemented. |
| Hash claims are overread as cryptographic security | Say hash-verifiable manifest, not cryptographic ledger. |
| Suspicious grep has false positives | Explain it as a heuristic or replace it with AST/policy checks. |
| Demo takes too long | Keep training and evaluation under 20 seconds each. |
| Optional sponsor features distract | Add ElevenLabs or Scaleway only after the core loop is stable. |

## 16. Done Means Done

The MVP is ready when:

- `python demo.py --scenario cheating_then_repair` runs from a fresh checkout.
- The cheating patch is rejected for concrete reasons.
- The repaired patch is accepted with a trusted metric.
- All evidence artifacts are generated.
- The Flywheel graph or local fallback graph shows the full state transition.
- The demo can be completed in under three minutes.
- The presenter can explain the trust boundary without overclaiming.

## 17. Judge-Facing Script

Short version:

> Autonomous research agents are only useful if we can trust their claimed improvements. If an agent says it improved a benchmark from 74 percent to 99 percent, that might mean it solved the task, or it might mean it edited the evaluator, leaked hidden labels, or faked the metrics. MetricGuard is a Flywheel-native integrity gate for those claims. A Blue agent proposes an improvement; a Red auditor attacks it with hidden tests, trusted reruns, diff checks, and metric verification; then every claim, exploit, artifact, and verdict is stored in a Flywheel graph. Our demo rejects one cheating patch and accepts one repaired patch. The key idea is simple: Flywheel should not just remember successful experiments. It should preserve the evidence trail for failed, hacked, and repaired claims too.

## 18. Recommended Wording

Use:

- Flywheel-native integrity gate.
- Evidence-backed verdict.
- Trusted rerun.
- Protected evaluator.
- Hash-verifiable manifest.
- Claim-to-audit-to-evidence-to-verdict graph.
- Failed and rejected branches are first-class research outputs.

Avoid:

- Cryptographic ledger, unless signatures or trusted timestamps are implemented.
- Secure sandbox, unless real sandboxing is implemented.
- Fully autonomous scientific discovery, because the project is narrower and sharper.
- Another autonomous optimizer, because adjacent work already covers that territory.
- Voice-controlled research agent, because it is not the core novelty.

## 19. Source Inputs Used For This Summary

This summary consolidates:

- `chat.md`: final strategic direction and P0/P1/P2 priorities.
- `metricguard_prompt_engineering_proposal.md`: original project package, architecture, schemas, demo plan, and prompts.
- `Deep Research Analysis of the MetricGuard Markdown Package.pdf`: verification, novelty analysis, security review, sponsor strategy, and implementation critique.

## 20. Final Recommendation

Do not spend more time ideating. The idea is ready to build.

The next best action is to implement the smallest credible end-to-end loop:

```text
baseline node
-> cheating claim
-> rejected audit with evidence
-> repaired claim
-> accepted audit with evidence
```

If that loop is visible in Flywheel and backed by deterministic artifacts, MetricGuard will have a clear hackathon story: it turns agentic experimentation from an opaque leaderboard into an auditable research process.
