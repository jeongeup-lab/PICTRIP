import { AppError, type ErrorCode } from "@/lib/app-error";

const MESSAGES: Partial<Record<ErrorCode, string>> = {
  AGENT_INTENT_UNAVAILABLE: "지금은 질문을 이해하지 못했어요. 잠시 후 다시 시도해 주세요.",
  AGENT_NO_RESULTS: "조건에 맞는 곳을 찾지 못했어요. 조건을 조금 넓혀서 다시 물어봐 주세요.",
  IMAGE_INVALID: "이 사진은 읽을 수 없어요. 다른 사진으로 시도해 주세요.",
  VALIDATION_FAILED: "요청을 처리하지 못했어요. 질문을 조금 바꿔서 다시 물어봐 주세요.",
  RATE_LIMITED: "요청이 너무 잦아요. 잠시 후 다시 시도해 주세요.",
  KTO_API_UNAVAILABLE: "관광 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
  NETWORK_ERROR: "네트워크에 연결할 수 없어요. 연결을 확인해 주세요.",
};

const FALLBACK = "답을 만들지 못했어요. 잠시 후 다시 시도해 주세요.";

export const PHOTO_PICK_FAILED = "사진을 불러오지 못했어요. 사진 접근 권한을 확인해 주세요.";

export function agentErrorMessage(error: unknown): string {
  if (!(error instanceof AppError)) return FALLBACK;
  return MESSAGES[error.code] ?? FALLBACK;
}
