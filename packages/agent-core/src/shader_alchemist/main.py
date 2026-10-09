"""Command-line entry point for Shader Alchemist."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .agents import MathArchitect, PerformanceEvaluator, WGSLWriter
from .codegen import generate_markdown_report, generate_typescript_driver
from .config import Settings
from .pipeline import SequentialPipeline
from .pipeline import AdkSequentialPipeline
from .tools import WGSLStaticAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shader-alchemist",
        description="Design, synthesize, validate, and package WebGPU compute shaders.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="run the synthesis and evaluation pipeline")
    build.add_argument("prompt", help="high-level algorithm or shader request")
    build.add_argument("--elements", type=int)
    build.add_argument("--workgroup-size", type=int)
    build.add_argument("--budget-ms", type=float)
    build.add_argument("--max-iterations", type=int)
    build.add_argument("--output", type=Path)
    build.add_argument(
        "--adk",
        action="store_true",
        help="use Gemini through Google ADK instead of deterministic local agents",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "build":
        return 2
    settings = Settings.from_environment()
    use_adk = args.adk or settings.use_adk
    if use_adk:
        adk_pipeline = AdkSequentialPipeline()
        adk_pipeline.loop.target_budget_ms = args.budget_ms or settings.target_budget_ms
        adk_pipeline.loop.max_iterations = (
            args.max_iterations
            if args.max_iterations is not None
            else settings.max_iterations
        )
        state = asyncio.run(
            adk_pipeline.run_async(args.prompt)
        )
    else:
        pipeline = SequentialPipeline(
            architect=MathArchitect(),
            writer=WGSLWriter(),
            evaluator=PerformanceEvaluator(),
        )
        pipeline.loop.target_budget_ms = args.budget_ms or settings.target_budget_ms
        pipeline.loop.max_iterations = (
            args.max_iterations
            if args.max_iterations is not None
            else settings.max_iterations
        )
        state = pipeline.run(
            args.prompt,
            element_count=args.elements,
            workgroup_size=args.workgroup_size or settings.default_workgroup_size,
        )
    output = args.output or settings.output_directory
    output.mkdir(parents=True, exist_ok=True)
    (output / "state.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
    if state.shader_artifact:
        (output / "shader.wgsl").write_text(
            state.shader_artifact.wgsl_code, encoding="utf-8"
        )
        (output / "driver.ts").write_text(
            generate_typescript_driver(state.shader_artifact), encoding="utf-8"
        )
        static_issues = WGSLStaticAnalyzer().analyze(
            state.shader_artifact, state.math_spec
        )
        (output / "static-analysis.json").write_text(
            json.dumps([issue.__dict__ for issue in static_issues], indent=2),
            encoding="utf-8",
        )
    (output / "report.md").write_text(
        generate_markdown_report(state), encoding="utf-8"
    )
    print(f"{state.status.value}: {output}")
    return 0 if state.status.value == "passed" else 1