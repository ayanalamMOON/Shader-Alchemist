import { BufferAllocator } from "./profiler/buffer-allocator.js";
import { requestDevice, type CapabilityProfile } from "./profiler/device.js";
import { TimestampQuery } from "./profiler/query-set.js";
import { ValidationScope, type ValidationIssue } from "./profiler/validation-scope.js";
import { monotonicNowMs, summarizeSamples } from "./utils/time.js";
import { validateHarnessJob } from "./validation.js";

export type HarnessArtifact = {
  wgsl_code: string;
  entry_point: string;
  bind_group_layouts: Array<{
    group: number; binding: number; name: string;
    resource_type: "storage_read" | "storage_read_write" | "uniform";
    visibility: Array<"compute" | "vertex" | "fragment">;
    min_binding_size?: number;
  }>;
  dispatch_size: [number, number, number];
  required_features?: string[];
  math_spec?: { domain?: Record<string, unknown>; grid_dispatch_dimensions?: [number, number, number] };
  metadata?: Record<string, string | number | boolean>;
};

export type HarnessBuffer = {
  group?: number;
  binding: number;
  data?: number[] | string;
  byteLength?: number;
};

export type HarnessJob = {
  artifact: HarnessArtifact;
  buffers?: HarnessBuffer[];
  outputBindings?: number[];
  warmupIterations?: number;
  measuredIterations?: number;
  maxDispatchInvocations?: number;
  maxBufferBytes?: number;
  targetBudgetMs?: number;
};

export type HarnessResult = {
  pipeline_creation_success: boolean;
  validation_errors: string[];
  execution_time_ms: number | null;
  alignment_warnings: string[];
  metadata: Record<string, unknown>;
  capability_profile?: CapabilityProfile;
  timing?: ReturnType<typeof summarizeSamples>;
  timestamp_query_supported?: boolean;
  samples_ms?: number[];
  output_buffers?: Record<string, string>;
};

function failure(issues: string[], phase: string, extra: Record<string, unknown> = {}): HarnessResult {
  return { pipeline_creation_success: false, validation_errors: issues, alignment_warnings: [], execution_time_ms: null, metadata: { phase, ...extra } };
}

function decodeData(data: number[] | string | undefined, byteLength: number): Uint8Array<ArrayBuffer> {
  if (Array.isArray(data)) {
    const values = new Float32Array(data);
    const bytes = new Uint8Array(new ArrayBuffer(values.byteLength));
    bytes.set(new Uint8Array(values.buffer));
    return bytes;
  }
  if (typeof data === "string") {
    const binary = atob(data);
    const bytes = new Uint8Array(new ArrayBuffer(binary.length));
    for (let index = 0; index < binary.length; index++) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }
  return new Uint8Array(new ArrayBuffer(byteLength));
}

export async function executeInBrowser(job: HarnessJob): Promise<HarnessResult> {
  const artifact = job?.artifact;
  const validationErrors = validateHarnessJob(job).map((issue) => `${issue.code}: ${issue.message}`);
  if (validationErrors.length) return {
    ...failure(validationErrors, "preflight", { diagnostic_count: validationErrors.length }),
  };
  if (!artifact) return failure(["missing-artifact: artifact is required"], "preflight");

  let device: GPUDevice;
  let profile: CapabilityProfile;
  try {
    ({ device, profile } = await requestDevice(artifact.required_features ?? []));
  } catch (error) {
    return failure([error instanceof Error ? error.message : String(error)], "device-request");
  }
  const allocator = new BufferAllocator(device, job.maxBufferBytes ?? 256 * 1024 * 1024);
  const query = TimestampQuery.create(device);
  const errors: ValidationIssue[] = [];
  try {
    const shader = device.createShaderModule({ label: "shader-alchemist-candidate", code: artifact.wgsl_code });
    const moduleInfo = await shader.getCompilationInfo();
    for (const message of moduleInfo.messages) {
      if (message.type === "error") errors.push({ type: "validation", message: `WGSL ${message.lineNum}:${message.linePos}: ${message.message}` });
    }
    if (errors.length) return result(false, errors, profile, query.supported);
    const groups = [...new Set(artifact.bind_group_layouts.map((binding) => binding.group))].sort((a, b) => a - b);
    if (groups.some((group, index) => group !== index)) {
      return result(false, [{ type: "validation", message: "bind groups must be contiguous starting at group 0" }], profile, query.supported);
    }
    const layouts = groups.map((group) => device.createBindGroupLayout({
      entries: artifact.bind_group_layouts.filter((binding) => binding.group === group).map((binding) => ({
        binding: binding.binding,
        visibility: binding.visibility.reduce((mask, stage) => mask | ({ compute: GPUShaderStage.COMPUTE, vertex: GPUShaderStage.VERTEX, fragment: GPUShaderStage.FRAGMENT }[stage] ?? 0), 0),
        buffer: { type: binding.resource_type === "uniform" ? "uniform" : binding.resource_type === "storage_read" ? "read-only-storage" : "storage", ...(binding.min_binding_size === undefined ? {} : { minBindingSize: binding.min_binding_size }) },
      })),
    }));
    const pipeline = device.createComputePipeline({ layout: device.createPipelineLayout({ bindGroupLayouts: layouts }), compute: { module: shader, entryPoint: artifact.entry_point } });
    const requests = artifact.bind_group_layouts.map((binding) => {
      const supplied = job.buffers?.find((item) => (item.group ?? 0) === binding.group && item.binding === binding.binding);
      const byteLength = supplied?.byteLength ?? binding.min_binding_size ?? 4;
      return { binding, supplied, buffer: allocator.create({ label: binding.name, size: Math.max(byteLength, 4), usage: GPUBufferUsage.STORAGE | GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC }) };
    });
    for (const item of requests) {
      if (item.supplied?.data !== undefined) device.queue.writeBuffer(item.buffer, 0, decodeData(item.supplied.data, item.buffer.size));
    }
    const bindGroups = layouts.map((layout, group) => device.createBindGroup({
      layout,
      entries: requests.filter((item) => item.binding.group === group).map((item) => ({ binding: item.binding.binding, resource: { buffer: item.buffer } })),
    }));
    const warmups = Math.max(0, Math.floor(job.warmupIterations ?? 2));
    const measured = Math.max(1, Math.floor(job.measuredIterations ?? 10));
    const runtimeIssues: ValidationIssue[] = [];
    for (let i = 0; i < warmups; i++) {
      const execution = await ValidationScope.run(device, () => dispatch(device, pipeline, bindGroups, artifact.dispatch_size, null));
      runtimeIssues.push(...execution.issues);
      if (execution.issues.length) throw new Error(execution.issues.map((issue) => issue.message).join("; "));
    }
    const samples: number[] = [];
    for (let i = 0; i < measured; i++) {
      const start = monotonicNowMs();
      const execution = await ValidationScope.run(device, () => dispatch(device, pipeline, bindGroups, artifact.dispatch_size, query));
      runtimeIssues.push(...execution.issues);
      if (execution.issues.length) throw new Error(execution.issues.map((issue) => issue.message).join("; "));
      const elapsed = monotonicNowMs() - start;
      samples.push(elapsed);
    }
    const summary = summarizeSamples(samples);
    const output = await readOutputs(device, requests, job.outputBindings ?? []);
    errors.push(...runtimeIssues);
    return { pipeline_creation_success: errors.length === 0, validation_errors: errors.map((item) => item.message), alignment_warnings: [], execution_time_ms: summary.medianMs, metadata: { phase: "execution", warmup_iterations: warmups, measured_iterations: measured, allocated_buffer_bytes: allocator.bytesAllocated, target_budget_ms: job.targetBudgetMs ?? null, diagnostic_count: errors.length }, capability_profile: profile, timing: summary, timestamp_query_supported: query.supported, samples_ms: samples, output_buffers: output };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return result(false, [{ type: "internal", message: `execution failed: ${message}` }], profile, query.supported);
  } finally {
    query.dispose();
    allocator.dispose();
    device.destroy();
  }
}

async function dispatch(device: GPUDevice, pipeline: GPUComputePipeline, bindGroups: GPUBindGroup[], dispatch: [number, number, number], query: TimestampQuery | null): Promise<void> {
  const encoder = device.createCommandEncoder();
  const pass = encoder.beginComputePass(query?.passDescriptor);
  pass.setPipeline(pipeline);
  bindGroups.forEach((bindGroup, index) => pass.setBindGroup(index, bindGroup));
  pass.dispatchWorkgroups(...dispatch);
  pass.end();
  query?.resolve(encoder);
  device.queue.submit([encoder.finish()]);
  await device.queue.onSubmittedWorkDone();
  if (query) await query.readNanoseconds();
}

async function readOutputs(device: GPUDevice, requests: Array<{ binding: HarnessArtifact["bind_group_layouts"][number]; buffer: GPUBuffer }>, outputBindings: number[]): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  for (const item of requests.filter((entry) => outputBindings.includes(entry.binding.binding))) {
    const read = device.createBuffer({ size: item.buffer.size, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    const encoder = device.createCommandEncoder();
    encoder.copyBufferToBuffer(item.buffer, 0, read, 0, item.buffer.size);
    device.queue.submit([encoder.finish()]);
    await read.mapAsync(GPUMapMode.READ);
    const bytes = new Uint8Array(read.getMappedRange()).slice();
    read.unmap(); read.destroy();
    let binary = ""; for (const byte of bytes) binary += String.fromCharCode(byte);
    result[String(item.binding.binding)] = btoa(binary);
  }
  return result;
}

function result(success: boolean, issues: ValidationIssue[], profile: CapabilityProfile, timestamp: boolean): HarnessResult {
  return { pipeline_creation_success: success, validation_errors: issues.map((item) => item.message), alignment_warnings: [], execution_time_ms: null, metadata: { phase: "pipeline" }, capability_profile: profile, timestamp_query_supported: timestamp };
}
