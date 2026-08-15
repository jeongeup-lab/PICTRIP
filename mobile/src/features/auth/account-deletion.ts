import { AppError } from "@/lib/app-error";

const losses = (savedCount: number): readonly string[] => [
  savedCount > 0 ? `저장한 장소 ${savedCount}곳` : "저장한 장소",
  "취향에 맞춘 추천",
  "계정 정보와 로그인 연결",
];

const errorMessage = (error: unknown): string => {
  if (!(error instanceof AppError)) return "탈퇴 처리에 실패했어요. 잠시 후 다시 시도해 주세요.";
  switch (error.code) {
    case "AUTH_TOKEN_INVALID":
    case "AUTH_TOKEN_EXPIRED":
    case "AUTH_SESSION_REVOKED":
      return "로그인이 만료됐어요. 다시 로그인한 뒤 시도해 주세요.";
    case "NETWORK_ERROR":
      return "네트워크가 불안정해요. 잠시 후 다시 시도해 주세요.";
    default:
      return "탈퇴 처리에 실패했어요. 잠시 후 다시 시도해 주세요.";
  }
};

export const accountDeletion = {
  title: "회원 탈퇴",
  lead: "탈퇴하면 되돌릴 수 없어요.",
  acknowledgement: "확인했어요",
  losses,
  errorMessage,
} as const;
