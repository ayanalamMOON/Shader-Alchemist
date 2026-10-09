"""Google ADK runtime for structured Shader Alchemist agents.

This module owns all provider-specific code. Agents communicate through Pydantic response
schemas, and no unvalidated model text is allowed into the compiler pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import Settings
from ..schemas.artifact import ShaderArtifact
from ..schemas.eval_report import EvalReport
from ..schemas.math_spec import MathSpec
from .evaluator import PerformanceEvaluator

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AdkUnavailableError(RuntimeError):
    """Raised when the Google ADK runtime cannot be imported or configured."""


class AdkInvocationError(RuntimeError):
    """Raised when an ADK invocation fails or returns invalid structured data."""


def _load_adk() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from google.adk.agents import LlmAgent
        from google.adk.agents.run_config import RunConfig
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except ImportError as exc:
        raise AdkUnavailableError(
            "Google ADK is not installed. Install the agent-core dependencies."
        ) from exc
    return LlmAgent, RunConfig, Runner, InMemorySessionService, types, asyncio


def _event_text(event: Any) -> str:
    content = getattr(event, "content", None)
    if content is None:
        return ""
    parts = getattr(content, "parts", None) or []
    return "".join(
        str(getattr(part, "text", ""))
        for part in parts
        if getattr(part, "text", None)
    )


class AdkStructuredRuntime:
    """Reusable structured-output ADK runner.

    A new session is created per runtime instance and each logical agent receives an isolated
    invocation. This avoids cross-agent prompt leakage while retaining traceable session IDs.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_environment()
        (
            self._llm_agent,
            self._run_config,
            self._runner,
            self._session_service,
            self._types,
            _,
        ) = _load_adk()
        self._sessions = self._session_service()

    async def _events(
        self, agent: Any, prompt: str, session_id: str, user_id: str
    ) -> AsyncIterator[Any]:
        runner = self._runner(
            app_name=self.settings.adk_app_name,
            agent=agent,
            session_service=self._sessions,
        )
        await self._sessions.create_session(
            app_name=self.settings.adk_app_name,
            user_id=user_id,
            session_id=session_id,
        )
        message = self._types.Content(
            role="user", parts=[self._types.Part(text=prompt)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
            run_config=self._run_config(
                response_modalities=[self._types.Modality.TEXT]
            ),
        ):
            yield event

    async def invoke(
        self,
        *,
        name: str,
        instruction: str,
        prompt: str,
        output_schema: type[T],
        session_id: str,
        user_id: str | None = None,
    ) -> T:
        """Invoke one ADK LLM agent and validate its final structured response."""
        agent = self._llm_agent(
            name=name,
            model=self.settings.adk_model,
            instruction=instruction,
            output_schema=output_schema,
            output_key="structured_output",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )
        last_error: Exception | None = None
        for attempt in range(self.settings.adk_max_retries + 1):
            try:
                async with asyncio.timeout(self.settings.adk_timeout_seconds):
                    text = ""
                    final_output: Any = None
                    async for event in self._events(
                        agent,
                        prompt,
                        session_id=f"{session_id}-{name}-{attempt}",
                        user_id=user_id or self.settings.adk_user_id,
                    ):
                        text += _event_text(event)
                        actions = getattr(event, "actions", None)
                        state_delta = getattr(actions, "state_delta", None)
                        if state_delta and "structured_output" in state_delta:
                            final_output = state_delta["structured_output"]
                    if final_output is not None:
                        if isinstance(final_output, str):
                            return self._parse_response(final_output, output_schema)
                        return output_schema.model_validate(final_output)
                    return self._parse_response(text, output_schema)
            except (
                TimeoutError,
                ValidationError,
                json.JSONDecodeError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                last_error = exc
                if attempt >= self.settings.adk_max_retries:
                    break
                logger.warning(
                    "ADK invocation failed; retrying",
                    extra={"agent": name, "attempt": attempt + 1, "error": str(exc)},
                )
        raise AdkInvocationError(
            f"ADK agent {name!r} failed after {self.settings.adk_max_retries + 1} attempts: "
            f"{last_error}"
        ) from last_error

    @staticmethod
    def _parse_response(text: str, schema: type[T]) -> T:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.split("\n", 1)[1]
            candidate = candidate.rsplit("```", 1)[0].strip()
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start < 0 or end <= start:
                raise
            value = json.loads(candidate[start : end + 1])
        return schema.model_validate(value)


class AdkShaderAgents:
    """Typed Math Architect, WGSL Writer, and Evaluator facade."""

    def __init__(self, runtime: AdkStructuredRuntime | None = None) -> None:
        self.runtime = runtime or AdkStructuredRuntime()
        self._evaluator_prompts = PerformanceEvaluator()

    async def create_math_spec(
        self, prompt: str, rendered_instruction: str, session_id: str
    ) -> MathSpec:
        return await self.runtime.invoke(
            name="math_architect",
            instruction=rendered_instruction,
            prompt=prompt,
            output_schema=MathSpec,
            session_id=session_id,
        )

    async def create_shader_artifact(
        self, prompt: str, rendered_instruction: str, session_id: str
    ) -> ShaderArtifact:
        return await self.runtime.invoke(
            name="wgsl_writer",
            instruction=rendered_instruction,
            prompt=prompt,
            output_schema=ShaderArtifact,
            session_id=session_id,
        )

    async def evaluate_shader(
        self, prompt: str, rendered_instruction: str, session_id: str
    ) -> EvalReport:
        return await self.runtime.invoke(
            name="performance_evaluator",
            instruction=rendered_instruction,
            prompt=prompt,
            output_schema=EvalReport,
            session_id=session_id,
        )

    def evaluator_instruction(
        self, artifact: ShaderArtifact, target_budget_ms: float
    ) -> str:
        return self._evaluator_prompts.render_prompt(
            artifact, target_budget_ms=target_budget_ms
        )


def run_async(coroutine: Any) -> Any:
    """Run an ADK coroutine from synchronous callers without nested-loop corruption."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    raise RuntimeError(
        "run_async() cannot be called from an active event loop; use the async API instead"
    )
