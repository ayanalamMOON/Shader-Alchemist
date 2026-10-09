import pytest

from shader_alchemist.agents import (
    ShaderGenerationError,
    WGSLWriter,
    build_math_spec,
    evaluate_shader,
    write_wgsl,
)
from shader_alchemist.pipeline import SequentialPipeline
from shader_alchemist.schemas import DeviceCapabilities, MathSpec, PipelineStatus
from shader_alchemist.tools import WGSLStaticAnalyzer


def test_vector_add_contract_derives_rounded_dispatch() -> None:
    spec = build_math_spec("add two vectors with 1025 elements")
    assert spec.algorithm_name == "vector_add"
    assert spec.grid_dispatch_dimensions == (17, 1, 1)
    assert [item.binding for item in spec.buffer_bindings] == [0, 1, 2]


def test_writer_emits_bounds_safe_shader() -> None:
    artifact = write_wgsl(build_math_spec("vector addition of 10 elements"))
    assert "arrayLength" in artifact.wgsl_code
    assert "if (index >=" in artifact.wgsl_code
    assert evaluate_shader(artifact).pass_status


def test_static_analyzer_accepts_baseline() -> None:
    spec = build_math_spec("vector addition of 64 elements")
    artifact = write_wgsl(spec)
    assert WGSLStaticAnalyzer().analyze(artifact, spec) == []


def test_pipeline_produces_artifacts_and_report() -> None:
    state = SequentialPipeline().run("add two vectors with 128 elements")
    assert state.status == PipelineStatus.PASSED
    assert state.math_spec is not None
    assert state.shader_artifact is not None
    assert len(state.eval_history) == 1


def test_writer_supports_registered_scalar_kernel() -> None:
    spec = MathSpec(
        algorithm_name="scalar_multiply",
        entry_point="scalar_multiply",
        domain={"element_count": 128},
        workgroup_dimensions=(64, 1, 1),
        grid_dispatch_dimensions=(2, 1, 1),
        buffer_bindings=[
            {"group": 0, "binding": 0, "name": "input_buffer", "resource_type": "storage_read", "stride_bytes": 4},
            {"group": 0, "binding": 1, "name": "scalar", "resource_type": "uniform", "stride_bytes": 16},
            {"group": 0, "binding": 2, "name": "output_buffer", "resource_type": "storage_read_write", "stride_bytes": 4},
        ],
    )
    artifact = WGSLWriter().write(spec)
    assert "scalar.value" in artifact.wgsl_code
    assert artifact.source_hash == artifact.metadata["source_hash"]


def test_writer_rejects_unsupported_device_workgroup() -> None:
    spec = build_math_spec("vector addition with 128 elements", workgroup_size=128)
    writer = WGSLWriter(
        capabilities=DeviceCapabilities(max_compute_invocations_per_workgroup=64)
    )
    with pytest.raises(ShaderGenerationError, match="workgroup-unsupported"):
        writer.write(spec)
