"""Persistence and safe state transitions for pipeline runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas.state import PipelineStatus, ShaderAlchemistState


class InvalidTransitionError(RuntimeError):
    pass


class StateManager:
    _allowed: dict[PipelineStatus, set[PipelineStatus]] = {
        PipelineStatus.PENDING: {PipelineStatus.SPECIFIED, PipelineStatus.FAILED},
        PipelineStatus.SPECIFIED: {PipelineStatus.GENERATED, PipelineStatus.FAILED},
        PipelineStatus.GENERATED: {
            PipelineStatus.EVALUATING,
            PipelineStatus.FAILED,
        },
        PipelineStatus.EVALUATING: {
            PipelineStatus.PASSED,
            PipelineStatus.REFINING,
            PipelineStatus.FAILED,
        },
        PipelineStatus.REFINING: {
            PipelineStatus.GENERATED,
            PipelineStatus.FAILED,
        },
        PipelineStatus.PASSED: set(),
        PipelineStatus.FAILED: set(),
    }

    def __init__(self, state: ShaderAlchemistState) -> None:
        self.state = state

    def transition(self, status: PipelineStatus, *, error: str | None = None) -> None:
        if status == self.state.status:
            return
        if status not in self._allowed[self.state.status]:
            raise InvalidTransitionError(
                f"cannot transition from {self.state.status.value} to {status.value}"
            )
        self.state.status = status
        if error:
            self.state.last_error = error

    def update_metadata(self, **values: Any) -> None:
        self.state.metadata.update(values)

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            self.state.model_dump_json(indent=2), encoding="utf-8"
        )
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "StateManager":
        source = Path(path)
        state = ShaderAlchemistState.model_validate_json(
            source.read_text(encoding="utf-8")
        )
        return cls(state)