export type ErrorCode =
  | "VALIDATION_FAILED"
  | "AUTH_TOKEN_INVALID"
  | "AUTH_TOKEN_EXPIRED"
  | "RESOURCE_NOT_FOUND"
  | "IMAGE_INVALID"
  | "RATE_LIMITED"
  | "KTO_API_UNAVAILABLE"
  | "OAUTH_PROVIDER_UNAVAILABLE"
  | "OAUTH_ID_TOKEN_INVALID"
  | "AUTH_SESSION_REVOKED"
  | "AGENT_FESTIVAL_UNAVAILABLE"
  | "AGENT_INTENT_UNAVAILABLE"
  | "AGENT_NO_RESULTS"
  | "AGENT_OUT_OF_SCOPE"
  | "AGENT_WRITER_UNAVAILABLE"
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
