from __future__ import annotations

import json
import os
import shutil
import subprocess
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
        node_id: str | None = None,
    ) -> None:
        node_id = node_id or _node_id(kind, title)
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
    root_node_id: str | None = None
    parent_node_id: str | None = None
    updated_by: str = "MetricGuard"
    repo_url: str | None = None
    branch_name: str | None = None
    head_commit_sha: str | None = None
    origin_host: str = "local-script"
    external_transcript_ref: str | None = None

    @classmethod
    def from_env(cls, parent_node_id: str | None = None) -> "FlywheelConfig":
        _load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        return cls(
            root_node_id=os.environ.get("FLYWHEEL_ROOT_NODE_ID"),
            parent_node_id=parent_node_id or os.environ.get("FLYWHEEL_PARENT_NODE_ID"),
            updated_by=os.environ.get("FLYWHEEL_UPDATED_BY", "MetricGuard"),
            repo_url=os.environ.get("FLYWHEEL_REPO_URL"),
            branch_name=os.environ.get("FLYWHEEL_BRANCH_NAME"),
            head_commit_sha=os.environ.get("FLYWHEEL_HEAD_COMMIT_SHA"),
            origin_host=os.environ.get("FLYWHEEL_ORIGIN_HOST", "local-script"),
            external_transcript_ref=os.environ.get("FLYWHEEL_EXTERNAL_TRANSCRIPT_REF"),
        )


class FlywheelGraph(LocalGraph):
    """Local graph mirror plus best-effort Flywheel CLI node creation."""

    def __init__(
        self,
        artifacts_dir: Path,
        config: FlywheelConfig,
        create_node: Any | None = None,
    ) -> None:
        super().__init__(artifacts_dir)
        self.config = config
        self._create_node = create_node or self._create_node_with_cli
        self.sync_events: list[dict[str, Any]] = []
        self.local_to_flywheel: dict[str, str] = {}

    def write(self) -> None:
        super().write()
        for node in self.nodes:
            self._sync_node(node)
        self._write_sync_report()

    def _sync_node(self, node: GraphNode) -> None:
        try:
            parent_ids = self._parent_ids_for(node)
        except RuntimeError as exc:
            self.sync_events.append(
                {
                    "type": "node",
                    "local_id": node.id,
                    "ok": False,
                    "status": None,
                    "response": str(exc),
                    "parent_ids": [],
                }
            )
            return

        payload = self._node_payload(node, parent_ids)
        try:
            response = self._create_node(payload)
            flywheel_node = response.get("node", {})
            flywheel_node_id = flywheel_node.get("node_id")
            if not flywheel_node_id:
                raise RuntimeError(f"Flywheel response did not include node.node_id: {response}")
            self.local_to_flywheel[node.id] = str(flywheel_node_id)
            self.sync_events.append(
                {
                    "type": "node",
                    "local_id": node.id,
                    "flywheel_node_id": str(flywheel_node_id),
                    "slug_name": flywheel_node.get("slug_name"),
                    "ok": True,
                    "status": "created",
                    "response": _trim(json.dumps(response)),
                    "parent_ids": parent_ids,
                }
            )
            self._upload_node_artifacts(str(flywheel_node_id), node)
        except Exception as exc:
            self.sync_events.append(
                {
                    "type": "node",
                    "local_id": node.id,
                    "ok": False,
                    "status": None,
                    "response": _trim(str(exc)),
                    "parent_ids": parent_ids,
                }
            )

    def _parent_ids_for(self, node: GraphNode) -> list[str]:
        if node.parent_id:
            parent_node_id = self.local_to_flywheel.get(node.parent_id)
            if not parent_node_id:
                raise RuntimeError(
                    f"cannot create {node.id}: parent {node.parent_id} was not synced"
                )
            return [parent_node_id]
        if self.config.parent_node_id:
            return [self.config.parent_node_id]
        if self.config.root_node_id:
            return [self.config.root_node_id]
        return []

    def _node_payload(self, node: GraphNode, parent_ids: list[str]) -> dict[str, Any]:
        content_lines = [
            f"# {node.title}",
            "",
            f"- Local node id: `{node.id}`",
            f"- Kind: `{node.kind}`",
            f"- Status: `{node.status}`",
            f"- Summary: {node.summary}",
        ]
        if node.artifacts:
            content_lines.extend(
                [
                    "",
                    "## Evidence Artifacts",
                    *[f"- `{artifact}`" for artifact in node.artifacts],
                ]
            )
        llm_explanation = self._read_llm_judge_artifact(node)
        if llm_explanation:
            content_lines.extend(["", llm_explanation])
        return {
            "local_temp_node_id": f"metricguard-{node.id}",
            "parent_ids": parent_ids,
            "staged_payload": {
                "title": node.title,
                "summary": node.summary,
                "content": "\n".join(content_lines),
                "repo_context": {
                    "repo_url": self.config.repo_url,
                    "branch_name": self.config.branch_name,
                    "head_commit_sha": self.config.head_commit_sha,
                    "origin_host": self.config.origin_host,
                    "updated_by": self.config.updated_by,
                    "external_transcript_ref": self.config.external_transcript_ref,
                },
            },
        }

    def _read_llm_judge_artifact(self, node: GraphNode) -> str | None:
        for artifact in node.artifacts:
            normalized = artifact.replace("\\", "/")
            if normalized.endswith("llm_judge.md"):
                path = self.artifacts_dir / Path(normalized)
                if path.exists():
                    return path.read_text(encoding="utf-8").strip()
        return None

    def _create_node_with_cli(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload_dir = self.artifacts_dir / "flywheel_payloads"
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_path = payload_dir / f"{payload['local_temp_node_id']}.json"
        payload_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        command = [
            *_flywheel_command(),
            "nodes:commit-new",
            f"--payload_json=@{payload_path}",
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RuntimeError(f"Flywheel CLI command failed: {details}") from exc
        return json.loads(result.stdout)

    def _upload_node_artifacts(self, flywheel_node_id: str, node: GraphNode) -> None:
        items: list[dict[str, str]] = []
        for artifact in node.artifacts:
            path = self.artifacts_dir / Path(artifact.replace("\\", "/"))
            if not path.exists():
                self.sync_events.append(
                    {
                        "type": "artifact",
                        "local_id": node.id,
                        "flywheel_node_id": flywheel_node_id,
                        "artifact": artifact,
                        "ok": False,
                        "status": "missing",
                        "response": "local artifact path does not exist",
                    }
                )
                continue
            items.append(
                {
                    "local_path": str(path),
                    "artifact_type": _artifact_type(path),
                    "title": _artifact_title(artifact),
                }
            )
        if not items:
            return

        items_dir = self.artifacts_dir / "flywheel_payloads"
        items_dir.mkdir(parents=True, exist_ok=True)
        items_path = items_dir / f"metricguard-{node.id}-artifacts.json"
        items_path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")

        revision = self._get_node_revision(flywheel_node_id)
        command = [
            *_flywheel_command(),
            "artifacts:upload",
            "--node_id",
            flywheel_node_id,
            "--expected_revision",
            str(revision),
            f"--items=@{items_path}",
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RuntimeError(f"Flywheel artifact upload failed for {node.id}: {details}") from exc
        self.sync_events.append(
            {
                "type": "artifacts",
                "local_id": node.id,
                "flywheel_node_id": flywheel_node_id,
                "count": len(items),
                "items_file": str(items_path),
                "ok": True,
                "status": "uploaded",
                "response": _trim(result.stdout),
            }
        )

    def _get_node_revision(self, flywheel_node_id: str) -> int:
        command = [
            *_flywheel_command(),
            "nodes:get",
            "--node_id",
            flywheel_node_id,
            "--format",
            "json",
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RuntimeError(f"Flywheel nodes:get failed for {flywheel_node_id}: {details}") from exc
        payload = json.loads(result.stdout)
        return int(payload["revision"])

    def _write_sync_report(self) -> None:
        report = {
            "backend": "flywheel-cli",
            "root_node_id": self.config.root_node_id,
            "parent_node_id": self.config.parent_node_id,
            "ok": bool(self.sync_events) and all(event["ok"] for event in self.sync_events),
            "local_to_flywheel": self.local_to_flywheel,
            "events": self.sync_events,
        }
        (self.artifacts_dir / "flywheel_sync.json").write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )


def create_graph(artifacts_dir: Path, backend: str = "auto", parent_node_id: str | None = None) -> LocalGraph:
    if backend not in {"auto", "local", "flywheel", "flywheel-cli"}:
        raise ValueError(f"unknown graph backend: {backend}")
    config = FlywheelConfig.from_env(parent_node_id=parent_node_id)
    if backend == "local":
        return LocalGraph(artifacts_dir)
    if backend in {"flywheel", "flywheel-cli"}:
        return FlywheelGraph(artifacts_dir, config)
    if config.root_node_id:
        return FlywheelGraph(artifacts_dir, config)
    return LocalGraph(artifacts_dir)


def _node_id(kind: str, title: str) -> str:
    lower = title.lower()
    if kind == "baseline":
        return "baseline"
    if kind == "proposal" and lower.startswith("benchmark case:"):
        return "proposal-benchmark-" + _slug(lower.removeprefix("benchmark case:").strip())
    if kind == "audit" and lower.startswith("benchmark audit:"):
        parts = lower.removeprefix("benchmark audit:").strip().split()
        case_id = " ".join(parts[:-1]) if len(parts) > 1 else "case"
        return "audit-benchmark-" + _slug(case_id)
    if kind == "proposal" and lower.startswith("scifact case:"):
        return "proposal-scifact-" + _slug(lower.removeprefix("scifact case:").strip())
    if kind == "audit" and lower.startswith("scifact audit:"):
        parts = lower.removeprefix("scifact audit:").strip().split()
        case_id = " ".join(parts[:-1]) if len(parts) > 1 else "case"
        return "audit-scifact-" + _slug(case_id)
    if kind == "proposal" and "fabricated citations" in lower:
        return "proposal-citation-fake"
    if kind == "proposal" and "verified citation" in lower:
        return "proposal-citation-repair"
    if kind == "audit" and "citation" in lower and "accepted" in lower:
        return "audit-citation-accepted"
    if kind == "audit" and "citation" in lower and "rejected" in lower:
        return "audit-citation-rejected"
    if kind == "proposal" and "repair" in lower:
        return "proposal-repair"
    if kind == "proposal":
        return "proposal-cheat"
    if kind == "audit" and "accepted" in lower:
        return "audit-accepted"
    if kind == "audit" and "rejected" in lower:
        return "audit-rejected"
    return f"{kind}-{len(title)}"


def _slug(value: str) -> str:
    normalized = []
    for char in value.lower():
        normalized.append(char if char.isalnum() else "-")
    slug = "".join(normalized).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "node"


def _trim(value: str, limit: int = 1000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[trimmed]"


def _artifact_type(path: Path) -> str:
    if path.suffix.lower() == ".json":
        return "json"
    return "text"


def _artifact_title(path: str) -> str:
    return Path(path).name.replace("_", " ").replace("-", " ")


def _flywheel_command() -> list[str]:
    flywheel_candidates = ["flywheel.cmd", "flywheel.exe", "flywheel"] if os.name == "nt" else ["flywheel"]
    for candidate in flywheel_candidates:
        command = shutil.which(candidate)
        if command:
            return [command]
    npx_candidates = ["npx.cmd", "npx"] if os.name == "nt" else ["npx"]
    for candidate in npx_candidates:
        command = shutil.which(candidate)
        if command:
            return [command, "--yes", "@paradigma-inc/flywheel"]
    raise RuntimeError(
        "Flywheel CLI was not found on PATH. Install/configure it with: "
        "npx --yes @paradigma-inc/flywheel setup --mode cli"
    )


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
