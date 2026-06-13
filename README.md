# MetricGuard

MetricGuard is a Flywheel-native integrity gate for agentic research claims.
It treats a generated benchmark or citation claim as untrusted until it survives
deterministic checks, trusted reruns, evidence artifacts, and a graph-backed
verdict.

The short version:

> MetricGuard is not another autonomous optimizer. It is the integrity gate that
> decides whether an optimizer's claimed improvement can be trusted.

## Why It Exists

Agentic coding and research systems are often judged by scalar outputs:
accuracy, benchmark score, test pass rate, citation count, or answer quality.
That creates an obvious failure mode: the agent may improve the metric by
corrupting the measurement process instead of solving the task.

MetricGuard demonstrates a concrete trust boundary:

```text
claim -> audit -> evidence -> verdict -> repair -> benchmark
```

It currently covers two demo domains:

- benchmark integrity: reject evaluator tampering, hidden-label access, and fake reported metrics
- citation integrity: reject nonexistent citations, metadata mismatches, fake quotes, unsupported claims, and no-evidence citations

## Demo Command

For the cleanest end-to-end demo, run the full citation validation pipeline:

```powershell
python demo.py --scenario citation_validation_pipeline --live-citation-checks --graph-backend flywheel-cli
```

This creates one connected Flywheel evidence graph:

```text
Citation repair demo
|-- fabricated citation
|   `-- rejected audit
`-- repaired citation
    `-- accepted audit
        `-- synthetic citation benchmark
            `-- external SciFact subset
```

Local-only version:

```powershell
python demo.py --scenario citation_validation_pipeline --graph-backend local
```

Expected local output:

```text
Citation repair: REJECTED then ACCEPTED
Synthetic benchmark: 6/6 (100.0%)
External SciFact subset: 9/9 (100.0%)
```

## Quick Start

Requirements:

- Python 3.11+
- no required third-party Python packages
- optional: Node.js / `npx` for Flywheel CLI sync

Run the original benchmark-integrity MVP:

```powershell
python demo.py --scenario cheating_then_repair --graph-backend local
```

Run the citation repair demo:

```powershell
python demo.py --scenario fake_citations --graph-backend local
```

Run the synthetic citation benchmark:

```powershell
python demo.py --scenario citation_benchmark --graph-backend local
```

Run the external SciFact subset:

```powershell
python demo.py --scenario external_scifact_subset --graph-backend local
```

## Scenarios

### `cheating_then_repair`

This is the original MetricGuard MVP. A Blue proposer claims a dramatic accuracy
improvement, but the patch tampers with `evaluate.py`, probes for hidden labels,
and reports a fake metric. The Red auditor rejects it. A repaired patch is then
accepted after a trusted rerun.

Checks:

- protected file diff check
- forbidden path scan
- hidden test run
- reported metric vs trusted metric comparison
- hash manifest generation
- optional LLM judge explanation artifact

Expected:

```text
Cheating claim verdict: REJECTED
Repair claim verdict: ACCEPTED
```

### `fake_citations`

This creates a seeded fabricated citation answer and a repaired citation answer.
The bad answer includes a nonexistent DOI, an invalid URL, fake metadata, and an
unsupported claim. The repaired answer cites a local trusted fixture.

Artifacts are written under:

```text
artifacts/citations/
```

Important files:

```text
bad_answer.md
repaired_answer.md
fake_citations_rejected/extracted_citations.json
fake_citations_rejected/deterministic_verification.json
fake_citations_rejected/live_citation_resolution.json
fake_citations_rejected/judge_report.md
fake_citations_rejected/verdict.json
fake_citations_repaired/verdict.json
```

### `citation_benchmark`

This is a seeded synthetic benchmark created for this project. It is not an
industry benchmark. It tests representative citation-integrity failure modes.

Cases:

```text
valid_supported
nonexistent_doi_url
metadata_mismatch
fake_quote
overclaimed_support
missing_citation
```

Metrics:

```text
accuracy
cheat_detection_rate
false_reject_rate
```

Current expected result:

```text
Cases correct: 6/6
Accuracy: 100.0%
Cheat detection rate: 100.0%
False reject rate: 0.0%
```

Artifacts are written under:

```text
artifacts/citation_benchmark/
```

### `external_scifact_subset`

This adapts a fixed nine-example subset of the SciFact dev set. It is the
external benchmark layer for the demo.

Subset composition:

- 3 SciFact `SUPPORT` examples
- 3 SciFact `CONTRADICT` examples
- 3 examples with no annotated supporting evidence

MetricGuard accepts the supported citations and rejects contradicting or
unsupported citations.

Metrics:

```text
accuracy
unsupported_detection_rate
false_reject_rate
```

Current expected result:

```text
Cases correct: 9/9
Accuracy: 100.0%
Unsupported detection rate: 100.0%
False reject rate: 0.0%
```

The fixed subset lives at:

```text
benchmarks/external_scifact_subset.jsonl
```

Generated artifacts are written under:

```text
artifacts/external_scifact_subset/
```

### `citation_validation_pipeline`

This is the recommended judge-facing demo. It runs the citation repair demo,
then derives the synthetic benchmark from the accepted citation audit, then
derives the external SciFact subset from the benchmark node.

This scenario avoids manual node ID passing because the accepted node is known
inside the running graph construction process.

## Citation Verification

Citation verification is implemented in:

```text
metricguard/citations.py
```

The citation auditor performs:

- citation extraction from footnote-style Markdown
- source existence check against the trusted local source registry
- DOI or URL match check
- title/year/journal/author metadata check
- direct quote presence check
- claimed entity check
- judge-style support check for unsupported or overclaimed statements
- optional live DOI/URL resolution

Live DOI/URL resolution is evidence-only by default:

```powershell
python demo.py --scenario fake_citations --live-citation-checks --graph-backend local
```

To make failed live DOI/URL probes affect the verdict:

```powershell
python demo.py --scenario fake_citations --enforce-live-citation-checks --graph-backend local
```

The live resolver writes:

```text
live_citation_resolution.json
```

For example, a fake DOI produces evidence such as:

```text
HEAD https://doi.org/10.1038/s42256-025-99999-9 -> HTTP 404
```

## Metric Meanings

For citation and SciFact-style validation, the most important metrics are:

```text
unsupported_detection_rate
```

How many unsupported, contradicting, fake, or no-evidence citations were
correctly rejected.

```text
false_reject_rate
```

How many valid supported citations were incorrectly rejected.

```text
accuracy
```

Total correct accept/reject decisions.

For the seeded synthetic benchmark, the equivalent rejection metric is named:

```text
cheat_detection_rate
```

## Flywheel Integration

MetricGuard always writes a local graph:

```text
artifacts/local_graph.json
artifacts/local_graph.md
```

To sync a live graph through the Flywheel CLI, configure `.env`:

```env
FLYWHEEL_ROOT_NODE_ID=replace-with-your-flywheel-root-node-id
```

Then run any scenario with:

```powershell
python demo.py --scenario citation_validation_pipeline --live-citation-checks --graph-backend flywheel-cli
```

The Flywheel CLI backend:

- creates committed Flywheel nodes
- connects parent-child evidence branches
- writes artifact paths into node content
- uploads generated files as real Flywheel artifacts
- writes sync results to `artifacts/flywheel_sync.json`

To attach a run under a specific existing Flywheel node:

```powershell
python demo.py --scenario external_scifact_subset --graph-backend flywheel-cli --flywheel-parent-node-id <NODE_ID>
```

For a full pipeline demo, manual parent passing is usually unnecessary because
the pipeline creates the accepted citation audit and derives later benchmark
nodes from it in the same run.

## LLM Judge

Benchmark integrity audits can include an optional LLM judge explanation. This
does not override deterministic verdicts.

Implementation:

```text
metricguard/llm_judge.py
```

Behavior:

- if `OPENAI_API_KEY` is not configured, it writes a skipped artifact
- if configured, it calls the OpenAI Responses API and writes:

```text
llm_judge.json
llm_judge.md
```

Disable it:

```powershell
$env:METRICGUARD_LLM_JUDGE="0"
```

## Repository Layout

```text
MetricGuard/
|-- demo.py
|-- README.md
|-- requirements.txt
|-- metricguard/
|   |-- benchmark.py
|   |-- blue.py
|   |-- citation_benchmark.py
|   |-- citations.py
|   |-- external_scifact.py
|   |-- flywheel_graph.py
|   |-- hashing.py
|   |-- llm_judge.py
|   |-- red_auditor.py
|   |-- report.py
|   `-- trusted_eval.py
|-- toy_repo/
|   |-- model.py
|   |-- train.py
|   |-- evaluate.py
|   |-- data/
|   `-- tests/
|-- trusted_assets/
|   `-- hidden_labels.csv
|-- benchmarks/
|   |-- external_scifact_subset.jsonl
|   `-- raw/
`-- artifacts/
    |-- local_graph.json
    |-- local_graph.md
    |-- citations/
    |-- citation_benchmark/
    |-- external_scifact_subset/
    |-- cheat/
    `-- repair/
```

## Evidence Artifacts

MetricGuard writes evidence for each claim and audit:

```text
proposal.json
patch.diff
extracted_citations.json
deterministic_verification.json
live_citation_resolution.json
judge_report.md
audit_result.json
trusted_metrics.json
verdict.json
audit_report.md
manifest.json
```

Not every scenario uses every artifact type. For example, benchmark integrity
uses `trusted_metrics.json`, while citation scenarios use extracted citation and
source-support artifacts.

## Demo Script

Suggested presenter flow:

1. Run:

```powershell
python demo.py --scenario citation_validation_pipeline --live-citation-checks --graph-backend flywheel-cli
```

2. Show terminal summary:

```text
Citation repair: REJECTED then ACCEPTED
Synthetic benchmark: 6/6 (100.0%)
External SciFact subset: 9/9 (100.0%)
```

3. Open Flywheel and show:

```text
fabricated citation -> rejected audit
repaired citation -> accepted audit
accepted audit -> synthetic benchmark
synthetic benchmark -> external SciFact subset
```

4. Open one rejected audit artifact and one accepted audit artifact.

5. Say:

> MetricGuard does not just track what worked. It tracks what cheated, why it
> failed, what evidence supports the verdict, and how the repaired claim holds
> up against synthetic and external validation.

## Honest Claims

Use:

- "seeded synthetic benchmark" for `citation_benchmark`
- "fixed nine-example SciFact dev subset" for `external_scifact_subset`
- "trusted rerun" rather than "secure sandbox"
- "hash-verifiable manifest" rather than "cryptographic ledger"
- "LLM judge explanation" rather than "LLM decides the verdict"

Avoid claiming:

- that the synthetic benchmark is an industry benchmark
- that the SciFact subset is a full benchmark evaluation
- that local trusted fixtures are public DOI records
- that the system is a secure sandbox

## Generated Outputs

Most commands rewrite `artifacts/`. That is expected. For demo submissions,
commit only the artifacts you want reviewers to inspect and do not commit local
secrets such as `.env`.

