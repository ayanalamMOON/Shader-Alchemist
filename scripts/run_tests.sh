#!/usr/bin/env bash

# Run all repository tests without requiring the caller to configure paths.
# Usage:
#   bash scripts/run_tests.sh
#   bash scripts/run_tests.sh --python-only
#   bash scripts/run_tests.sh --webgpu-only

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
AGENT_CORE_DIR="$ROOT_DIR/packages/agent-core"
WEBGPU_HARNESS_DIR="$ROOT_DIR/packages/webgpu-harness"

RUN_PYTHON=true
RUN_WEBGPU=true

usage() {
  cat <<'USAGE'
Usage: scripts/run_tests.sh [option]

Options:
  --python-only   Run agent-core pytest tests only
  --webgpu-only   Build and test the WebGPU harness only
  --help          Show this help
USAGE
}

for argument in "$@"; do
  case "$argument" in
    --python-only)
      RUN_WEBGPU=false
      ;;
    --webgpu-only)
      RUN_PYTHON=false
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$argument" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$AGENT_CORE_DIR" || ! -f "$AGENT_CORE_DIR/pyproject.toml" ]]; then
  printf 'agent-core package was not found under %s\n' "$AGENT_CORE_DIR" >&2
  exit 1
fi

if [[ ! -d "$WEBGPU_HARNESS_DIR" || ! -f "$WEBGPU_HARNESS_DIR/package.json" ]]; then
  printf 'webgpu-harness package was not found under %s\n' "$WEBGPU_HARNESS_DIR" >&2
  exit 1
fi

python_status=0
webgpu_status=0

run_python_tests() {
  printf '\n== agent-core tests ==\n'
  cd "$ROOT_DIR" || return 1

  if command -v uv >/dev/null 2>&1; then
    uv run \
      --project "$ROOT_DIR" \
      --no-sync \
      python -m pytest \
      "$AGENT_CORE_DIR/tests" \
      "$AGENT_CORE_DIR/src/tests" \
      -q
  elif [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    "$ROOT_DIR/.venv/Scripts/python.exe" \
      -m pytest \
      "$AGENT_CORE_DIR/tests" \
      "$AGENT_CORE_DIR/src/tests" \
      -q
  elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    "$ROOT_DIR/.venv/bin/python" \
      -m pytest \
      "$AGENT_CORE_DIR/tests" \
      "$AGENT_CORE_DIR/src/tests" \
      -q
  else
    printf 'Neither uv nor the repository virtual environment was found.\n' >&2
    printf 'Install uv or create .venv, then run this script again.\n' >&2
    return 1
  fi
}

run_webgpu_tests() {
  printf '\n== webgpu-harness build ==\n'
  cd "$WEBGPU_HARNESS_DIR" || return 1
  npm run build || return $?

  printf '\n== webgpu-harness tests ==\n'
  npm test
}

if [[ "$RUN_PYTHON" == true ]]; then
  run_python_tests || python_status=$?
fi

if [[ "$RUN_WEBGPU" == true ]]; then
  run_webgpu_tests || webgpu_status=$?
fi

printf '\n== test summary ==\n'
if [[ "$RUN_PYTHON" == true ]]; then
  printf 'agent-core:      %s\n' "$([[ "$python_status" -eq 0 ]] && echo PASS || echo FAIL)"
fi
if [[ "$RUN_WEBGPU" == true ]]; then
  printf 'webgpu-harness:  %s\n' "$([[ "$webgpu_status" -eq 0 ]] && echo PASS || echo FAIL)"
fi

if [[ "$python_status" -ne 0 ]]; then
  exit "$python_status"
fi
exit "$webgpu_status"
