import { createHash } from "node:crypto";

export type ReproducibilityManifest = {
  schemaVersion: 1;
  shaderHash: string;
  artifactHash: string;
  workloadHash: string;
  configurationHash: string;
  createdAt: string;
  dispatchSize: [number, number, number];
  warmupIterations: number;
  measuredIterations: number;
  seed?: number;
};

function sha256(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

export function createManifest(input: {
  artifact: unknown;
  shaderSource: string;
  workload: unknown;
  configuration: unknown;
  dispatchSize: [number, number, number];
  warmupIterations: number;
  measuredIterations: number;
  seed?: number;
}): ReproducibilityManifest {
  return {
    schemaVersion: 1,
    shaderHash: sha256(input.shaderSource),
    artifactHash: sha256(input.artifact),
    workloadHash: sha256(input.workload),
    configurationHash: sha256(input.configuration),
    createdAt: new Date().toISOString(),
    dispatchSize: input.dispatchSize,
    warmupIterations: input.warmupIterations,
    measuredIterations: input.measuredIterations,
    ...(input.seed === undefined ? {} : { seed: input.seed }),
  };
}
