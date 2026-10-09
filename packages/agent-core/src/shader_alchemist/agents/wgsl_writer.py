"""Production-oriented WGSL generation.

The writer deliberately separates policy validation, kernel selection, emission, and artifact
construction. This makes generated source deterministic and keeps model-generated MathSpecs from
silently turning into unsafe host-facing shader code.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..schemas.artifact import BindingDescription, ShaderArtifact
from ..schemas.capabilities import DeviceCapabilities, GenerationPolicy
from ..schemas.math_spec import MathSpec


class ShaderGenerationError(ValueError):
    """Raised when a MathSpec cannot be emitted safely."""


class UnsupportedKernelError(ShaderGenerationError):
    """Raised when no registered deterministic emitter supports an algorithm."""


@dataclass(frozen=True)
class GenerationDiagnostic:
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class GeneratedSource:
    source: str
    diagnostics: tuple[GenerationDiagnostic, ...] = ()


KernelEmitter = Callable[[MathSpec], GeneratedSource]


VECTOR_ADD: Final[str] = """struct FloatBuffer {{
  values: array<f32>,
}};

@group(0) @binding(0)
var<storage, read> lhs: FloatBuffer;
@group(0) @binding(1)
var<storage, read> rhs: FloatBuffer;
@group(0) @binding(2)
var<storage, read_write> output_buffer: FloatBuffer;

@compute @workgroup_size({x}, {y}, {z})
fn vector_add(@builtin(global_invocation_id) gid: vec3<u32>) {{
  let index = gid.x;
  let output_length = arrayLength(&output_buffer.values);
  if (index >= output_length || index >= arrayLength(&lhs.values) ||
      index >= arrayLength(&rhs.values)) {{
    return;
  }}
  output_buffer.values[index] = lhs.values[index] + rhs.values[index];
}}
"""

SCALAR_MULTIPLY: Final[str] = """struct FloatBuffer {{
  values: array<f32>,
}};

struct ScalarUniform {{
  value: f32,
}};

@group(0) @binding(0)
var<storage, read> input_buffer: FloatBuffer;
@group(0) @binding(1)
var<uniform> scalar: ScalarUniform;
@group(0) @binding(2)
var<storage, read_write> output_buffer: FloatBuffer;

@compute @workgroup_size({x}, {y}, {z})
fn scalar_multiply(@builtin(global_invocation_id) gid: vec3<u32>) {{
  let index = gid.x;
  let output_length = arrayLength(&output_buffer.values);
  if (index >= output_length || index >= arrayLength(&input_buffer.values)) {{
    return;
  }}
  output_buffer.values[index] = input_buffer.values[index] * scalar.value;
}}
"""

SAXPY: Final[str] = """struct FloatBuffer {{
  values: array<f32>,
}};

struct ScalarUniform {{
  value: f32,
}};

@group(0) @binding(0)
var<storage, read> x_buffer: FloatBuffer;
@group(0) @binding(1)
var<storage, read> y_buffer: FloatBuffer;
@group(0) @binding(2)
var<uniform> alpha: ScalarUniform;
@group(0) @binding(3)
var<storage, read_write> output_buffer: FloatBuffer;

@compute @workgroup_size({x}, {y}, {z})
fn saxpy(@builtin(global_invocation_id) gid: vec3<u32>) {{
  let index = gid.x;
  let output_length = arrayLength(&output_buffer.values);
  if (index >= output_length || index >= arrayLength(&x_buffer.values) ||
      index >= arrayLength(&y_buffer.values)) {{
    return;
  }}
  output_buffer.values[index] = alpha.value * x_buffer.values[index] + y_buffer.values[index];
}}
"""

COPY: Final[str] = """struct FloatBuffer {{
  values: array<f32>,
}};

@group(0) @binding(0)
var<storage, read> input_buffer: FloatBuffer;
@group(0) @binding(1)
var<storage, read_write> output_buffer: FloatBuffer;

@compute @workgroup_size({x}, {y}, {z})
fn copy_buffer(@builtin(global_invocation_id) gid: vec3<u32>) {{
  let index = gid.x;
  let output_length = arrayLength(&output_buffer.values);
  if (index >= output_length || index >= arrayLength(&input_buffer.values)) {{
    return;
  }}
  output_buffer.values[index] = input_buffer.values[index];
}}
"""


def _format(source: str, spec: MathSpec) -> str:
    x, y, z = spec.workgroup_dimensions
    return source.format(x=x, y=y, z=z)


def _emit_vector_add(spec: MathSpec) -> GeneratedSource:
    return GeneratedSource(_format(VECTOR_ADD, spec))


def _emit_scalar_multiply(spec: MathSpec) -> GeneratedSource:
    return GeneratedSource(_format(SCALAR_MULTIPLY, spec))


def _emit_saxpy(spec: MathSpec) -> GeneratedSource:
    return GeneratedSource(_format(SAXPY, spec))


def _emit_copy(spec: MathSpec) -> GeneratedSource:
    return GeneratedSource(_format(COPY, spec))


DEFAULT_EMITTERS: dict[str, KernelEmitter] = {
    "vector_add": _emit_vector_add,
    "scalar_multiply": _emit_scalar_multiply,
    "saxpy": _emit_saxpy,
    "copy": _emit_copy,
    "copy_buffer": _emit_copy,
}


class WGSLWriter:
    """Compile a validated MathSpec into a host-bindable ShaderArtifact."""

    def __init__(
        self,
        prompt_directory: str | Path | None = None,
        *,
        capabilities: DeviceCapabilities | None = None,
        policy: GenerationPolicy | None = None,
        emitters: dict[str, KernelEmitter] | None = None,
    ) -> None:
        directory = Path(prompt_directory or Path(__file__).with_name("prompts"))
        self._templates = Environment(
            loader=FileSystemLoader(directory),
            undefined=StrictUndefined,
            autoescape=False,
        )
        self.capabilities = capabilities or DeviceCapabilities()
        self.policy = policy or GenerationPolicy()
        self.emitters = dict(DEFAULT_EMITTERS)
        self.emitters.update(emitters or {})

    def render_prompt(self, math_spec: MathSpec, feedback: list[str] | None = None) -> str:
        return self._templates.get_template("wgsl_writer.jinja2").render(
            math_spec=math_spec.model_dump_json(indent=2),
            feedback=json.dumps(feedback or [], sort_keys=True),
        )

    def register(self, algorithm_name: str, emitter: KernelEmitter) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", algorithm_name):
            raise ValueError("algorithm_name must be a WGSL-compatible identifier")
        self.emitters[algorithm_name] = emitter

    def diagnose(self, spec: MathSpec) -> list[GenerationDiagnostic]:
        diagnostics: list[GenerationDiagnostic] = []
        if not self.capabilities.supports_workgroup(spec.workgroup_dimensions):
            diagnostics.append(
                GenerationDiagnostic(
                    "workgroup-unsupported",
                    f"workgroup {spec.workgroup_dimensions} exceeds device limits",
                )
            )
        missing = self.capabilities.missing_features(spec.required_features)
        if missing:
            diagnostics.append(
                GenerationDiagnostic(
                    "feature-unavailable",
                    f"required WebGPU features unavailable: {', '.join(missing)}",
                )
            )
        if not self.policy.allow_subgroups and spec.subgroup_requirements.required:
            diagnostics.append(
                GenerationDiagnostic(
                    "subgroups-disabled",
                    "MathSpec requires subgroups but generation policy disables them",
                )
            )
        for binding in spec.buffer_bindings:
            if binding.resource_type == "uniform" and binding.stride_bytes % 16:
                diagnostics.append(
                    GenerationDiagnostic(
                        "uniform-alignment",
                        f"uniform binding {binding.name!r} stride must be 16-byte aligned",
                    )
                )
        return diagnostics

    def _validate_emitted_source(self, source: str, spec: MathSpec) -> None:
        if len(source.encode("utf-8")) > self.policy.max_source_bytes:
            raise ShaderGenerationError("generated WGSL exceeds max_source_bytes")
        if source.count("{") != source.count("}"):
            raise ShaderGenerationError("generated WGSL contains unbalanced braces")
        if "@compute" not in source or f"fn {spec.entry_point}" not in source:
            raise ShaderGenerationError("generated WGSL does not expose the requested entry point")
        if self.policy.require_bounds_checks and "global_invocation_id" in source:
            if not re.search(r"\bif\s*\([^)]*(?:>=|<)", source, flags=re.DOTALL):
                raise ShaderGenerationError("generated dispatch has no bounds guard")

    def validate_artifact(self, artifact: ShaderArtifact) -> list[GenerationDiagnostic]:
        """Validate model-produced source without replacing it with a local emitter."""
        if artifact.math_spec is None:
            raise ShaderGenerationError("artifact must carry its MathSpec before validation")
        diagnostics = self.diagnose(artifact.math_spec)
        errors = [item for item in diagnostics if item.severity == "error"]
        if errors:
            return errors
        try:
            self._validate_emitted_source(artifact.wgsl_code, artifact.math_spec)
        except ShaderGenerationError as exc:
            return [GenerationDiagnostic("source-invalid", str(exc))]
        if artifact.entry_point != artifact.math_spec.entry_point:
            return [
                GenerationDiagnostic(
                    "entry-point-mismatch",
                    "artifact entry point differs from MathSpec",
                )
            ]
        expected = {(item.group, item.binding) for item in artifact.math_spec.buffer_bindings}
        actual = {(item.group, item.binding) for item in artifact.bind_group_layouts}
        if expected != actual:
            return [
                GenerationDiagnostic(
                    "binding-mismatch",
                    f"artifact bindings {sorted(actual)} differ from MathSpec {sorted(expected)}",
                )
            ]
        return []

    def write(
        self,
        math_spec: MathSpec,
        feedback: list[str] | None = None,
    ) -> ShaderArtifact:
        del feedback  # Feedback is consumed by the upstream model; emitters remain deterministic.
        diagnostics = self.diagnose(math_spec)
        errors = [item for item in diagnostics if item.severity == "error"]
        if errors:
            detail = "; ".join(f"{item.code}: {item.message}" for item in errors)
            raise ShaderGenerationError(detail)
        emitter = self.emitters.get(math_spec.algorithm_name)
        if emitter is None:
            supported = ", ".join(sorted(self.emitters))
            raise UnsupportedKernelError(
                f"unsupported algorithm {math_spec.algorithm_name!r}; supported kernels: {supported}"
            )
        generated = emitter(math_spec)
        self._validate_emitted_source(generated.source, math_spec)
        layouts = [
            BindingDescription(
                group=item.group,
                binding=item.binding,
                name=item.name,
                resource_type=item.resource_type,
                min_binding_size=item.stride_bytes,
            )
            for item in math_spec.buffer_bindings
        ]
        source_hash = hashlib.sha256(generated.source.encode("utf-8")).hexdigest()
        return ShaderArtifact(
            wgsl_code=generated.source,
            entry_point=math_spec.entry_point,
            bind_group_layouts=layouts,
            dispatch_size=math_spec.grid_dispatch_dimensions,
            required_features=math_spec.required_features,
            math_spec=math_spec,
            metadata={
                "generator": "deterministic-wgsl-writer",
                "source_hash": source_hash,
                "kernel": math_spec.algorithm_name,
                "diagnostics": json.dumps(
                    [item.__dict__ for item in diagnostics], sort_keys=True
                ),
            },
        )


def write_wgsl(
    math_spec: MathSpec,
    feedback: list[str] | None = None,
    *,
    capabilities: DeviceCapabilities | None = None,
    policy: GenerationPolicy | None = None,
) -> ShaderArtifact:
    return WGSLWriter(capabilities=capabilities, policy=policy).write(
        math_spec, feedback
    )
