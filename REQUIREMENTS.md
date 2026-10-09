# Shader Alchemist Requirements

**Status:** Product and research requirements  
**Version:** 1.0  
**Last updated:** October 2026

## 1. Purpose

Shader Alchemist is an agentic engineering system for turning a high-level compute workload into
a verified and measured WebGPU/WGSL implementation. It must separate mathematical reasoning,
shader synthesis, and execution evidence so that generated code is not accepted solely because it
looks plausible.

The system's core contract is:

> Intent → mathematical specification → shader artifact → validation and measurement → refinement
> → reproducible evidence package.

This document is the implementation-oriented source of truth for the required behavior described in
the project design documents.

## 2. Product scope

### In scope

- Compute-oriented WebGPU workloads written in WGSL.
- Natural-language and structured workload requests.
- Mathematical decomposition, buffer layout reasoning, dispatch derivation, and synchronization
  analysis.
- Host-side resource and pipeline metadata.
- Static WGSL checks and WebGPU validation.
- Isolated headless execution and GPU timestamp measurement where supported.
- CPU/reference comparisons, invariants, tolerances, and property-based checks.
- Bounded iterative optimization with explicit transformation history.
- Hardware capability profiles and capability-dependent variants.
- Reproducible benchmark manifests and diagnostic output.
- Example workloads such as spatial hashing, particle/fluid simulation, reductions, image
  processing, and matrix/vector kernels.

### Out of scope for the initial release

- General-purpose rendering-pipeline optimization.
- Replacing a full GPU vendor profiler or a formal theorem prover.
- Treating visual similarity as a substitute for numerical correctness.
- Unbounded autonomous search.
- Universal performance claims from a single device or benchmark.
- Silent source rewriting to bypass execution safety limits.

## 3. Actors and system boundaries

| Actor or component | Responsibility |
| --- | --- |
| User | Supplies intent, workload limits, tolerances, target capabilities, and priorities. |
| Math Architect | Produces a machine-checkable `MathSpec`. |
| WGSL Writer | Produces or refines a `ShaderArtifact` from the specification and feedback. |
| Performance Evaluator | Validates, executes, profiles, and reports evidence. |
| Artifact Assembler | Packages the selected candidate and all supporting evidence. |
| Agent core | Orchestrates agents, state transitions, schemas, prompts, and code generation. |
| WebGPU harness | Provides disposable browser/device execution, validation scopes, and timing. |

## 4. Functional requirements

### FR-001 — Workload intake

The system shall accept a workload containing:

- operation or algorithm;
- input and output domains;
- element counts or grid dimensions;
- data types and numerical precision;
- expected invariants and correctness tolerances;
- required and optional WebGPU features;
- memory, dispatch, and latency budgets;
- representative benchmark sizes;
- hard constraints versus optimization preferences.

### FR-002 — Mathematical specification

The Math Architect shall emit a `MathSpec` before shader synthesis. The specification shall
describe algorithm semantics, domain decomposition, workgroup shape, derived dispatch geometry,
buffer layouts and byte offsets, bindings, synchronization, numerical constraints, capabilities,
and verification obligations.

### FR-003 — Layout and dispatch safety

The system shall:

1. calculate host-shareable layouts and explicit padding;
2. account for WGSL alignment rules, including 16-byte alignment for `vec3<f32>`-containing
   structures where applicable;
3. ensure bindings agree between host metadata and WGSL declarations;
4. derive dispatch dimensions from the workload domain and workgroup size;
5. reject inconsistent element counts, buffer lengths, bindings, or dispatch dimensions before
   execution.

### FR-004 — Shader synthesis

The WGSL Writer shall generate a `ShaderArtifact` containing, at minimum:

- WGSL source;
- entry points;
- binding and resource metadata;
- workgroup and dispatch configuration;
- required feature declarations;
- provenance linking the artifact to its `MathSpec` and refinement history.

The writer shall support feedback-driven revisions for validation failures, unsafe memory access,
workgroup sizing, memory locality, divergence, synchronization, and numerical regressions.

### FR-005 — Static and API validation

The evaluator shall distinguish and report:

- source/compiler errors;
- WebGPU pipeline and resource validation errors;
- memory-safety failures;
- numerical failures;
- semantic or invariant failures;
- deterministic/parallel consistency failures;
- performance-budget failures.

Passing one validation layer shall not imply that the other layers passed.

### FR-006 — Isolated execution and profiling

The harness shall execute candidates in a disposable or otherwise isolated WebGPU context. Where
the device supports it, it shall use GPU timestamp queries and report whether compilation,
resource creation, data upload, and dispatch execution are included in each measurement.

The evaluator shall use warm-up iterations followed by measured iterations and report distributions
such as median and high percentiles rather than only a single average.

### FR-007 — Correctness verification

Every supported kernel shall have a CPU or mathematically simple reference implementation, or an
explicitly documented alternative oracle. The evaluator shall support:

- exact comparisons for discrete algorithms;
- absolute and relative tolerances for floating-point results;
- norm-based error reporting;
- application-specific aggregation rules;
- property-based inputs and invariant checks;
- deterministic replay where the workload permits it.

### FR-008 — Bounded refinement loop

The orchestrator shall implement the following bounded lifecycle:

`PENDING → SPECIFIED → GENERATED → EVALUATING → PASSED`

or:

`EVALUATING → REFINING → GENERATED`

Candidates that exceed the refinement budget, safety limits, or unrecoverable validation
conditions shall transition to `FAILED` or `BUDGET_EXCEEDED`. Each transition shall be recorded.

### FR-009 — Optimization experiments

Each optimization shall be named and recorded as an experiment. Supported transformation
categories shall include workgroup-size tuning, AoS/SoA layout changes, workgroup tiling, loop
and branch restructuring, multi-pass decomposition, subgroup operations, precision changes,
specialization, and dispatch decomposition.

The evaluator shall compare candidates under the same benchmark manifest. Correctness and hard
resource constraints shall be applied before performance ranking.

### FR-010 — Capability-aware generation

The system shall discover and persist a hardware capability profile containing supported features,
device limits, memory-related properties, timestamp/query support, and platform metadata. It shall
not assume optional WebGPU features are universally available and shall generate fallback variants
or reject unsupported candidates explicitly.

### FR-011 — Safety guardrails

The harness shall enforce configurable upper bounds for:

- total dispatch work;
- allocated buffer memory;
- loop or iteration budgets;
- wall-clock execution time;
- benchmark input size.

It shall also support watchdogs, cancellation, disposable browser/device contexts, host-process
supervision, failure quarantine, and rollback to the last known-good artifact. Unsafe candidates
shall be rejected or profiled under documented constraints, never silently changed.

### FR-012 — Evidence package

A successful task shall produce:

```text
ShaderAlchemistOutput/
├── shader.wgsl
├── host_driver.ts
├── math_spec.json
├── layout_spec.json
├── capability_profile.json
├── correctness_report.md
├── performance_report.md
├── optimization_history.json
└── reproducibility_manifest.json
```

The exact serialization may evolve, but the semantic contents are required.

## 5. Data-contract requirements

### `MathSpec`

Required conceptual fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Contract version for compatibility and migrations. |
| `algorithm` | Algorithm identity and semantic traceability. |
| `domain` | Input/output domain and workload dimensions. |
| `workgroups` | Candidate local workgroup dimensions. |
| `dispatch` | Derived global dispatch geometry. |
| `buffers` | Element types, strides, offsets, padding, and sizes. |
| `bindings` | Group, binding, resource type, and access mode. |
| `synchronization` | Barriers, atomics, hazards, and pass boundaries. |
| `numerics` | Precision, absolute/relative tolerances, and reduction policy. |
| `capabilities` | Required features and device limits. |
| `invariants` | Properties that must hold after execution. |

### `ShaderArtifact`

The artifact shall contain source, entry points, bindings, dispatch metadata, feature requirements,
and provenance. It is not valid if it contains WGSL without the host-side execution contract.

### `EvalReport`

The report shall contain validation results, timing samples and summary statistics, correctness
results, memory/resource observations, numerical errors, optimization observations, and remediation
recommendations.

### Reproducibility manifest

Each experiment shall preserve an identity containing shader, math specification, hardware,
input, configuration, and timestamp hashes, plus workload size, seed, reference-output hash,
tolerances, dispatch dimensions, feature requirements, warm-up count, and measured iteration count.

## 6. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | **Correctness first:** no performance score may compensate for a failed hard correctness or safety constraint. |
| NFR-002 | **Reproducibility:** comparable runs must retain enough metadata to replay or explain the result. |
| NFR-003 | **Isolation:** generated executable code must run outside the agent process where practical. |
| NFR-004 | **Auditability:** state transitions, hypotheses, failures, transformations, and selected/rejected candidates must be inspectable. |
| NFR-005 | **Portability:** device-specific assumptions must be represented as capabilities, not hidden heuristics. |
| NFR-006 | **Determinism:** schemas, derived dispatch, and validation outcomes should be deterministic for identical inputs and capabilities. |
| NFR-007 | **Observability:** reports must separate validation, correctness, resource, timing, and optimization evidence. |
| NFR-008 | **Bounded cost:** every autonomous loop and benchmark sweep must have explicit limits. |
| NFR-009 | **Maintainability:** Python agent logic and TypeScript harness logic must remain independently testable. |
| NFR-010 | **Privacy:** local execution should be possible without sending shader source or workload data to a remote evaluator. |

## 7. Acceptance criteria

A release candidate is acceptable only when:

1. a representative workload produces a valid `MathSpec`;
2. the generated artifact passes schema and static validation;
3. host and WGSL bindings/layouts agree;
4. dispatch bounds prevent out-of-range accesses;
5. the harness can execute within configured limits or reports a structured failure;
6. output is compared with a reference implementation using recorded tolerances;
7. timing uses a documented warm-up and measurement protocol;
8. at least one refinement cycle can consume evaluator feedback;
9. all state transitions and experiment metadata are persisted;
10. the final package contains shader, contract, correctness, performance, and reproducibility evidence.

## 8. Delivery phases

1. **Deterministic foundation:** schemas, manifests, artifact contracts, reference outputs, and a
   minimal harness.
2. **Agentic synthesis:** Math Architect and WGSL Writer with validated handoffs.
3. **Closed-loop optimization:** named transformations, correctness gates, and bounded refinement.
4. **Hardware-aware search:** capability profiles, parameter sweeps, fallbacks, and benchmark history.
5. **Research platform:** cross-device experiments, baselines, ablations, confidence estimates,
   and reproducible study outputs.

## 9. Requirement traceability

| Requirement area | Primary design source | Repository surface |
| --- | --- | --- |
| Agent orchestration | Architecture and state-machine sections | `packages/agent-core/src/shader_alchemist/pipeline/` |
| Mathematical contracts | MathSpec and layout sections | `packages/agent-core/src/shader_alchemist/schemas/math_spec.py` |
| Artifact contracts | ShaderArtifact section | `packages/agent-core/src/shader_alchemist/schemas/artifact.py` |
| Evaluation evidence | EvalReport and profiling sections | `packages/agent-core/src/shader_alchemist/schemas/eval_report.py`, `packages/webgpu-harness/` |
| Safety and isolation | Safety and TDR sections | `packages/agent-core/src/shader_alchemist/tools/`, `packages/webgpu-harness/src/` |
| Examples and research workloads | End-to-end scenario sections | `docs/examples/` |
| Delivery automation | Repository architecture and roadmap | `.github/workflows/`, `scripts/`, `templates/` |
