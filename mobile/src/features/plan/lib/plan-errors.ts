import { AppError, type ErrorCode } from "@/lib/app-error";

const MESSAGES: Partial<Record<ErrorCode, string>> = {
  PLAN_SOURCE_INVALID: "지원하지 않는 입력이에요. 유튜브 링크나 사진으로 다시 시도해 주세요.",
  PLAN_TRANSCRIPT_UNAVAILABLE:
    "이 영상에서는 자막을 가져올 수 없어요. 다른 영상으로 시도해 주세요.",
  PLAN_TRANSCRIPT_THIN:
    "이 영상은 음성 자막이 거의 없어 장소를 찾지 못했어요. 화면 글씨는 읽지 못하고 말로 소개한 내용만 이해할 수 있어요.",
  PLAN_NO_PLACES_FOUND:
    "콘텐츠에서 장소 이름을 찾지 못했어요. 장소명이 나오는 콘텐츠를 보내주세요.",
  PLAN_LLM_BUSY: "요청이 몰려 있어요. 1분쯤 후 다시 시도해 주세요.",
  PLAN_LLM_UNAVAILABLE: "장소 추출 서비스가 잠시 응답하지 않아요. 잠시 후 다시 시도해 주세요.",
  PLAN_NOT_FOUND: "요청한 일정을 찾을 수 없어요.",
  PLAN_NOT_ENOUGH_SPOTS: "이 주변에서 일정을 만들 만큼 장소를 찾지 못했어요.",
  PLAN_SPOT_NOT_FOUND: "선택한 장소를 찾을 수 없어요.",
  PLAN_SLOT_INVALID: "이미 바뀐 일정이에요. 다시 불러올게요.",
  IMAGE_INVALID: "이 사진은 읽을 수 없어요. 다른 사진으로 시도해 주세요.",
  RATE_LIMITED: "요청이 너무 잦아요. 잠시 후 다시 시도해 주세요.",
  NETWORK_ERROR: "네트워크에 연결할 수 없어요. 연결을 확인해 주세요.",
};

const FALLBACK = "일정을 만들지 못했어요. 잠시 후 다시 시도해 주세요.";

export function planErrorMessage(error: unknown): string {
  if (!(error instanceof AppError)) return FALLBACK;
  return MESSAGES[error.code] ?? FALLBACK;
}
