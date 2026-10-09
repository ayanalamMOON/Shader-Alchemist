# Live Example: Bounds-Safe Vector Addition

Vector addition is the smallest complete Shader Alchemist workload and should be used as the
first smoke test for a new environment, adapter, or generated host driver.

## Contract

```text
C[i] = A[i] + B[i]
0 <= i < element_count
```

The workload uses three storage buffers, a 64-thread workgroup, and a rounded-up x dispatch.
Every invocation must return before touching storage when its global index is outside the logical
element count.

## Generate and inspect

```bash
uv run --active shader-alchemist build \
  "add two vectors with 1025 elements" \
  --elements 1025 \
  --workgroup-size 64 \
  --output artifacts/examples/vector-add
```

```bash
cat artifacts/examples/vector-add/shader.wgsl
cat artifacts/examples/vector-add/report.md
```

Expected dispatch:

```text
ceil(1025 / 64) = 17 workgroups
```

## Reference WGSL

```wgsl
@group(0) @binding(0)
var<storage, read> input_a: array<f32>;

@group(0) @binding(1)
var<storage, read> input_b: array<f32>;

@group(0) @binding(2)
var<storage, read_write> output: array<f32>;

@compute @workgroup_size(64, 1, 1)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  let index = id.x;
  if (index >= arrayLength(&input_a) ||
      index >= arrayLength(&input_b) ||
      index >= arrayLength(&output)) {
    return;
  }
  output[index] = input_a[index] + input_b[index];
}
```

## Acceptance checks

- Output length equals the input length.
- Every output equals `a + b` exactly for ordinary `f32` fixtures.
- The final tail workgroup does not write outside the output buffer.
- The artifact dispatch is `[17, 1, 1]`.
- No optional WebGPU feature is required.
