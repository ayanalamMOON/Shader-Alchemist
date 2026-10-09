export function monotonicNowMs(): number {
  return typeof performance !== "undefined"
    ? performance.now()
    : Number(process.hrtime.bigint()) / 1_000_000;
}

export function percentile(values: readonly number[], p: number): number | null {
  if (values.length === 0) return null;
  if (!Number.isFinite(p) || p < 0 || p > 1) throw new RangeError("p must be in [0, 1]");
  const sorted = [...values].sort((a, b) => a - b);
  const index = (sorted.length - 1) * p;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const a = sorted[lower];
  const b = sorted[upper];
  if (a === undefined || b === undefined) return null;
  return a + (b - a) * (index - lower);
}

export function summarizeSamples(samples: readonly number[]): {
  count: number; minMs: number | null; maxMs: number | null;
  meanMs: number | null; medianMs: number | null; p95Ms: number | null; p99Ms: number | null;
} {
  if (!samples.length) {
    return { count: 0, minMs: null, maxMs: null, meanMs: null, medianMs: null, p95Ms: null, p99Ms: null };
  }
  return {
    count: samples.length,
    minMs: Math.min(...samples),
    maxMs: Math.max(...samples),
    meanMs: samples.reduce((sum, value) => sum + value, 0) / samples.length,
    medianMs: percentile(samples, 0.5),
    p95Ms: percentile(samples, 0.95),
    p99Ms: percentile(samples, 0.99),
  };
}
