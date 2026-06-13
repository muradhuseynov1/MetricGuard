from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _flywheel_command() -> str:
    candidates = ["flywheel.cmd", "flywheel.exe", "flywheel"] if os.name == "nt" else ["flywheel"]
    for candidate in candidates:
        command = shutil.which(candidate)
        if command:
            return command
    raise RuntimeError(
        "Flywheel CLI was not found on PATH. Install/configure it with: "
        "npx --yes @paradigma-inc/flywheel setup --mode cli"
    )


def create_flywheel_node(payload: dict[str, Any]) -> dict[str, Any]:
    temp_path = Path("artifacts/new_node_runtime.json")
    temp_path.parent.mkdir(exist_ok=True)
    temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    command = [
        _flywheel_command(),
        "nodes:commit-new",
        f"--payload_json=@{temp_path}",
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Flywheel CLI command failed: {details}") from exc

    return json.loads(result.stdout)



payload = {
    "local_temp_node_id": "my-new-node-local-001",
    "parent_ids": ["6640fc65-251b-56c1-86fe-dda53903f08f"],
    "staged_payload": {
        "title": "My New Experiment",
        "summary": "Testing a new MetricGuard experiment.",
        "content": "# My New Experiment\n\nThis node was created from Python code.",
        "repo_context": {
            "repo_url": "https://github.com/muradhuseynov1/MetricGuard.git",
            "branch_name": "main",
            "head_commit_sha": "b1d848e0cf5637620031c4b010fb18b6c9746dfd",
            "origin_host": "local-script",
            "updated_by": "riccardo",
            "external_transcript_ref": None,
        },
    },
}

created = create_flywheel_node(payload)
print(created["node"]["node_id"])
