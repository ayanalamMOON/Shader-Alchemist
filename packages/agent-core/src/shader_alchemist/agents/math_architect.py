"""Math Architect agent and deterministic request-to-contract lowering."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..schemas.math_spec import BufferLayout, MathSpec, StructField


class MathArchitect:
    """Build a validated MathSpec, with an optional prompt for an LLM-backed agent."""

    def __init__(self, prompt_directory: str | Path | None = None) -> None:
        directory = Path(prompt_directory or Path(__file__).with_name("prompts"))
        self._templates = Environment(
            loader=FileSystemLoader(directory), undefined=StrictUndefined, autoescape=False
        )

    def render_prompt(
        self,
        user_prompt: str,
        target_budget_ms: float = 2.0,
        hardware_profile: dict[str, Any] | None = None,
    ) -> str:
        return self._templates.get_template("math_architect.jinja2").render(
            user_prompt=user_prompt,
            target_budget_ms=target_budget_ms,
            hardware_profile=json.dumps(hardware_profile or {}, sort_keys=True),
        )

    def build_spec(
        self,
        user_prompt: str,
        *,
        element_count: int | None = None,
        workgroup_size: int = 64,
    ) -> MathSpec:
        """Lower common requests locally; also provides an offline smoke-test path."""
        if element_count is None:
            match = re.search(r"\b(\d+)\s*(?:elements?|items?)\b", user_prompt, re.I)
            element_count = int(match.group(1)) if match else 1024
        if element_count < 1 or workgroup_size < 1:
            raise ValueError("element_count and workgroup_size must be positive")

        is_vector_add = bool(
            re.search(r"vector\s*(?:addition|add)|add(?:ing)?(?:\s+\w+)*\s+vectors?", user_prompt, re.I)
        )
        algorithm = "vector_add" if is_vector_add else "generic_elementwise"
        entry_point = "vector_add" if is_vector_add else "main"
        dispatch = math.ceil(element_count / workgroup_size)
        if is_vector_add:
            buffers = [
                BufferLayout(
                    group=0, binding=0, name="lhs", resource_type="storage_read",
                    stride_bytes=4,
                    fields=[StructField(name="values", wgsl_type="array<f32>", offset_bytes=0, size_bytes=4)],
                ),
                BufferLayout(
                    group=0, binding=1, name="rhs", resource_type="storage_read",
                    stride_bytes=4,
                    fields=[StructField(name="values", wgsl_type="array<f32>", offset_bytes=0, size_bytes=4)],
                ),
                BufferLayout(
                    group=0, binding=2, name="output_buffer", resource_type="storage_read_write",
                    stride_bytes=4,
                    fields=[StructField(name="values", wgsl_type="array<f32>", offset_bytes=0, size_bytes=4)],
                ),
            ]
            formulas = ["output[i] = lhs[i] + rhs[i]", "0 <= i < element_count"]
            invariants = ["input_lengths_equal", "output_length_equals_input_length"]
        else:
            buffers, formulas, invariants = [], [], ["bounds_checked"]
        return MathSpec(
            algorithm_name=algorithm,
            entry_point=entry_point,
            domain={"element_count": element_count, "request": user_prompt},
            workgroup_dimensions=(workgroup_size, 1, 1),
            grid_dispatch_dimensions=(dispatch, 1, 1),
            buffer_bindings=buffers,
            mathematical_formulations=formulas,
            invariants=invariants,
        )


def build_math_spec(user_prompt: str, **kwargs: Any) -> MathSpec:
    return MathArchitect().build_spec(user_prompt, **kwargs)