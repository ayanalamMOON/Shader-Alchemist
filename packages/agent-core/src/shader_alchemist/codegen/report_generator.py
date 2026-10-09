"""Human-readable diagnostic report generation."""

from __future__ import annotations

from datetime import datetime, timezone

from ..schemas.state import ShaderAlchemistState


def generate_markdown_report(state: ShaderAlchemistState) -> str:
    latest = state.eval_history[-1] if state.eval_history else None
    lines = [
        "# Shader Alchemist Evaluation Report",
        "",
        f"- Session: `{state.session_id}`",
        f"- Status: **{state.status.value}**",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Iterations: {state.current_iteration + 1}",
        "",
        "## Request",
        "",
        state.user_prompt,
        "",
        "## Specification",
        "",
    ]
    if state.math_spec:
        lines.extend(
            [
                f"- Algorithm: `{state.math_spec.algorithm_name}`",
                f"- Entry point: `{state.math_spec.entry_point}`",
                f"- Workgroup: `{state.math_spec.workgroup_dimensions}`",
                f"- Dispatch: `{state.math_spec.grid_dispatch_dimensions}`",
                f"- Required features: `{state.math_spec.required_features or 'none'}`",
            ]
        )
    if latest:
        lines.extend(
            [
                "",
                "## Evaluation",
                "",
                f"- Passed: `{latest.pass_status}`",
                f"- Compilation checks: `{latest.compilation_success}`",
                f"- GPU time: `{latest.gpu_execution_time_ms or 'not measured'} ms`",
                f"- Out-of-bounds evidence: `{latest.memory_out_of_bounds_detected}`",
            ]
        )
        if latest.validation_errors:
            lines.extend(["", "### Validation errors", ""])
            lines.extend(f"- {error}" for error in latest.validation_errors)
        if latest.remediation_suggestions:
            lines.extend(["", "### Recommendations", ""])
            lines.extend(f"- {item}" for item in latest.remediation_suggestions)
    if state.shader_artifact:
        lines.extend(
            [
                "",
                "## Artifact",
                "",
                f"- Source hash: `{state.shader_artifact.source_hash}`",
                f"- WGSL length: `{len(state.shader_artifact.wgsl_code)}` characters",
            ]
        )
    return "\n".join(lines) + "\n"