export class TimestampQuery {
  readonly supported: boolean;
  readonly querySet: GPUQuerySet | null;
  readonly resolveBuffer: GPUBuffer | null;
  readonly readBuffer: GPUBuffer | null;

  private constructor(
    private readonly device: GPUDevice,
    count: number,
    supported: boolean,
    querySet: GPUQuerySet | null,
    resolveBuffer: GPUBuffer | null,
    readBuffer: GPUBuffer | null,
  ) {
    this.supported = supported;
    this.querySet = querySet;
    this.resolveBuffer = resolveBuffer;
    this.readBuffer = readBuffer;
  }

  static create(device: GPUDevice, count = 2): TimestampQuery {
    const supported = device.features.has("timestamp-query");
    if (!supported) return new TimestampQuery(device, count, false, null, null, null);
    const querySet = device.createQuerySet({ type: "timestamp", count });
    const resolveBuffer = device.createBuffer({
      size: count * 8,
      usage: GPUBufferUsage.QUERY_RESOLVE | GPUBufferUsage.COPY_SRC,
    });
    const readBuffer = device.createBuffer({
      size: count * 8,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    });
    return new TimestampQuery(device, count, true, querySet, resolveBuffer, readBuffer);
  }

  get passDescriptor(): GPUComputePassDescriptor {
    return this.querySet
      ? {
          timestampWrites: {
            querySet: this.querySet,
            beginningOfPassWriteIndex: 0,
            endOfPassWriteIndex: 1,
          },
        }
      : {};
  }

  resolve(encoder: GPUCommandEncoder): void {
    if (this.querySet && this.resolveBuffer && this.readBuffer) {
      encoder.resolveQuerySet(this.querySet, 0, 2, this.resolveBuffer, 0);
      encoder.copyBufferToBuffer(this.resolveBuffer, 0, this.readBuffer, 0, 16);
    }
  }

  async readNanoseconds(): Promise<number | null> {
    if (!this.readBuffer || !this.resolveBuffer) return null;
    await this.readBuffer.mapAsync(GPUMapMode.READ);
    const values = new BigUint64Array(this.readBuffer.getMappedRange());
    const start = values[0];
    const end = values[1];
    if (start === undefined || end === undefined) {
      this.readBuffer.unmap();
      return null;
    }
    const elapsed = Number(end - start);
    this.readBuffer.unmap();
    return Number.isFinite(elapsed) && elapsed >= 0 ? elapsed : null;
  }

  dispose(): void {
    this.querySet?.destroy();
    this.resolveBuffer?.destroy();
    this.readBuffer?.destroy();
  }
}
