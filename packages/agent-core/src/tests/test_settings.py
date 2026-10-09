from pydantic import ValidationError
import pytest

from shader_alchemist.config import Settings


def test_settings_have_safe_defaults() -> None:
    settings = Settings()
    assert settings.target_budget_ms > 0
    assert settings.max_iterations == 4
    assert settings.default_workgroup_size == 64
    assert settings.use_adk is False


def test_settings_reject_invalid_iteration_budget() -> None:
    with pytest.raises(ValidationError):
        Settings(max_iterations=101)


def test_settings_reject_non_positive_time_budget() -> None:
    with pytest.raises(ValidationError):
        Settings(target_budget_ms=0)
