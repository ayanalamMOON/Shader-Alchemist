#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { executeInBrowser, type HarnessJob, type HarnessResult } from "./browser-runner.js";

export * from "./browser-runner.js";
export * from "./profiler/device.js";
export * from "./profiler/buffer-allocator.js";
export * from "./profiler/query-set.js";
export * from "./profiler/validation-scope.js";
export * from "./utils/time.js";
export * from "./correctness/comparator.js";
export * from "./reproducibility.js";
export * from "./validation.js";

type BrowserPage = { evaluate: (fn: (job: HarnessJob) => Promise<HarnessResult>, job: HarnessJob) => Promise<HarnessResult>; close: () => Promise<void> };

async function run(): Promise<void> {
  const input = process.argv[2];
  if (!input) {
    process.stderr.write("Usage: shader-alchemist-webgpu <artifact-json-or-file>\n");
    process.exitCode = 2;
    return;
  }
  let job: HarnessJob;
  try {
    const raw = input.trim().startsWith("{") ? input : await readFile(input, "utf8");
    job = JSON.parse(raw) as HarnessJob;
  } catch (error) {
    writeFailure("input", error);
    process.exitCode = 2;
    return;
  }
  let page: BrowserPage | undefined;
  try {
    page = await createBrowserPage();
    const result = await page.evaluate(executeInBrowser, job);
    process.stdout.write(`${JSON.stringify(result)}\n`);
    process.exitCode = result.pipeline_creation_success && result.validation_errors.length === 0 ? 0 : 1;
  } catch (error) {
    writeFailure("host", error);
    process.exitCode = 1;
  } finally {
    if (page) await page.close();
  }
}

function writeFailure(phase: string, error: unknown): void {
  process.stdout.write(`${JSON.stringify({ pipeline_creation_success: false, validation_errors: [error instanceof Error ? error.message : String(error)], alignment_warnings: [], execution_time_ms: null, metadata: { phase } })}\n`);
}

async function createBrowserPage(): Promise<BrowserPage> {
  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setContent("<!doctype html><html><body></body></html>");
  return {
    evaluate: (fn, job) => page.evaluate(fn, job),
    close: async () => { await page.close(); await browser.close(); },
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) void run();
