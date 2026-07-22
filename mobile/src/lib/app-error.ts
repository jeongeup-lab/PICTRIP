export type ErrorCode =
  | "VALIDATION_FAILED"
  | "AUTH_TOKEN_INVALID"
  | "AUTH_TOKEN_EXPIRED"
  | "GUEST_FORBIDDEN"
  | "PERMISSION_DENIED"
  | "RESOURCE_NOT_FOUND"
  | "DUPLICATE_RESOURCE"
  | "IMAGE_INVALID"
  | "RATE_LIMITED"
  | "KTO_API_UNAVAILABLE"
  | "LBS_CONSENT_REQUIRED"
  | "OAUTH_PROVIDER_UNAVAILABLE"
  | "OAUTH_ID_TOKEN_INVALID"
  | "EMAIL_TAKEN"
  | "AUTH_INVALID_CREDENTIALS"
  | "AUTH_SESSION_REVOKED"
  | "SESSION_STORE_UNAVAILABLE"
  | "PLAN_SOURCE_INVALID"
  | "PLAN_TRANSCRIPT_UNAVAILABLE"
  | "PLAN_TRANSCRIPT_THIN"
  | "PLAN_NO_PLACES_FOUND"
  | "PLAN_LLM_UNAVAILABLE"
  | "PLAN_LLM_BUSY"
  | "PLAN_NOT_FOUND"
  | "PLAN_NOT_ENOUGH_SPOTS"
  | "PLAN_SPOT_NOT_FOUND"
  | "PLAN_SLOT_INVALID"
  | "INTERNAL_ERROR"
  | "NETWORK_ERROR"
  | "UNKNOWN";

export interface ErrorDetail {
  field: string;
  issue: string;
}

export class AppError extends Error {
  code: ErrorCode;
  status: number;
  details?: ErrorDetail[];

  constructor(code: ErrorCode, message: string, status: number, details?: ErrorDetail[]) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}
