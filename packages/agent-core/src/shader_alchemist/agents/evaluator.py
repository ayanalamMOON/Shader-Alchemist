"""Static and optional runtime evaluation for ShaderArtifact instances."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Sequence

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..schemas.artifact import ShaderArtifact
from ..schemas.eval_report import EvalReport


class PerformanceEvaluator:
    def __init__(
        self,
        prompt_directory: str | Path | None = None,
        harness_command: Sequence[str] | None = None,
    ) -> None:
        directory = Path(prompt_directory or Path(__file__).with_name("prompts"))
        self._templates = Environment(
            loader=FileSystemLoader(directory), undefined=StrictUndefined, autoescape=False
        )
        self.harness_command = tuple(harness_command or ())

    def render_prompt(self, artifact: ShaderArtifact, target_budget_ms: float = 2.0) -> str:
        return self._templates.get_template("evaluator.jinja2").render(
            artifact=artifact.model_dump_json(indent=2), target_budget_ms=target_budget_ms
        )

    def evaluate(
        self,
        artifact: ShaderArtifact,
        *,
        target_budget_ms: float = 2.0,
        run_harness: bool = False,
    ) -> EvalReport:
        errors: list[str] = []
        code = artifact.wgsl_code
        if "@compute" not in code:
            errors.append("shader has no compute entry point")
        if f"fn {artifact.entry_point}" not in code:
            errors.append(f"entry point {artifact.entry_point!r} is not defined")
        if "@workgroup_size" not in code:
            errors.append("shader does not declare workgroup size")
        if re.search(r"arrayLength\s*\(", code) and "if (" not in code:
            errors.append("runtime-sized storage access has no visible bounds guard")
        if artifact.math_spec and artifact.dispatch_size != artifact.math_spec.grid_dispatch_dimensions:
            errors.append("artifact dispatch differs from MathSpec dispatch")
        out_of_bounds = bool(re.search(r"global_invocation_id", code)) and not bool(
            re.search(r"\bif\s*\([^)]*(?:>=|<)", code)
        )
        if out_of_bounds:
            errors.append("global invocation index is not guarded by a comparison")

        runtime_ms: float | None = None
        metadata: dict[str, Any] = {"mode": "static"}
        if run_harness and self.harness_command:
            completed = subprocess.run(
                [*self.harness_command, json.dumps(artifact.model_dump())],
                capture_output=True, text=True, timeout=30, check=False
            )
            if completed.returncode:
                errors.append(f"harness exited with status {completed.returncode}")
                metadata["harness_stderr"] = completed.stderr[-1000:]
            else:
                try:
                    result = json.loads(completed.stdout)
                    runtime_ms = float(result["gpu_execution_time_ms"])
                    metadata.update(
                        {str(k): v for k, v in result.items() if k != "gpu_execution_time_ms"}
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"harness returned invalid JSON: {exc}")
        suggestions = []
        if errors:
            suggestions.append("Fix validation errors before attempting performance optimization.")
        if runtime_ms is not None and runtime_ms > target_budget_ms:
            suggestions.append("Reduce dispatch work or memory traffic and re-run the benchmark.")
        return EvalReport(
            pass_status=not errors and (runtime_ms is None or runtime_ms <= target_budget_ms),
            compilation_success=not errors,
            validation_errors=errors,
            gpu_execution_time_ms=runtime_ms,
            memory_out_of_bounds_detected=out_of_bounds,
            remediation_suggestions=suggestions,
            metadata=metadata,
        )


def evaluate_shader(
    artifact: ShaderArtifact, *, target_budget_ms: float = 2.0, run_harness: bool = False
) -> EvalReport:
    return PerformanceEvaluator().evaluate(
        artifact, target_budget_ms=target_budget_ms, run_harness=run_harness
    )