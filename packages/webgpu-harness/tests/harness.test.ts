import test from "node:test";
import assert from "node:assert/strict";
import { validateHarnessJob, type HarnessJob } from "../src/index.js";

const validJob: HarnessJob = {
  artifact: {
    wgsl_code: "@compute @workgroup_size(1) fn main() {}",
    entry_point: "main",
    bind_group_layouts: [],
    dispatch_size: [1, 1, 1],
  },
};

test("validates duplicate bindings and unsafe dispatches before browser startup", () => {
  const job: HarnessJob = {
    ...validJob,
    artifact: {
      ...validJob.artifact,
      dispatch_size: [2, 1, 1],
      bind_group_layouts: [
        { group: 0, binding: 0, name: "a", resource_type: "storage_read", visibility: ["compute"] },
        { group: 0, binding: 0, name: "b", resource_type: "storage_read", visibility: ["compute"] },
      ],
    },
    maxDispatchInvocations: 1,
  };
  const issues = validateHarnessJob(job);
  assert.ok(issues.some((issue) => issue.code === "dispatch-budget"));
  assert.ok(issues.some((issue) => issue.code === "duplicate-binding"));
});

test("rejects output bindings that are not declared", () => {
  const issues = validateHarnessJob({ ...validJob, outputBindings: [4] });
  assert.deepEqual(issues.map((issue) => issue.code), ["unknown-output"]);
});