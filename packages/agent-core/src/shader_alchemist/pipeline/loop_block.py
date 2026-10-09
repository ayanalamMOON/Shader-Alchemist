"""Refinement-loop stopping and feedback policy."""

from __future__ import annotations

from ..schemas.eval_report import EvalReport


class RefinementLoop:
    def __init__(self, max_iterations: int = 4, target_budget_ms: float = 2.0) -> None:
        if max_iterations < 0:
            raise ValueError("max_iterations must not be negative")
        if target_budget_ms <= 0:
            raise ValueError("target_budget_ms must be positive")
        self.max_iterations = max_iterations
        self.target_budget_ms = target_budget_ms

    def should_stop(self, report: EvalReport, iteration: int) -> bool:
        return report.pass_status or iteration >= self.max_iterations

    def feedback_for(self, report: EvalReport) -> list[str]:
        feedback = list(report.validation_errors)
        feedback.extend(report.remediation_suggestions)
        if report.memory_out_of_bounds_detected:
            feedback.append("Add a bounds check before every storage-array access.")
        return list(dict.fromkeys(feedback))

    def next_iteration(self, report: EvalReport, iteration: int) -> int | None:
        if self.should_stop(report, iteration):
            return None
        return iteration + 1