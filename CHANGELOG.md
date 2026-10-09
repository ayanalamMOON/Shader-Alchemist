# Changelog

All notable changes to Shader Alchemist are documented here.

## [Unreleased] - 2026-10-09

### Added

#### Agent-core pipeline

- Added validated Pydantic contracts for:
  - `MathSpec`
  - `ShaderArtifact`
  - `EvalReport`
  - `DeviceCapabilities`
  - pipeline state and iteration history
- Added deterministic shader agents for:
  - mathematical workload planning;
  - WGSL generation;
  - static and optional runtime evaluation.
- Added a registry-based WGSL generator with support for:
  - vector addition;
  - scalar multiplication;
  - SAXPY;
  - buffer copy;
  - custom kernel registration.
- Added workgroup, dispatch, binding, alignment, feature, source-size, entry-point,
  bounds-safety, and source-hash validation.
- Added local WGSL structural analysis.
- Added state transitions, persistence, evaluation history, feedback handling, and
  bounded refinement loops.
- Added sequential local pipeline orchestration.

#### Gemini and Google ADK integration

- Added an asynchronous Google ADK runtime adapter with:
  - `LlmAgent`;
  - `Runner.run_async`;
  - isolated sessions;
  - structured Pydantic output schemas;
  - JSON and Markdown-fenced JSON response recovery;
  - configurable retries;
  - configurable timeouts;
  - explicit unavailable-runtime errors.
- Added Gemini-backed Math Architect, WGSL Writer, and Performance Evaluator agents.
- Added an ADK sequential pipeline:

  ```text
  Gemini Math Architect
      -> Gemini WGSL Writer
      -> local artifact validation
      -> Gemini Performance Evaluator
      -> local evaluator authority gate
      -> bounded refinement
  ```

- Added local validation as the final authority so Gemini cannot mark an invalid or
  unsafe shader as passed.
- Added CLI support for `--adk`.
- Added environment-based ADK configuration:
  - `GOOGLE_API_KEY`;
  - `SHADER_ALCHEMIST_USE_ADK`;
  - model, timeout, retry, app-name, and user-id settings.
- Added Google ADK and Google GenAI package dependencies.

#### Prompt templates

- Expanded `math_architect.jinja2` with:
  - strict MathSpec output requirements;
  - workload and domain analysis;
  - mathematical formulation rules;
  - dispatch derivation;
  - binding and host-layout planning;
  - synchronization and optional-feature guidance;
  - numerical tolerance requirements;
  - consistency review instructions.
- Expanded `wgsl_writer.jinja2` with:
  - strict ShaderArtifact output requirements;
  - WGSL syntax and type safety rules;
  - runtime-array bounds guards;
  - workgroup memory and barrier requirements;
  - host binding compatibility;
  - numerical and performance guidance;
  - compiler-style self-review.
- Expanded `evaluator.jinja2` with:
  - strict EvalReport output requirements;
  - ordered static validation;
  - binding and alignment review;
  - bounds and race analysis;
  - numerical correctness checks;
  - runtime measurement rules;
  - evidence-based pass/fail criteria.

#### WebGPU harness

- Replaced the WebGPU harness skeleton with a TypeScript execution boundary.
- Added real browser-based WebGPU execution through Playwright.
- Added WGSL compilation and `getCompilationInfo()` diagnostics.
- Added adapter and device capability discovery.
- Added required-feature validation.
- Added support for multiple contiguous bind groups.
- Added bind-group layout generation from `ShaderArtifact`.
- Added bounded GPU buffer allocation.
- Added input upload from:
  - packed `f32` arrays;
  - base64 byte strings.
- Added compute dispatch and GPU completion waits.
- Added output buffer readback with base64 serialization.
- Added warm-up and measured benchmark iterations.
- Added median, mean, min, max, P95, and P99 timing summaries.
- Added timestamp-query support when available.
- Added host monotonic timing fallback.
- Added scoped uncaptured WebGPU error collection.
- Added device-loss reporting.
- Added configurable limits for:
  - dispatch invocations;
  - allocated buffer bytes;
  - warm-up iterations;
  - measured iterations.
- Added numerical output comparison with:
  - absolute tolerances;
  - relative tolerances;
  - exact discrete comparison;
  - mismatch counts;
  - maximum error reporting;
  - first mismatch reporting.
- Added reproducibility manifests with SHA-256 hashes for shader, artifact,
  workload, and configuration inputs.
- Added a JSON CLI compatible with the Python `WebGPUProfiler` bridge.
- Added WebGPU harness package metadata, strict TypeScript configuration, and
  package scripts.
- Added browser runner template and harness documentation.

#### Code generation and reporting

- Added Markdown evaluation report generation.
- Added TypeScript WebGPU driver generation.
- Added static-analysis JSON output.
- Added artifact source hashes and serialized pipeline state output.
- Updated the Python profiler bridge to accept both:
  - `execution_time_ms`;
  - `gpu_execution_time_ms`.

#### Testing and developer tooling

- Added agent-core tests for:
  - Math Architect behavior;
  - WGSL writer kernels and validation;
  - pipeline loop behavior;
  - state persistence;
  - code generation;
  - ADK response parsing.
- Added WebGPU harness tests for harness and timestamp-query behavior.
- Added [scripts/run_tests.sh](scripts/run_tests.sh), which:
  - resolves the repository root automatically;
  - works regardless of the caller's current directory;
  - runs agent-core tests through `uv` when available;
  - falls back to the repository virtual environment;
  - builds the WebGPU harness;
  - runs WebGPU harness tests;
  - supports `--python-only`;
  - supports `--webgpu-only`;
  - returns meaningful failure statuses.
- Expanded the root `.gitignore` for:
  - Python environments and caches;
  - Node dependencies and build output;
  - generated shader artifacts;
  - benchmark and report output;
  - profiling traces;
  - local configuration files;
  - temporary files.

### Usage

Run all available tests from any directory:

```bash
bash scripts/run_tests.sh
```

Run only agent-core tests:

```bash
bash scripts/run_tests.sh --python-only
```

Run only the WebGPU harness build and tests:

```bash
bash scripts/run_tests.sh --webgpu-only
```

Run the deterministic local pipeline:

```bash
shader-alchemist build \
  "add two vectors with 1025 elements" \
  --output artifacts/vector-add
```

Run through Gemini and Google ADK:

```bash
export GOOGLE_API_KEY="your-api-key"
shader-alchemist build \
  "create a bounds-safe vector addition shader for 4096 elements" \
  --adk \
  --output artifacts/adk-vector-add
```

Build the WebGPU harness:

```bash
cd packages/webgpu-harness
npm install
npx playwright install chromium
npm run build
npm test
```

### Validation status

- Editor diagnostics report no remaining TypeScript errors in the WebGPU harness.
- The timestamp-query implementation was aligned with the installed
  `@webgpu/types` declarations by using `GPUComputePassDescriptor.timestampWrites`.
- The test runner has been added and is path-independent.
- Live test execution has been attempted through the repository environment and
  `uv`, but the current Windows sandbox can block process startup before Python,
  Node, or npm execute.
- A live Gemini invocation requires a configured `GOOGLE_API_KEY`.
- Real WebGPU execution requires a browser/runtime with WebGPU support and a
  compatible adapter.

### Known limitations

- The ADK runtime currently uses isolated in-memory sessions; a persistent session
  service should be added for multi-user deployments.
- Runtime WebGPU evidence is not yet automatically merged into every Gemini evaluator
  report.
- The harness currently accepts generic buffer payloads; algorithm-specific reference
  input generation and output-oracle wiring should be expanded for each kernel family.
- Browser GPU availability and timestamp-query support remain platform-dependent.

