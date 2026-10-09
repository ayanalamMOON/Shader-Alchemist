export type BufferRequest = {
  label: string;
  size: number;
  usage: GPUBufferUsageFlags;
  mappedAtCreation?: boolean;
};

export class BufferBudgetExceededError extends Error {}

export class BufferAllocator {
  private allocated = 0;
  private readonly buffers: GPUBuffer[] = [];

  constructor(private readonly device: GPUDevice, private readonly maxBytes = 256 * 1024 * 1024) {}

  create(request: BufferRequest): GPUBuffer {
    if (!Number.isInteger(request.size) || request.size <= 0) throw new RangeError(`${request.label}: size must be positive`);
    const size = Math.ceil(request.size / 4) * 4;
    if (this.allocated + size > this.maxBytes) {
      throw new BufferBudgetExceededError(`buffer budget exceeded by ${request.label}`);
    }
    const buffer = this.device.createBuffer({
      label: request.label,
      size,
      usage: request.usage,
      ...(request.mappedAtCreation === undefined ? {} : { mappedAtCreation: request.mappedAtCreation }),
    });
    this.allocated += buffer.size;
    this.buffers.push(buffer);
    return buffer;
  }

  get bytesAllocated(): number { return this.allocated; }

  dispose(): void {
    for (const buffer of this.buffers) buffer.destroy();
    this.buffers.length = 0;
    this.allocated = 0;
  }
}
