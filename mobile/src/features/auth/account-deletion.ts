import { AppError } from "@/lib/app-error";

export interface DeletionReason {
  readonly code: string;
  readonly label: string;
}

const reasons: readonly DeletionReason[] = [
  { code: "found_everything", label: "가고 싶던 곳을 다 찾았어요" },
  { code: "taking_a_break", label: "여행 앱을 잠시 쉬려고요" },
  { code: "poor_recommendations", label: "추천이 취향과 맞지 않아요" },
  { code: "declined", label: "말하고 싶지 않아요" },
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
  reasonPrompt: "떠나시는 이유 (선택)",
  submitLabel: "탈퇴하기",
  pendingLabel: "탈퇴 처리 중…",
  confirmTitle: "정말 탈퇴할까요?",
  confirmBody: "계정과 저장한 장소가 모두 삭제돼요. 되돌릴 수 없어요.",
  cancelLabel: "취소",
  reasons,
  errorMessage,
} as const;
