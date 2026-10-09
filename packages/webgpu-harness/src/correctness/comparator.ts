export type ComparisonResult = {
  passed: boolean;
  comparedValues: number;
  mismatches: number;
  maxAbsoluteError: number;
  maxRelativeError: number;
  firstMismatch: number | null;
  message: string;
};

export type ComparisonOptions = {
  absoluteTolerance?: number;
  relativeTolerance?: number;
  discrete?: boolean;
};

export function compareNumeric(
  actual: ArrayLike<number>,
  expected: ArrayLike<number>,
  options: ComparisonOptions = {},
): ComparisonResult {
  const atol = options.absoluteTolerance ?? 1e-6;
  const rtol = options.relativeTolerance ?? 1e-5;
  if (actual.length !== expected.length) {
    return { passed: false, comparedValues: Math.min(actual.length, expected.length), mismatches: 1, maxAbsoluteError: Infinity, maxRelativeError: Infinity, firstMismatch: Math.min(actual.length, expected.length), message: `length mismatch: actual=${actual.length}, expected=${expected.length}` };
  }
  let mismatches = 0;
  let firstMismatch: number | null = null;
  let maxAbsoluteError = 0;
  let maxRelativeError = 0;
  for (let index = 0; index < actual.length; index++) {
    const a = actual[index] ?? NaN;
    const e = expected[index] ?? NaN;
    const absolute = Math.abs(a - e);
    const relative = absolute / Math.max(Math.abs(e), Number.EPSILON);
    maxAbsoluteError = Math.max(maxAbsoluteError, absolute);
    maxRelativeError = Math.max(maxRelativeError, relative);
    const valid = Number.isFinite(a) && Number.isFinite(e) &&
      (options.discrete ? a === e : absolute <= atol + rtol * Math.abs(e));
    if (!valid) {
      mismatches++;
      if (firstMismatch === null) firstMismatch = index;
    }
  }
  return {
    passed: mismatches === 0,
    comparedValues: actual.length,
    mismatches,
    maxAbsoluteError,
    maxRelativeError,
    firstMismatch,
    message: mismatches === 0 ? "outputs match within tolerance" : `${mismatches} values exceeded tolerance`,
  };
}
