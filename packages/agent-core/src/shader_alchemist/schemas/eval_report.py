"""Evidence returned by static and runtime shader evaluation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TimestampMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gpu_execution_time_ms: float | None = Field(default=None, ge=0)
    pipeline_creation_time_ms: float | None = Field(default=None, ge=0)
    sample_count: int = Field(default=0, ge=0)


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass_status: bool
    compilation_success: bool
    validation_errors: list[str] = Field(default_factory=list)
    gpu_execution_time_ms: float | None = Field(default=None, ge=0)
    pipeline_creation_time_ms: float | None = Field(default=None, ge=0)
    memory_out_of_bounds_detected: bool = False
    alignment_warnings: list[str] = Field(default_factory=list)
    numerical_correctness: bool | None = None
    remediation_suggestions: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)