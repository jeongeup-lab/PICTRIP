import type { Envelope } from "@/lib/api-types";
import { AppError, type ErrorCode } from "@/lib/app-error";

export function unwrapData<T>(envelope: Envelope<T>): T {
  return envelope.data as T;
}

export function envelopeToError(envelope: Envelope<unknown>, status: number): AppError {
  const payload = envelope?.error;
  if (!payload) {
    return new AppError("UNKNOWN", "Unexpected error.", status);
  }
  return new AppError(
    payload.code as ErrorCode,
    payload.message,
    status,
    (payload as { details?: { field: string; issue: string }[] }).details,
  );
}
