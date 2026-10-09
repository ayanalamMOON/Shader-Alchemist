# Live Example: 3D Spatial Hash

This example describes a bounded, deterministic spatial-hash workload for broad-phase
neighbor lookup. It is intentionally split into two compute passes:

1. `hash_particles`: map each particle position to a cell key.
2. `sort_or_compact_cells`: build cell ranges for neighbor traversal.

The first pass is safe to run as a standalone Shader Alchemist generation request and is the
recommended smoke test for dispatch geometry, storage bindings, and tail guards.

## Workload contract

| Property | Value |
|---|---|
| Algorithm | `spatial_hash_3d` |
| Pass | `hash_particles` |
| Input | `positions: array<vec4<f32>>`, xyz used, w ignored |
| Output | `cell_keys: array<u32>` |
| Cell size | `0.25` |
| Grid dimensions | `256 x 256 x 256` |
| Workgroup | `64 x 1 x 1` |
| Dispatch | `ceil(particle_count / 64), 1, 1` |
| Boundary policy | Clamp cell coordinates to the valid grid |
| Correctness | Exact integer key comparison |

The packed key is:

```text
key = x + grid_width * (y + grid_height * z)
```

## Reference WGSL pass

```wgsl
struct Params {
  particle_count: u32,
  cell_size: f32,
  grid_width: u32,
  grid_height: u32,
  grid_depth: u32,
};

@group(0) @binding(0)
var<storage, read> positions: array<vec4<f32>>;

@group(0) @binding(1)
var<storage, read_write> cell_keys: array<u32>;

@group(0) @binding(2)
var<uniform> params: Params;

@compute @workgroup_size(64, 1, 1)
fn hash_particles(@builtin(global_invocation_id) id: vec3<u32>) {
  let index = id.x;
  if (index >= params.particle_count ||
      index >= arrayLength(&positions) ||
      index >= arrayLength(&cell_keys)) {
    return;
  }

  let position = positions[index].xyz;
  let raw = floor(position / vec3<f32>(params.cell_size));
  let max_cell = vec3<f32>(
    f32(params.grid_width - 1u),
    f32(params.grid_height - 1u),
    f32(params.grid_depth - 1u)
  );
  let cell = clamp(raw, vec3<f32>(0.0), max_cell);
  let x = u32(cell.x);
  let y = u32(cell.y);
  let z = u32(cell.z);
  cell_keys[index] = x + params.grid_width * (y + params.grid_height * z);
}
```

## Generate with the agent

From the repository root:

```bash
uv run --active shader-alchemist build \
  "Create a bounds-safe 3D spatial hash pass for 100000 particles using vec4 positions, \
   cell size 0.25, a 256 by 256 by 256 grid, exact u32 cell keys, and a 64-thread workgroup" \
  --elements 100000 \
  --workgroup-size 64 \
  --output artifacts/examples/spatial-hash-3d
```

Inspect the evidence:

```bash
cat artifacts/examples/spatial-hash-3d/report.md
cat artifacts/examples/spatial-hash-3d/static-analysis.json
```

## Correctness oracle

For each position:

```python
import math

def reference_key(position, cell_size=0.25, width=256, height=256, depth=256):
    x = min(max(math.floor(position[0] / cell_size), 0), width - 1)
    y = min(max(math.floor(position[1] / cell_size), 0), height - 1)
    z = min(max(math.floor(position[2] / cell_size), 0), depth - 1)
    return x + width * (y + height * z)
```

Test inputs must include negative coordinates, exact cell boundaries, coordinates above the
grid, zero particles, one particle, and a count that is not divisible by 64.

## Benchmark dimensions

The benchmark runner evaluates:

- `1024` particles;
- `100000` particles;
- `1000000` particles.

The hard safety limits are defined in [manifest.json](../../benchmarks/manifest.json). The
benchmark must reject candidates with unguarded tail invocations or unsupported features before
ranking performance.
