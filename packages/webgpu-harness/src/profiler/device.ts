export type CapabilityProfile = {
  adapterName: string;
  vendor: string;
  architecture: string;
  description: string;
  features: string[];
  limits: Record<string, number>;
  timestampQuery: boolean;
  isFallbackAdapter: boolean;
  capturedAt: string;
};

export async function requestDevice(requiredFeatures: readonly string[] = []): Promise<{
  device: GPUDevice;
  profile: CapabilityProfile;
}> {
  if (!("gpu" in navigator)) throw new Error("WebGPU is unavailable in this browser/runtime");
  const adapter = await navigator.gpu.requestAdapter({ powerPreference: "high-performance" });
  if (!adapter) throw new Error("No WebGPU adapter was found");
  const available = new Set([...adapter.features].map(String));
  const missing = requiredFeatures.filter((feature) => !available.has(feature));
  if (missing.length) throw new Error(`Required WebGPU features are unavailable: ${missing.join(", ")}`);
  const features = [...requiredFeatures].filter(
    (feature): feature is GPUFeatureName => available.has(feature),
  );
  const device = await adapter.requestDevice({ requiredFeatures: features });
  device.lost.then((info) => console.error(`WebGPU device lost (${info.reason}): ${info.message}`));
  const adapterWithInfo = adapter as GPUAdapter & {
    info?: GPUAdapterInfo;
    isFallbackAdapter?: boolean;
  };
  const info = adapterWithInfo.info;
  const limits: Record<string, number> = {};
  for (const key of Object.keys(adapter.limits)) {
    const value = adapter.limits[key as keyof GPUSupportedLimits];
    if (typeof value === "number") limits[key] = value;
  }
  return {
    device,
    profile: {
      adapterName: info?.description || "unknown",
      vendor: info?.vendor || "unknown",
      architecture: info?.architecture || "unknown",
      description: info?.device || "WebGPU adapter",
      features: [...adapter.features].map(String).sort(),
      limits,
      timestampQuery: available.has("timestamp-query"),
      isFallbackAdapter: Boolean(adapterWithInfo.isFallbackAdapter),
      capturedAt: new Date().toISOString(),
    },
  };
}
