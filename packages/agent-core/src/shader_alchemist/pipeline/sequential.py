"""Math -> WGSL -> evaluation orchestration."""

from __future__ import annotations

from collections.abc import Callable

from ..agents import MathArchitect, PerformanceEvaluator, WGSLWriter
from ..schemas.state import PipelineStatus, ShaderAlchemistState
from .loop_block import RefinementLoop
from .state_manager import StateManager


class SequentialPipeline:
    def __init__(
        self,
        *,
        architect: MathArchitect | None = None,
        writer: WGSLWriter | None = None,
        evaluator: PerformanceEvaluator | None = None,
        loop: RefinementLoop | None = None,
    ) -> None:
        self.architect = architect or MathArchitect()
        self.writer = writer or WGSLWriter()
        self.evaluator = evaluator or PerformanceEvaluator()
        self.loop = loop or RefinementLoop()

    def run(
        self,
        user_prompt: str,
        *,
        element_count: int | None = None,
        workgroup_size: int = 64,
        on_iteration: Callable[[ShaderAlchemistState], None] | None = None,
    ) -> ShaderAlchemistState:
        state = ShaderAlchemistState(
            user_prompt=user_prompt,
            target_budget_ms=self.loop.target_budget_ms,
            max_iterations=self.loop.max_iterations,
        )
        manager = StateManager(state)
        try:
            state.math_spec = self.architect.build_spec(
                user_prompt,
                element_count=element_count,
                workgroup_size=workgroup_size,
            )
            manager.transition(PipelineStatus.SPECIFIED)
            while True:
                state.shader_artifact = self.writer.write(
                    state.math_spec, feedback=state.feedback
                )
                manager.transition(PipelineStatus.GENERATED)
                manager.transition(PipelineStatus.EVALUATING)
                report = self.evaluator.evaluate(
                    state.shader_artifact,
                    target_budget_ms=state.target_budget_ms,
                )
                state.record_evaluation(report)
                if on_iteration:
                    on_iteration(state)
                if self.loop.should_stop(report, state.current_iteration):
                    manager.transition(
                        PipelineStatus.PASSED
                        if report.pass_status
                        else PipelineStatus.FAILED
                    )
                    return state
                state.feedback = self.loop.feedback_for(report)
                state.current_iteration += 1
                manager.transition(PipelineStatus.REFINING)
        except Exception as exc:
            state.last_error = str(exc)
            if state.status not in {PipelineStatus.PASSED, PipelineStatus.FAILED}:
                manager.transition(PipelineStatus.FAILED, error=str(exc))
            return state