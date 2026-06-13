# MetricGuard

MetricGuard is a Flywheel-native integrity gate for agentic research claims. It
does not optimize a benchmark; it decides whether a claimed improvement or cited
answer can be trusted.

```text
claim -> audit -> evidence -> verdict -> repair -> benchmark
```

MetricGuard records rejected claims, accepted repairs, audit artifacts, and
benchmark results as a connected Flywheel evidence graph.

## What It Checks

MetricGuard currently demonstrates two trust boundaries:

- **Benchmark integrity**: detects evaluator tampering, hidden-label access, fake reported metrics, and failed trusted reruns.
- **Citation integrity**: detects nonexistent DOI/URL targets, metadata mismatches, fake quotes, unsupported claims, and no-evidence citations.

## Best Demo Command

Run the full citation validation pipeline locally:

```powershell
python demo.py --scenario citation_validation_pipeline --graph-backend local
```

Run the same pipeline and sync it to Flywheel:

```powershell
python demo.py --scenario citation_validation_pipeline --live-citation-checks --graph-backend flywheel-cli
```

## Scenarios

| Scenario | Purpose |
|---|---|
| `cheating_then_repair` | Original benchmark-integrity demo: reject a cheating patch, accept a repaired patch. |
| `fake_citations` | Reject a fabricated citation answer, accept a repaired supported answer. |
| `citation_benchmark` | Seeded synthetic citation benchmark with six representative failure modes. |
| `external_scifact_subset` | Fixed nine-example SciFact dev subset for external validation. |
| `citation_validation_pipeline` | Recommended end-to-end graph combining repair, synthetic benchmark, and SciFact subset. |

Examples:

```powershell
python demo.py --scenario cheating_then_repair --graph-backend local
python demo.py --scenario citation_benchmark --graph-backend local
python demo.py --scenario external_scifact_subset --graph-backend local
```

## Benchmark Results

### Synthetic Citation Benchmark

This is a seeded project-specific benchmark, not an industry benchmark.

Cases:

```text
valid_supported
nonexistent_doi_url
metadata_mismatch
fake_quote
overclaimed_support
missing_citation
```

Expected result:

```text
Cases correct: 6/6
Accuracy: 100.0%
Cheat detection rate: 100.0%
False reject rate: 0.0%
```

Artifacts:

```text
artifacts/citation_benchmark/
```

### External SciFact Subset

MetricGuard also evaluates a fixed nine-example subset of SciFact dev:

- 3 `SUPPORT` examples
- 3 `CONTRADICT` examples
- 3 no-annotated-evidence examples

Expected result:

```text
Cases correct: 9/9
Accuracy: 100.0%
Unsupported detection rate: 100.0%
False reject rate: 0.0%
```

Fixed subset:

```text
benchmarks/external_scifact_subset.jsonl
```

Artifacts:

```text
artifacts/external_scifact_subset/
```

## Metric Meanings

| Metric | Meaning |
|---|---|
| `unsupported_detection_rate` | Bad, contradicting, fake, or no-evidence citations correctly rejected. |
| `cheat_detection_rate` | Synthetic citation failures correctly rejected. |
| `false_reject_rate` | Valid supported citations incorrectly rejected. |
| `accuracy` | Overall accept/reject correctness. |

## Citation Verification

Implemented in:

```text
metricguard/citations.py
```

Checks:

- extracts Markdown footnote citations
- validates source existence against a trusted registry
- checks DOI/URL, title, year, journal, and authors
- verifies direct quotes when present
- checks whether the source supports or overclaims the cited statement
- optionally resolves public DOI/URL targets live

Live DOI/URL checks are evidence-only by default:

```powershell
python demo.py --scenario fake_citations --live-citation-checks --graph-backend local
```

To make failed live probes affect verdicts:

```powershell
python demo.py --scenario fake_citations --enforce-live-citation-checks --graph-backend local
```

Live evidence is written to:

```text
live_citation_resolution.json
```

## Benchmark Integrity Checks

Implemented in:

```text
metricguard/red_auditor.py
metricguard/trusted_eval.py
```

Checks:

- protected file diff check
- forbidden hidden-path scan
- hidden test execution
- trusted metric recomputation
- reported-vs-trusted metric comparison
- manifest generation
- optional LLM judge explanation artifact

The LLM judge never overrides the deterministic verdict.

## Flywheel Integration

MetricGuard always writes a local graph:

```text
artifacts/local_graph.json
artifacts/local_graph.md
```

To sync a live graph through Flywheel CLI, configure:

```env
FLYWHEEL_ROOT_NODE_ID=replace-with-your-flywheel-root-node-id
```

Then run:

```powershell
python demo.py --scenario citation_validation_pipeline --live-citation-checks --graph-backend flywheel-cli
```

The Flywheel backend:

- creates committed nodes
- connects parent-child evidence branches
- uploads generated files as Flywheel artifacts
- writes sync details to `artifacts/flywheel_sync.json`

For manual continuation from an existing node:

```powershell
python demo.py --scenario external_scifact_subset --graph-backend flywheel-cli --flywheel-parent-node-id <NODE_ID>
```

The full pipeline usually does not need manual parent IDs because it creates the
accepted node and later benchmark branches in one run.

## Honest Scope

- `citation_benchmark` is a seeded synthetic benchmark.
- `external_scifact_subset` is a fixed nine-example SciFact dev subset, not a full SciFact evaluation.
- MetricGuard uses trusted reruns, not a secure sandbox.
- Manifests are hash-verifiable, not a cryptographic ledger.
- LLM judge output is explanatory; deterministic checks decide the verdict.

Generated commands rewrite `artifacts/`. Do not commit local secrets such as
`.env`.

