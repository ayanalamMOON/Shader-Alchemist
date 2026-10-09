"""Shared state for the synthesis and refinement pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .artifact import ShaderArtifact
from .eval_report import EvalReport
from .math_spec import MathSpec


class PipelineStatus(StrEnum):
    PENDING = "pending"
    SPECIFIED = "specified"
    GENERATED = "generated"
    EVALUATING = "evaluating"
    REFINING = "refining"
    PASSED = "passed"
    FAILED = "failed"


class IterationRecord(BaseModel):
    iteration: int = Field(ge=0)
    status: PipelineStatus
    artifact_hash: str | None = None
    report: EvalReport | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShaderAlchemistState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_prompt: str = Field(min_length=1)
    target_budget_ms: float = Field(default=2.0, gt=0)
    current_iteration: int = Field(default=0, ge=0)
    max_iterations: int = Field(default=4, ge=0)
    status: PipelineStatus = PipelineStatus.PENDING
    math_spec: MathSpec | None = None
    shader_artifact: ShaderArtifact | None = None
    eval_history: list[EvalReport] = Field(default_factory=list)
    iteration_history: list[IterationRecord] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def evaluation_passed(self) -> bool:
        return bool(self.eval_history and self.eval_history[-1].pass_status)

    def record_evaluation(self, report: EvalReport) -> None:
        self.eval_history.append(report)
        self.iteration_history.append(
            IterationRecord(
                iteration=self.current_iteration,
                status=PipelineStatus.PASSED if report.pass_status else PipelineStatus.REFINING,
                artifact_hash=self.shader_artifact.source_hash
                if self.shader_artifact
                else None,
                report=report,
            )
        )
        self.feedback = list(report.remediation_suggestions) + list(report.validation_errors)