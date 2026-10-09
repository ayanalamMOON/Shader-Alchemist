"""Gemini/ADK-backed Shader Alchemist orchestration."""

from __future__ import annotations

from ..agents import AdkShaderAgents, MathArchitect, PerformanceEvaluator, WGSLWriter
from ..schemas.artifact import ShaderArtifact
from ..schemas.state import PipelineStatus, ShaderAlchemistState
from .loop_block import RefinementLoop
from .state_manager import StateManager


class AdkSequentialPipeline:
    """Run all three specialist agents through Google ADK.

    Local deterministic validation still runs after model output. ADK is responsible for
    reasoning and synthesis; the compiler-side checks remain the final authority.
    """

    def __init__(
        self,
        *,
        agents: AdkShaderAgents | None = None,
        architect: MathArchitect | None = None,
        writer: WGSLWriter | None = None,
        loop: RefinementLoop | None = None,
    ) -> None:
        self.agents = agents or AdkShaderAgents()
        self.architect = architect or MathArchitect()
        self.writer = writer or WGSLWriter()
        self.local_evaluator = PerformanceEvaluator()
        self.loop = loop or RefinementLoop()

    async def run_async(
        self,
        user_prompt: str,
        *,
        on_iteration=None,
    ) -> ShaderAlchemistState:
        state = ShaderAlchemistState(
            user_prompt=user_prompt,
            target_budget_ms=self.loop.target_budget_ms,
            max_iterations=self.loop.max_iterations,
        )
        manager = StateManager(state)
        try:
            state.math_spec = await self.agents.create_math_spec(
                prompt=user_prompt,
                rendered_instruction=self.architect.render_prompt(
                    user_prompt, self.loop.target_budget_ms
                ),
                session_id=state.session_id,
            )
            manager.transition(PipelineStatus.SPECIFIED)
            while True:
                writer_prompt = (
                    "Produce a ShaderArtifact JSON for this MathSpec. "
                    "Preserve every binding and entry point exactly.\n\n"
                    f"MathSpec:\n{state.math_spec.model_dump_json(indent=2)}\n\n"
                    f"Previous evaluator feedback:\n{state.feedback}"
                )
                model_artifact = await self.agents.create_shader_artifact(
                    prompt=writer_prompt,
                    rendered_instruction=self.writer.render_prompt(
                        state.math_spec, state.feedback
                    ),
                    session_id=state.session_id,
                )
                # The model must produce WGSL, but the local artifact contract owns provenance.
                state.shader_artifact = ShaderArtifact(
                    **model_artifact.model_dump(exclude={"math_spec"}),
                    math_spec=state.math_spec,
                )
                generation_errors = self.writer.validate_artifact(state.shader_artifact)
                if generation_errors:
                    state.feedback = [
                        f"{item.code}: {item.message}" for item in generation_errors
                    ]
                    state.last_error = "; ".join(state.feedback)
                    manager.transition(PipelineStatus.FAILED, error=state.last_error)
                    return state
                manager.transition(PipelineStatus.GENERATED)
                manager.transition(PipelineStatus.EVALUATING)
                evaluator_prompt = (
                    "Evaluate this artifact against the MathSpec and return EvalReport JSON.\n\n"
                    f"MathSpec:\n{state.math_spec.model_dump_json(indent=2)}\n\n"
                    f"Artifact:\n{state.shader_artifact.model_dump_json(indent=2)}"
                )
                report = await self.agents.evaluate_shader(
                    prompt=evaluator_prompt,
                    rendered_instruction=self.agents.evaluator_instruction(
                        state.shader_artifact, state.target_budget_ms
                    ),
                    session_id=state.session_id,
                )
                local_report = self.local_evaluator.evaluate(
                    state.shader_artifact,
                    target_budget_ms=state.target_budget_ms,
                )
                if not local_report.compilation_success:
                    report = report.model_copy(
                        update={
                            "pass_status": False,
                            "compilation_success": False,
                            "validation_errors": list(
                                dict.fromkeys(
                                    report.validation_errors
                                    + local_report.validation_errors
                                )
                            ),
                            "remediation_suggestions": list(
                                dict.fromkeys(
                                    report.remediation_suggestions
                                    + local_report.remediation_suggestions
                                )
                            ),
                        }
                    )
                state.record_evaluation(report)
                if on_iteration:
                    on_iteration(state)
                if self.loop.should_stop(report, state.current_iteration):
                    manager.transition(
                        PipelineStatus.PASSED if report.pass_status else PipelineStatus.FAILED
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
