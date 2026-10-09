import type { HarnessJob } from "./browser-runner.js";

export type JobValidationIssue = {
  code: string;
  message: string;
  path?: string;
};

const positiveInteger = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value > 0;

export function validateHarnessJob(job: HarnessJob): JobValidationIssue[] {
  const issues: JobValidationIssue[] = [];
  const artifact = job?.artifact;
  if (!artifact || typeof artifact !== "object") {
    return [{ code: "missing-artifact", message: "artifact is required", path: "artifact" }];
  }
  if (typeof artifact.wgsl_code !== "string" || !artifact.wgsl_code.trim()) {
    issues.push({ code: "empty-shader", message: "WGSL source is empty", path: "artifact.wgsl_code" });
  }
  if (typeof artifact.entry_point !== "string" || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(artifact.entry_point)) {
    issues.push({ code: "invalid-entry-point", message: "entry_point must be a valid WGSL identifier", path: "artifact.entry_point" });
  }
  if (!Array.isArray(artifact.dispatch_size) || artifact.dispatch_size.length !== 3 ||
      artifact.dispatch_size.some((value) => !positiveInteger(value))) {
    issues.push({ code: "invalid-dispatch", message: "dispatch_size must contain three positive safe integers", path: "artifact.dispatch_size" });
  } else {
    const invocations = artifact.dispatch_size.reduce((a, b) => a * b, 1);
    const limit = job.maxDispatchInvocations ?? 16_777_216;
    if (!positiveInteger(limit)) issues.push({ code: "invalid-dispatch-budget", message: "maxDispatchInvocations must be a positive safe integer", path: "maxDispatchInvocations" });
    else if (invocations > limit) issues.push({ code: "dispatch-budget", message: `dispatch exceeds configured invocation budget (${invocations} > ${limit})`, path: "artifact.dispatch_size" });
  }
  const bindings = artifact.bind_group_layouts;
  if (!Array.isArray(bindings)) issues.push({ code: "missing-bindings", message: "bind_group_layouts must be an array", path: "artifact.bind_group_layouts" });
  else {
    const seen = new Set<string>();
    for (const [index, binding] of bindings.entries()) {
      const path = `artifact.bind_group_layouts[${index}]`;
      if (!binding || typeof binding !== "object") {
        issues.push({ code: "invalid-binding", message: "binding must be an object", path });
        continue;
      }
      if (!positiveInteger(binding.group) && binding.group !== 0) issues.push({ code: "invalid-group", message: "group must be a non-negative safe integer", path: `${path}.group` });
      if (!positiveInteger(binding.binding) && binding.binding !== 0) issues.push({ code: "invalid-binding", message: "binding must be a non-negative safe integer", path: `${path}.binding` });
      const key = `${binding.group}:${binding.binding}`;
      if (seen.has(key)) issues.push({ code: "duplicate-binding", message: `duplicate binding ${key}`, path });
      seen.add(key);
      if (!binding.name?.trim()) issues.push({ code: "missing-binding-name", message: "binding name is required", path: `${path}.name` });
      if (!binding.visibility?.length) issues.push({ code: "missing-visibility", message: "binding visibility cannot be empty", path: `${path}.visibility` });
      if (binding.min_binding_size !== undefined &&
          (!positiveInteger(binding.min_binding_size) || binding.min_binding_size % 4 !== 0)) {
        issues.push({ code: "invalid-binding-size", message: "min_binding_size must be a positive multiple of 4", path: `${path}.min_binding_size` });
      }
    }
  }
  if (job.buffers !== undefined && !Array.isArray(job.buffers)) {
    issues.push({ code: "invalid-buffers", message: "buffers must be an array", path: "buffers" });
  }
  for (const [index, buffer] of (Array.isArray(job.buffers) ? job.buffers : []).entries()) {
    const path = `buffers[${index}]`;
    if (!buffer || typeof buffer !== "object") {
      issues.push({ code: "invalid-buffer", message: "buffer must be an object", path });
      continue;
    }
    if (!positiveInteger(buffer.binding) && buffer.binding !== 0) issues.push({ code: "invalid-buffer-binding", message: "binding must be a non-negative safe integer", path });
    if (buffer.byteLength !== undefined && (!positiveInteger(buffer.byteLength) || buffer.byteLength % 4 !== 0)) {
      issues.push({ code: "invalid-buffer-size", message: "byteLength must be a positive multiple of 4", path: `${path}.byteLength` });
    }
    if (Array.isArray(buffer.data) && buffer.byteLength !== undefined && buffer.data.length * 4 > buffer.byteLength) {
      issues.push({ code: "buffer-data-too-large", message: "buffer data does not fit byteLength", path });
    }
  }
  for (const [name, value] of [["warmupIterations", job.warmupIterations], ["measuredIterations", job.measuredIterations]] as const) {
    if (value !== undefined && (!Number.isSafeInteger(value) || value < 0)) issues.push({ code: "invalid-iterations", message: `${name} must be a non-negative safe integer`, path: name });
  }
  if (job.measuredIterations === 0) issues.push({ code: "no-measurements", message: "measuredIterations must be at least 1", path: "measuredIterations" });
  if (job.maxBufferBytes !== undefined && (!positiveInteger(job.maxBufferBytes) || job.maxBufferBytes % 4 !== 0)) {
    issues.push({ code: "invalid-buffer-budget", message: "maxBufferBytes must be a positive multiple of 4", path: "maxBufferBytes" });
  }
  if (job.targetBudgetMs !== undefined && (!Number.isFinite(job.targetBudgetMs) || job.targetBudgetMs <= 0)) {
    issues.push({ code: "invalid-target-budget", message: "targetBudgetMs must be a positive finite number", path: "targetBudgetMs" });
  }
  if (artifact.required_features?.some((feature) => typeof feature !== "string" || !feature.trim())) {
    issues.push({ code: "invalid-feature", message: "required_features must contain non-empty strings", path: "artifact.required_features" });
  }
  if (job.outputBindings !== undefined && !Array.isArray(job.outputBindings)) {
    issues.push({ code: "invalid-outputs", message: "outputBindings must be an array", path: "outputBindings" });
  }
  const requestedOutputs = new Set(Array.isArray(job.outputBindings) ? job.outputBindings : []);
  for (const binding of requestedOutputs) {
    if (!bindings?.some((item) => item.binding === binding)) issues.push({ code: "unknown-output", message: `output binding ${binding} is not declared`, path: "outputBindings" });
  }
  return issues;
}
