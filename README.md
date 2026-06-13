# MetricGuard

MetricGuard is a deterministic integrity gate for agentic benchmark claims. A
Blue proposer makes a claimed improvement, a Red auditor reruns it through a
protected evaluator and hidden data, and the resulting evidence is written into
a local Flywheel-style graph.

Run the full MVP demo:

```bash
python3 demo.py --scenario cheating_then_repair
```

The demo creates:

- a trusted baseline metric
- one cheating claim that is rejected
- one repaired claim that is accepted
- evidence artifacts under `artifacts/`
- optional LLM judge explanation artifacts when `OPENAI_API_KEY` is configured
- a local fallback graph in `artifacts/local_graph.json` and
  `artifacts/local_graph.md`

No third-party packages are required.

## Optional LLM Judge Explanation

MetricGuard's final verdict is always deterministic. If `OPENAI_API_KEY` is
configured, the audit also asks an LLM to write a concise judge-facing
explanation of the evidence. The explanation is written to `llm_judge.json`,
`llm_judge.md`, and included in `audit_report.md`.

```bash
export OPENAI_API_KEY="your-key"
export METRICGUARD_LLM_JUDGE_MODEL="gpt-5.5"
```

If no API key is configured, the demo still runs and records the LLM judge
artifact as skipped.

## Optional Live Flywheel Graph

The demo always writes the local fallback graph. To also sync live graph nodes
to Flywheel, configure the Flywheel CLI once:

```bash
npx --yes @paradigma-inc/flywheel setup --mode cli
flywheel auth:status
```

Then either export these variables or put them in a local `.env` file copied
from `.env.example`:

```bash
export FLYWHEEL_ROOT_NODE_ID="your-existing-project-node-id"
export FLYWHEEL_UPDATED_BY="your-name"
```

Then run:

```bash
python3 demo.py --scenario cheating_then_repair --graph-backend flywheel
```

Sync results are written to `artifacts/flywheel_sync.json`. Payloads sent to
the CLI are written to `artifacts/flywheel_payloads/`. If `FLYWHEEL_ROOT_NODE_ID`
is configured, the baseline node is created under that Flywheel project node.
Child proposal and audit nodes are connected through Flywheel parent IDs
returned by earlier `flywheel nodes:commit-new` calls.

