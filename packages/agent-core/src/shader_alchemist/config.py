"""Environment-backed runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    target_budget_ms: float = Field(default=2.0, gt=0)
    max_iterations: int = Field(default=4, ge=0, le=100)
    default_workgroup_size: int = Field(default=64, gt=0, le=1024)
    harness_command: tuple[str, ...] = ()
    output_directory: Path = Path("artifacts")
    log_level: str = "INFO"
    adk_app_name: str = "shader-alchemist"
    adk_user_id: str = "shader-alchemist-user"
    adk_model: str = "gemini-2.5-flash"
    adk_timeout_seconds: float = Field(default=90.0, gt=0)
    adk_max_retries: int = Field(default=2, ge=0, le=10)
    use_adk: bool = False

    @classmethod
    def from_environment(cls) -> "Settings":
        command = os.getenv("SHADER_ALCHEMIST_HARNESS_COMMAND", "").strip()
        return cls(
            target_budget_ms=float(os.getenv("SHADER_ALCHEMIST_TARGET_BUDGET_MS", "2.0")),
            max_iterations=int(os.getenv("SHADER_ALCHEMIST_MAX_ITERATIONS", "4")),
            default_workgroup_size=int(
                os.getenv("SHADER_ALCHEMIST_WORKGROUP_SIZE", "64")
            ),
            harness_command=tuple(command.split()) if command else (),
            output_directory=Path(os.getenv("SHADER_ALCHEMIST_OUTPUT", "artifacts")),
            log_level=os.getenv("SHADER_ALCHEMIST_LOG_LEVEL", "INFO").upper(),
            adk_app_name=os.getenv("SHADER_ALCHEMIST_ADK_APP_NAME", "shader-alchemist"),
            adk_user_id=os.getenv("SHADER_ALCHEMIST_ADK_USER_ID", "shader-alchemist-user"),
            adk_model=os.getenv("SHADER_ALCHEMIST_ADK_MODEL", "gemini-2.5-flash"),
            adk_timeout_seconds=float(
                os.getenv("SHADER_ALCHEMIST_ADK_TIMEOUT_SECONDS", "90")
            ),
            adk_max_retries=int(os.getenv("SHADER_ALCHEMIST_ADK_MAX_RETRIES", "2")),
            use_adk=os.getenv("SHADER_ALCHEMIST_USE_ADK", "false").lower()
            in {"1", "true", "yes", "on"},
        )