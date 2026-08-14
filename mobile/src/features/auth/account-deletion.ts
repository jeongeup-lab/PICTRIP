import { AppError } from "@/lib/app-error";

const losses = (savedCount: number): readonly string[] => [
  savedCount > 0 ? `스크랩 ${savedCount}개가 삭제돼요` : "스크랩이 모두 삭제돼요",
  "소셜 로그인 연결이 해제돼요",
  "닉네임·이메일 등 계정 정보가 지워져요",
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
  lead: "탈퇴하면 다음이 즉시 사라지고 되돌릴 수 없어요.",
  losses,
  errorMessage,
} as const;
