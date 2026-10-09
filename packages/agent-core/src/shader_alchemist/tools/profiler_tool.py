"""A safe subprocess bridge to the Node WebGPU harness."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence

from ..schemas.artifact import ShaderArtifact


class HarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class HarnessResult:
    pipeline_creation_success: bool
    validation_errors: list[str]
    execution_time_ms: float | None
    alignment_warnings: list[str]
    metadata: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "HarnessResult":
        return cls(
            pipeline_creation_success=bool(payload.get("pipeline_creation_success", False)),
            validation_errors=[str(item) for item in payload.get("validation_errors", [])],
            execution_time_ms=(
                float(
                    payload.get(
                        "execution_time_ms",
                        payload.get("gpu_execution_time_ms"),
                    )
                )
                if payload.get("execution_time_ms", payload.get("gpu_execution_time_ms")) is not None
                else None
            ),
            alignment_warnings=[
                str(item) for item in payload.get("alignment_warnings", [])
            ],
            metadata={
                str(key): value
                for key, value in payload.items()
                if key
                not in {
                    "pipeline_creation_success",
                    "validation_errors",
                    "execution_time_ms",
                    "gpu_execution_time_ms",
                    "alignment_warnings",
                }
            },
        )


class WebGPUProfiler:
    def __init__(self, command: Sequence[str], timeout_seconds: float = 30.0) -> None:
        if not command:
            raise ValueError("harness command must not be empty")
        self.command = tuple(command)
        self.timeout_seconds = timeout_seconds

    def profile(self, artifact: ShaderArtifact) -> HarnessResult:
        try:
            process = subprocess.run(
                [*self.command, artifact.to_json()],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HarnessError(
                f"WebGPU harness exceeded {self.timeout_seconds:.1f}s timeout"
            ) from exc
        if process.returncode:
            raise HarnessError(
                f"WebGPU harness exited {process.returncode}: {process.stderr.strip()}"
            )
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise HarnessError("WebGPU harness returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HarnessError("WebGPU harness response must be a JSON object")
        return HarnessResult.from_payload(payload)