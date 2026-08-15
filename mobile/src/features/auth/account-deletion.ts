import { AppError } from "@/lib/app-error";

const losses = (savedCount: number): readonly string[] => [
  savedCount > 0 ? `스크랩 ${savedCount}개가 삭제돼요` : "스크랩이 모두 삭제돼요",
  "PicTrip에 저장된 소셜 로그인 연결 정보가 삭제돼요",
  "PicTrip에 저장된 닉네임, 이메일 등 계정 정보가 삭제돼요",
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
  eyebrow: "계정과 데이터",
  heading: "계정을 삭제할까요?",
  lead: "탈퇴하면 PicTrip에 저장된 아래 데이터가 즉시 삭제되며 복구할 수 없어요.",
  consequencesLabel: "삭제되는 PicTrip 데이터",
  irreversibleNotice: "탈퇴 후 PicTrip에 저장된 데이터는 다시 복구할 수 없어요.",
  acknowledgement: "위 내용을 확인했고, PicTrip에 저장된 데이터를 복구할 수 없음을 이해했어요.",
  losses,
  errorMessage,
} as const;
