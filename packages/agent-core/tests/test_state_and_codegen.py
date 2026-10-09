from shader_alchemist.agents import build_math_spec, write_wgsl
from shader_alchemist.codegen import generate_markdown_report, generate_typescript_driver
from shader_alchemist.pipeline import StateManager
from shader_alchemist.schemas import ShaderAlchemistState


def test_state_round_trip(tmp_path) -> None:
    state = ShaderAlchemistState(user_prompt="vector addition")
    path = tmp_path / "state.json"
    StateManager(state).save(path)
    loaded = StateManager.load(path).state
    assert loaded.session_id == state.session_id
    assert loaded.user_prompt == state.user_prompt


def test_generated_outputs_include_contract_details() -> None:
    spec = build_math_spec("add vectors with 32 elements")
    artifact = write_wgsl(spec)
    state = ShaderAlchemistState(
        user_prompt="add vectors with 32 elements",
        math_spec=spec,
        shader_artifact=artifact,
    )
    driver = generate_typescript_driver(artifact)
    report = generate_markdown_report(state)
    assert "createPipeline" in driver
    assert "vector_add" in report
