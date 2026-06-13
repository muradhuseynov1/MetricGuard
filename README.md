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
- a local fallback graph in `artifacts/local_graph.json` and
  `artifacts/local_graph.md`

No third-party packages are required.

## Optional Live Flywheel Graph

The demo always writes the local fallback graph. To also sync live graph nodes
and edges to Flywheel, either export these variables or put them in a local `.env`
file copied from `.env.example`:

```bash
export FLYWHEEL_API_BASE_URL="https://your-flywheel-api.example.com"
export FLYWHEEL_API_TOKEN="your-token"
export FLYWHEEL_PROJECT_ID="your-project-id"
```

If your Flywheel API uses project-scoped paths, override the endpoint templates:

```bash
export FLYWHEEL_NODES_PATH="/projects/{project_id}/nodes"
export FLYWHEEL_EDGES_PATH="/projects/{project_id}/edges"
```

Then run:

```bash
python3 demo.py --scenario cheating_then_repair --graph-backend flywheel
```

Sync results are written to `artifacts/flywheel_sync.json`. If the API is not
configured, `--graph-backend auto` keeps using the local graph only.

