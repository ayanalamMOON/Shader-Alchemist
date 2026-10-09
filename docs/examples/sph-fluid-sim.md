# Live Example: SPH Fluid Density

This example is a single-pass Smoothed Particle Hydrodynamics density calculation. It is a
representative memory-bound workload and is useful for testing agent reasoning about loops,
floating-point tolerances, and bounded execution.

For production-scale fluids, use a uniform-grid or spatial-hash neighbor list rather than the
reference all-pairs pass. The all-pairs variant below is deliberately simple and serves as a
correctness baseline.

## Workload contract

| Property | Value |
|---|---|
| Algorithm | `sph_density_all_pairs` |
| Input | `positions: array<vec4<f32>>`, xyz used |
| Output | `density: array<f32>` |
| Particle count | `N` |
| Smoothing radius | `h = 0.04` |
| Workgroup | `64 x 1 x 1` |
| Dispatch | `ceil(N / 64), 1, 1` |
| Correctness | Relative error <= `1e-4`, absolute error <= `1e-5` |
| Safety | Maximum pair iterations explicitly bounded by `N` |

The reference kernel uses the poly6 kernel:

```text
W(r, h) = 315 / (64 pi h^9) * (h^2 - r^2)^3, 0 <= r < h
```

## Reference WGSL pass

```wgsl
struct Params {
  particle_count: u32,
  smoothing_radius: f32,
  particle_mass: f32,
  _padding: f32,
};

@group(0) @binding(0)
var<storage, read> positions: array<vec4<f32>>;

@group(0) @binding(1)
var<storage, read_write> density: array<f32>;

@group(0) @binding(2)
var<uniform> params: Params;

const PI: f32 = 3.141592653589793;

@compute @workgroup_size(64, 1, 1)
fn compute_density(@builtin(global_invocation_id) id: vec3<u32>) {
  let index = id.x;
  if (index >= params.particle_count ||
      index >= arrayLength(&positions) ||
      index >= arrayLength(&density)) {
    return;
  }

  let h = params.smoothing_radius;
  if (h <= 0.0) {
    density[index] = 0.0;
    return;
  }

  let h2 = h * h;
  let h9 = h2 * h2 * h2 * h2 * h;
  let coefficient = 315.0 / (64.0 * PI * h9);
  let origin = positions[index].xyz;
  var value = 0.0;

  for (var neighbor = 0u; neighbor < params.particle_count; neighbor++) {
    if (neighbor >= arrayLength(&positions)) {
      break;
    }
    let delta = origin - positions[neighbor].xyz;
    let distance2 = dot(delta, delta);
    if (distance2 < h2) {
      let term = h2 - distance2;
      value += params.particle_mass * coefficient * term * term * term;
    }
  }
  density[index] = value;
}
```

## Generate with the agent

```bash
uv run --active shader-alchemist build \
  "Create a bounds-safe SPH density compute shader using the poly6 kernel, \
   vec4 particle positions, particle mass, smoothing radius, a 64-thread workgroup, \
   and absolute tolerance 1e-5 with relative tolerance 1e-4" \
  --elements 4096 \
  --workgroup-size 64 \
  --budget-ms 10 \
  --output artifacts/examples/sph-density
```

## Correctness oracle

Use a CPU implementation with the same `f32` inputs and compare each output:

```python
def poly6_density(position, positions, mass, h):
    import math
    if h <= 0:
        return 0.0
    h2 = h * h
    coefficient = 315.0 / (64.0 * math.pi * h**9)
    total = 0.0
    for neighbor in positions:
        dx = position[0] - neighbor[0]
        dy = position[1] - neighbor[1]
        dz = position[2] - neighbor[2]
        distance2 = dx * dx + dy * dy + dz * dz
        if distance2 < h2:
            term = h2 - distance2
            total += mass * coefficient * term**3
    return total
```

Include clustered, uniformly distributed, coincident, empty, singleton, and tail-sized inputs.
The all-pairs baseline should be compared with a spatial-hash implementation before any
performance optimization is accepted.
