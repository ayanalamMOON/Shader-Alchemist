"""Validated mathematical and host-layout contract for a generated shader."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StructField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    wgsl_type: str = Field(min_length=1)
    offset_bytes: int = Field(ge=0)
    size_bytes: int = Field(gt=0)


class BufferLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group: int = Field(ge=0)
    binding: int = Field(ge=0)
    name: str = Field(min_length=1)
    resource_type: Literal["storage_read", "storage_read_write", "uniform"]
    stride_bytes: int = Field(gt=0)
    fields: list[StructField] = Field(default_factory=list)


class SubgroupRequirements(BaseModel):
    required: bool = False
    min_subgroup_size: int | None = Field(default=None, gt=0)


class MathSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    algorithm_name: str = Field(min_length=1)
    entry_point: str = Field(default="main", min_length=1)
    domain: dict[str, Any] = Field(default_factory=dict)
    workgroup_dimensions: tuple[int, int, int] = (64, 1, 1)
    grid_dispatch_dimensions: tuple[int, int, int] = (1, 1, 1)
    buffer_bindings: list[BufferLayout] = Field(default_factory=list)
    mathematical_formulations: list[str] = Field(default_factory=list)
    required_barriers: list[Literal["workgroupBarrier", "storageBarrier"]] = Field(
        default_factory=list
    )
    subgroup_requirements: SubgroupRequirements = Field(
        default_factory=SubgroupRequirements
    )
    required_features: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    numerical_tolerances: dict[str, float] = Field(
        default_factory=lambda: {"atol": 1e-6, "rtol": 1e-5}
    )

    @model_validator(mode="after")
    def validate_geometry(self) -> "MathSpec":
        if any(value <= 0 for value in self.workgroup_dimensions):
            raise ValueError("workgroup dimensions must be positive")
        if any(value <= 0 for value in self.grid_dispatch_dimensions):
            raise ValueError("dispatch dimensions must be positive")
        count = self.domain.get("element_count")
        if isinstance(count, int) and count > 0 and self.algorithm_name == "vector_add":
            expected = (count + self.workgroup_dimensions[0] - 1) // self.workgroup_dimensions[0]
            if self.grid_dispatch_dimensions[0] != expected:
                raise ValueError("vector_add dispatch does not cover element_count")
        keys = [(item.group, item.binding) for item in self.buffer_bindings]
        if len(keys) != len(set(keys)):
            raise ValueError("buffer_bindings contains duplicate group/binding pairs")
        for buffer in self.buffer_bindings:
            offsets = [field.offset_bytes for field in buffer.fields]
            if len(offsets) != len(set(offsets)):
                raise ValueError(f"duplicate field offsets in {buffer.name!r}")
            if any(offset % 4 for offset in offsets):
                raise ValueError(f"field offsets in {buffer.name!r} must be 4-byte aligned")
        return self