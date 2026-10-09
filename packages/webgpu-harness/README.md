# WebGPU Harness

`@shader-alchemist/webgpu-harness` is the isolated execution boundary between the Python
agent pipeline and a real WebGPU implementation. It compiles candidate WGSL, validates its
bind-group contract, allocates bounded resources, dispatches it in a browser context, captures
validation errors, collects warm-up and measured samples, and returns one JSON result suitable
for `WebGPUProfiler`.

## Install and build

```powershell
npm install
npm run build
npx playwright install chromium
```

The browser must expose WebGPU. Chromium may require a platform-specific GPU configuration or
adapter flags on CI. The harness reports unavailability instead of silently falling back to a
fake benchmark.

## CLI

The process accepts either a JSON object or a path to a JSON job and always emits one JSON result
on stdout:

```powershell
node dist/index.js artifact-job.json
```

The job contains the serialized `ShaderArtifact` plus optional input data:

```json
{
  "artifact": {
    "wgsl_code": "@group(0) @binding(0) var<storage, read> input: array<f32>; ...",
    "entry_point": "main",
    "bind_group_layouts": [
      {
        "group": 0,
        "binding": 0,
        "name": "input",
        "resource_type": "storage_read",
        "visibility": ["compute"],
        "min_binding_size": 4096
      }
    ],
    "dispatch_size": [16, 1, 1],
    "required_features": []
  },
  "buffers": [
    { "binding": 0, "data": [0, 1, 2, 3], "byteLength": 4096 }
  ],
  "warmupIterations": 2,
  "measuredIterations": 10,
  "maxDispatchInvocations": 16777216,
  "maxBufferBytes": 268435456,
  "targetBudgetMs": 2
}
```

Array input is interpreted as packed `f32`. String input is base64 bytes. Output bindings can be
read back with `outputBindings`.

## Evidence and safety

The result separates:

- WGSL compilation and pipeline creation;
- uncaptured WebGPU validation errors;
- capability and feature availability;
- warm-up and measured timing distributions;
- timestamp-query support;
- allocated buffer bytes;
- output bytes for requested bindings.

The harness rejects oversized dispatches and allocations before execution. It destroys buffers,
query resources, and the device after each job. Timestamp queries are used when the adapter
supports `timestamp-query`; host wall-clock samples remain available as a fallback and are
reported as such.

Jobs are validated before requesting a browser device. Validation covers WGSL entry-point
identifiers, dispatch and buffer budgets, duplicate bindings, binding alignment, iteration
counts, declared output bindings, and feature names. Failures are returned as structured
diagnostic codes in `validation_errors` (for example `dispatch-budget:` or
`duplicate-binding:`), with `metadata.phase` identifying `preflight`, `device-request`,
`pipeline`, `execution`, or `host`. Device and dispatch failures are converted to a result and
still run cleanup, so callers do not need to handle browser exceptions separately.
