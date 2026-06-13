from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class GraphNode:
    id: str
    kind: str
    title: str
    status: str
    summary: str
    artifacts: list[str]
    parent_id: str | None = None


class LocalGraph:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self.nodes: list[GraphNode] = []

    def add_node(
        self,
        *,
        kind: str,
        title: str,
        status: str,
        summary: str,
        artifacts: list[str],
        parent_id: str | None = None,
    ) -> None:
        node_id = _node_id(kind, title)
        self.nodes.append(
            GraphNode(
                id=node_id,
                kind=kind,
                title=title,
                status=status,
                summary=summary,
                artifacts=artifacts,
                parent_id=parent_id,
            )
        )

    def write(self) -> None:
        self.artifacts_dir.mkdir(exist_ok=True)
        data = {"nodes": [asdict(node) for node in self.nodes]}
        (self.artifacts_dir / "local_graph.json").write_text(
            json.dumps(data, indent=2) + "\n",
            encoding="utf-8",
        )
        lines = ["# MetricGuard Local Evidence Graph", ""]
        for node in self.nodes:
            parent = f" parent={node.parent_id}" if node.parent_id else ""
            lines.append(f"## {node.title}")
            lines.append(f"- id: `{node.id}`{parent}")
            lines.append(f"- kind: `{node.kind}`")
            lines.append(f"- status: `{node.status}`")
            lines.append(f"- summary: {node.summary}")
            if node.artifacts:
                lines.append(f"- artifacts: {', '.join(f'`{item}`' for item in node.artifacts)}")
            lines.append("")
        (self.artifacts_dir / "local_graph.md").write_text("\n".join(lines), encoding="utf-8")


@dataclass(frozen=True)
class FlywheelConfig:
    base_url: str
    api_token: str
    project_id: str
    nodes_path: str = "/nodes"
    edges_path: str = "/edges"
    timeout_seconds: int = 20

    @classmethod
    def from_env(cls) -> "FlywheelConfig | None":
        _load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        base_url = os.environ.get("FLYWHEEL_API_BASE_URL")
        api_token = os.environ.get("FLYWHEEL_API_TOKEN")
        project_id = os.environ.get("FLYWHEEL_PROJECT_ID")
        if not (base_url and api_token and project_id):
            return None
        return cls(
            base_url=base_url.rstrip("/"),
            api_token=api_token,
            project_id=project_id,
            nodes_path=os.environ.get("FLYWHEEL_NODES_PATH", "/nodes"),
            edges_path=os.environ.get("FLYWHEEL_EDGES_PATH", "/edges"),
            timeout_seconds=int(os.environ.get("FLYWHEEL_TIMEOUT_SECONDS", "20")),
        )


class FlywheelGraph(LocalGraph):
    """Local graph mirror plus best-effort live Flywheel sync."""

    def __init__(self, artifacts_dir: Path, config: FlywheelConfig) -> None:
        super().__init__(artifacts_dir)
        self.config = config
        self.sync_events: list[dict[str, Any]] = []

    def write(self) -> None:
        super().write()
        for node in self.nodes:
            self._sync_node(node)
            if node.parent_id:
                self._sync_edge(node.parent_id, node.id)
        self._write_sync_report()

    def _sync_node(self, node: GraphNode) -> None:
        payload = {
            "project_id": self.config.project_id,
            "external_id": node.id,
            "kind": node.kind,
            "title": node.title,
            "status": node.status,
            "summary": node.summary,
            "artifacts": node.artifacts,
            "parent_id": node.parent_id,
            "metadata": {"source": "MetricGuard", "graph": "claim-audit-evidence-verdict"},
        }
        self._post("node", self.config.nodes_path, payload)

    def _sync_edge(self, source_id: str, target_id: str) -> None:
        payload = {
            "project_id": self.config.project_id,
            "source_external_id": source_id,
            "target_external_id": target_id,
            "relationship": "evidence_transition",
            "metadata": {"source": "MetricGuard"},
        }
        self._post("edge", self.config.edges_path, payload)

    def _post(self, item_type: str, path_template: str, payload: dict[str, Any]) -> None:
        path = path_template.format(project_id=self.config.project_id).lstrip("/")
        url = f"{self.config.base_url}/{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                self.sync_events.append(
                    {
                        "type": item_type,
                        "id": payload.get("external_id") or payload.get("target_external_id"),
                        "url": url,
                        "ok": 200 <= response.status < 300,
                        "status": response.status,
                        "response": _trim(response_body),
                    }
                )
        except urllib.error.HTTPError as exc:
            self.sync_events.append(
                {
                    "type": item_type,
                    "id": payload.get("external_id") or payload.get("target_external_id"),
                    "url": url,
                    "ok": False,
                    "status": exc.code,
                    "response": _trim(exc.read().decode("utf-8", errors="replace")),
                }
            )
        except urllib.error.URLError as exc:
            self.sync_events.append(
                {
                    "type": item_type,
                    "id": payload.get("external_id") or payload.get("target_external_id"),
                    "url": url,
                    "ok": False,
                    "status": None,
                    "response": str(exc.reason),
                }
            )

    def _write_sync_report(self) -> None:
        report = {
            "backend": "flywheel",
            "base_url": self.config.base_url,
            "project_id": self.config.project_id,
            "nodes_path": self.config.nodes_path,
            "edges_path": self.config.edges_path,
            "ok": bool(self.sync_events) and all(event["ok"] for event in self.sync_events),
            "events": self.sync_events,
        }
        (self.artifacts_dir / "flywheel_sync.json").write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )


def create_graph(artifacts_dir: Path, backend: str = "auto") -> LocalGraph:
    if backend not in {"auto", "local", "flywheel"}:
        raise ValueError(f"unknown graph backend: {backend}")
    config = FlywheelConfig.from_env()
    if backend == "local":
        return LocalGraph(artifacts_dir)
    if config:
        return FlywheelGraph(artifacts_dir, config)
    if backend == "flywheel":
        missing = ", ".join(
            name
            for name in ("FLYWHEEL_API_BASE_URL", "FLYWHEEL_API_TOKEN", "FLYWHEEL_PROJECT_ID")
            if not os.environ.get(name)
        )
        raise RuntimeError(f"Flywheel backend requested but missing environment variables: {missing}")
    return LocalGraph(artifacts_dir)


def _node_id(kind: str, title: str) -> str:
    lower = title.lower()
    if kind == "baseline":
        return "baseline"
    if kind == "proposal" and "repair" in lower:
        return "proposal-repair"
    if kind == "proposal":
        return "proposal-cheat"
    if kind == "audit" and "accepted" in lower:
        return "audit-accepted"
    if kind == "audit" and "rejected" in lower:
        return "audit-rejected"
    return f"{kind}-{len(title)}"


def _trim(value: str, limit: int = 1000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[trimmed]"



def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
