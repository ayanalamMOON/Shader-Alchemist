import pytest

from shader_alchemist.agents.adk_runtime import AdkStructuredRuntime
from shader_alchemist.schemas import MathSpec


def test_structured_response_parser_accepts_markdown_fences() -> None:
    value = AdkStructuredRuntime._parse_response(
        '```json\n{"algorithm_name":"vector_add","domain":{"element_count":1}}\n```',
        MathSpec,
    )
    assert value.algorithm_name == "vector_add"


def test_structured_response_parser_rejects_invalid_payload() -> None:
    with pytest.raises(Exception):
        AdkStructuredRuntime._parse_response("not json", MathSpec)
