#!/usr/bin/env bash
# Scaffolds the shader-alchemist monorepo.
# Usage: ./create_shader_alchemist.sh [target_dir]   (default: shader-alchemist)

set -euo pipefail

ROOT="${1:-shader-alchemist}"
mkdir -p "$ROOT"
cd "$ROOT"

PY="packages/agent-core/src/shader_alchemist"
TS="packages/webgpu-harness"

# ---------- Directories ----------
mkdir -p \
  .github/workflows .github/ISSUE_TEMPLATE \
  docs/architecture docs/examples \
  "$PY"/{agents/prompts,schemas,pipeline,tools,codegen} \
  packages/agent-core/src/tests \
  "$TS"/src/{profiler,templates,utils} "$TS"/tests \
  templates/typescript templates/html \
  scripts

# ---------- .github ----------
touch .github/workflows/{ci.yml,benchmark.yml}
touch .github/ISSUE_TEMPLATE/bug_report.md

# ---------- docs ----------
touch docs/architecture/{system-topology.png,state-machine.md,memory-alignment-rules.md}
touch docs/examples/{spatial-hash-3d.md,sph-fluid-sim.md}
touch docs/api-reference.md

# ---------- packages/agent-core (Python) ----------
touch packages/agent-core/{pyproject.toml,README.md}
touch "$PY"/{__init__.py,main.py,config.py}

touch "$PY"/agents/{__init__.py,math_architect.py,wgsl_writer.py,evaluator.py}
touch "$PY"/agents/prompts/{math_architect.jinja2,wgsl_writer.jinja2,evaluator.jinja2}

touch "$PY"/schemas/{__init__.py,state.py,math_spec.py,artifact.py,eval_report.py}
touch "$PY"/pipeline/{__init__.py,sequential.py,loop_block.py,state_manager.py}
touch "$PY"/tools/{__init__.py,profiler_tool.py,static_analyzer.py}
touch "$PY"/codegen/{__init__.py,ts_driver_generator.py,report_generator.py}

touch packages/agent-core/src/tests/{test_math_architect.py,test_wgsl_writer.py,test_pipeline_loop.py}

# ---------- packages/webgpu-harness (TypeScript/Node) ----------
touch "$TS"/{package.json,tsconfig.json,README.md}
touch "$TS"/src/{index.ts,browser-runner.ts}
touch "$TS"/src/profiler/{device.ts,buffer-allocator.ts,query-set.ts,validation-scope.ts}
touch "$TS"/src/templates/runner-page.html
touch "$TS"/src/utils/time.ts
touch "$TS"/tests/{harness.test.ts,timestamp-query.test.ts}

# ---------- templates ----------
touch templates/typescript/{package.json.jinja2,tsconfig.json.jinja2,webgpu_app.ts.jinja2}
touch templates/html/standalone_demo.html.jinja2

# ---------- scripts ----------
touch scripts/{setup_environment.sh,run_harness_server.sh,benchmark_all_examples.py}
chmod +x scripts/*.sh scripts/*.py

# ---------- root files ----------
touch .gitignore .env.example pnpm-workspace.yaml README.md LICENSE

echo "Created $(find . -type d | wc -l) directories and $(find . -type f | wc -l) files in $(pwd)"
