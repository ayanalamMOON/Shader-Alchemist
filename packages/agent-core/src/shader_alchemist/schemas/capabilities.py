"""WebGPU device capability and generation policy contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DeviceCapabilities(BaseModel):
    """Capabilities discovered from a concrete WebGPU adapter/device."""

    model_config = ConfigDict(extra="forbid")

    adapter_name: str = "unknown"
    backend: str = "unknown"
    max_compute_workgroup_size_x: int = Field(default=256, gt=0)
    max_compute_workgroup_size_y: int = Field(default=256, gt=0)
    max_compute_workgroup_size_z: int = Field(default=64, gt=0)
    max_compute_invocations_per_workgroup: int = Field(default=256, gt=0)
    max_storage_buffer_binding_size: int = Field(default=128 * 1024 * 1024, gt=0)
    features: set[str] = Field(default_factory=set)

    def supports_workgroup(self, dimensions: tuple[int, int, int]) -> bool:
        x, y, z = dimensions
        return (
            x <= self.max_compute_workgroup_size_x
            and y <= self.max_compute_workgroup_size_y
            and z <= self.max_compute_workgroup_size_z
            and x * y * z <= self.max_compute_invocations_per_workgroup
        )

    def missing_features(self, required: list[str]) -> list[str]:
        return sorted(set(required).difference(self.features))


class GenerationPolicy(BaseModel):
    """Safety policy applied before a shader is emitted."""

    model_config = ConfigDict(extra="forbid")

    require_bounds_checks: bool = True
    reject_unknown_features: bool = True
    allow_subgroups: bool = False
    max_source_bytes: int = Field(default=512 * 1024, gt=0)
    max_workgroup_invocations: int = Field(default=256, gt=0)
