export type ValidationIssue = {
  type: "uncaptured-error" | "validation" | "out-of-memory" | "internal";
  message: string;
};

export class ValidationScope {
  private readonly issues: ValidationIssue[] = [];
  private readonly listener: (event: Event) => void;
  private closed = false;

  private constructor(private readonly device: GPUDevice) {
    this.listener = (event: Event) => {
      const error = (event as GPUUncapturedErrorEvent).error;
      this.issues.push({
        type: error instanceof GPUOutOfMemoryError ? "out-of-memory" : "uncaptured-error",
        message: error.message,
      });
    };
    device.addEventListener("uncapturederror", this.listener);
  }

  static async run<T>(device: GPUDevice, operation: () => Promise<T>): Promise<{ value?: T; issues: ValidationIssue[] }> {
    const scope = new ValidationScope(device);
    try {
      const value = await operation();
      await device.queue.onSubmittedWorkDone();
      return { value, issues: scope.issues };
    } catch (error) {
      scope.issues.push({ type: "internal", message: error instanceof Error ? error.message : String(error) });
      return { issues: scope.issues };
    } finally {
      scope.close();
    }
  }

  private close(): void {
    if (!this.closed) {
      this.device.removeEventListener("uncapturederror", this.listener);
      this.closed = true;
    }
  }
}
