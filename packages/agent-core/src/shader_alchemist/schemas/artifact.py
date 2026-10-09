"""Generated shader and pipeline metadata."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .math_spec import MathSpec


class BindingDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group: int = Field(ge=0)
    binding: int = Field(ge=0)
    name: str = Field(min_length=1)
    resource_type: Literal["storage_read", "storage_read_write", "uniform"] 
    visibility: list[Literal["compute", "vertex", "fragment"]] = Field(
        default_factory=lambda: ["compute"]
    )
    min_binding_size: int | None = Field(default=None, ge=0)

    def to_webgpu_entry(self) -> dict[str, object]:
        if self.resource_type == "uniform":
            buffer_type = "uniform"
        elif self.resource_type == "storage_read":
            buffer_type = "read-only-storage"
        else:
            buffer_type = "storage"
        return {
            "binding": self.binding,
            "visibility": self.visibility,
            "buffer": {
                "type": buffer_type,
                **(
                    {"minBindingSize": self.min_binding_size}
                    if self.min_binding_size is not None
                    else {}
                ),
            },
        }


class ShaderArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    wgsl_code: str = Field(min_length=1)
    entry_point: str = Field(min_length=1)
    bind_group_layouts: list[BindingDescription] = Field(default_factory=list)
    dispatch_size: tuple[int, int, int]
    required_features: list[str] = Field(default_factory=list)
    math_spec: MathSpec | None = None
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_artifact(self) -> "ShaderArtifact":
        if len(self.dispatch_size) != 3 or any(
            dimension <= 0 for dimension in self.dispatch_size
        ):
            raise ValueError("dispatch_size must contain three positive dimensions")
        keys = [(item.group, item.binding) for item in self.bind_group_layouts]
        if len(keys) != len(set(keys)):
            raise ValueError("bind_group_layouts contains duplicate bindings")
        if self.math_spec and self.entry_point != self.math_spec.entry_point:
            raise ValueError("artifact entry point differs from MathSpec")
        return self

    @property
    def source_hash(self) -> str:
        import hashlib

        return hashlib.sha256(self.wgsl_code.encode("utf-8")).hexdigest()

    def bind_group_layout_entries(self, group: int = 0) -> list[dict[str, Any]]:
        return [
            binding.to_webgpu_entry()
            for binding in self.bind_group_layouts
            if binding.group == group
        ]

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)