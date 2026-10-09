"""Run the reproducible Shader Alchemist benchmark manifest.

This runner intentionally uses only the Python standard library. It invokes the installed
agent-core CLI, records generated evidence, and optionally sends each artifact to the real
WebGPU harness through its JSON subprocess boundary.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENT_PROJECT = ROOT / "packages" / "agent-core"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "benchmarks" / "manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark-results")
    parser.add_argument("--harness-command", default="")
    parser.add_argument("--skip-harness", action="store_true")
    return parser.parse_args()


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or not isinstance(value.get("workloads"), list):
        raise ValueError("benchmark manifest must contain a workloads list")
    return value


def invoke_agent(workload: dict[str, Any], output: Path) -> dict[str, Any]:
    command = [
        "uv",
        "run",
        "--project",
        str(AGENT_PROJECT),
        "shader-alchemist",
        "build",
        str(workload["prompt"]),
        "--elements",
        str(workload["elements"]),
        "--workgroup-size",
        str(workload["workgroup_size"]),
        "--output",
        str(output),
    ]
    process = run_command(command, ROOT)
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": process.stdout[-4000:],
        "stderr": process.stderr[-4000:],
    }


def invoke_harness(command_text: str, artifact: dict[str, Any], workload: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    command = shlex.split(command_text, posix=sys.platform != "win32")
    job = {
        "artifact": artifact,
        "warmupIterations": defaults["warmup_iterations"],
        "measuredIterations": defaults["measured_iterations"],
        "maxDispatchInvocations": defaults["max_dispatch_invocations"],
        "maxBufferBytes": defaults["max_buffer_bytes"],
        "targetBudgetMs": defaults["target_budget_ms"],
    }
    process = subprocess.run(
        [*command, json.dumps(job)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {
            "pipeline_creation_success": False,
            "validation_errors": ["harness returned invalid JSON"],
            "stdout": process.stdout[-2000:],
        }
    return {
        "command": command,
        "returncode": process.returncode,
        "result": payload,
        "stderr": process.stderr[-4000:],
        "workload": workload["id"],
    }


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest.resolve())
    defaults = manifest.get("defaults", {})
    args.output.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for workload in manifest["workloads"]:
        workload_id = str(workload["id"])
        output = args.output / workload_id
        output.mkdir(parents=True, exist_ok=True)
        agent = invoke_agent(workload, output)
        result: dict[str, Any] = {
            "id": workload_id,
            "algorithm": workload.get("algorithm"),
            "agent": agent,
        }
        state_path = output / "state.json"
        artifact: dict[str, Any] | None = None
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                candidate = state.get("shader_artifact")
                if isinstance(candidate, dict):
                    artifact = candidate
            except (OSError, json.JSONDecodeError):
                artifact = None
        if agent["returncode"] == 0 and artifact is not None and args.harness_command and not args.skip_harness:
            result["harness"] = invoke_harness(args.harness_command, artifact, workload, defaults)
        elif not args.skip_harness:
            result["harness"] = {"skipped": True, "reason": "agent generation failed or no harness command configured"}
        results.append(result)
        print(f"{workload_id}: {'PASS' if agent['returncode'] == 0 else 'FAIL'}")

    summary = {
        "schema_version": 1,
        "suite": manifest.get("suite"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if all(item["agent"]["returncode"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
