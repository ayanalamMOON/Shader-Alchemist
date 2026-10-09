# Benchmark Suite

The benchmark suite is correctness-first. A candidate is not ranked by runtime until its
artifact passes schema, static safety, binding, dispatch, and correctness checks.

## Manifest

[manifest.json](./manifest.json) contains stable workload IDs, prompts, workload sizes, expected
dispatch dimensions, tolerances, feature requirements, and default safety limits.

## Run the suite

From the repository root:

```bash
python scripts/benchmark_all_examples.py
```

Run only generation without starting a browser:

```bash
python scripts/benchmark_all_examples.py --skip-harness
```

Use a custom output directory:

```bash
python scripts/benchmark_all_examples.py \
  --output benchmark-results/local \
  --manifest benchmarks/manifest.json
```

Use the real WebGPU harness:

```bash
python scripts/benchmark_all_examples.py \
  --harness-command "node packages/webgpu-harness/dist/index.js"
```

Build the harness first:

```bash
cd packages/webgpu-harness
npm run build
cd ../..
```

## Output

Each workload produces:

```text
benchmark-results/
├── summary.json
├── vector-add-1025/
│   ├── state.json
│   ├── shader.wgsl
│   ├── report.md
│   └── static-analysis.json
└── ...
```

Failures are retained in the summary and never replaced with a success-shaped fallback.
