import { AppError } from "@/lib/app-error";
import { accountDeletion } from "@/features/auth/account-deletion";

describe("accountDeletion", () => {
  it("offers four reasons and lets the user decline one", () => {
    expect(accountDeletion.reasons.map((reason) => reason.label)).toEqual([
      "가고 싶던 곳을 다 찾았어요",
      "여행 앱을 잠시 쉬려고요",
      "추천이 취향과 맞지 않아요",
      "말하고 싶지 않아요",
    ]);
  });

  it("keeps reason codes stable and unique for the server", () => {
    const codes = accountDeletion.reasons.map((reason) => reason.code);

    expect(codes).toEqual([
      "found_everything",
      "taking_a_break",
      "poor_recommendations",
      "declined",
    ]);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it("states the loss only where the decision is made", () => {
    expect(accountDeletion.reasonPrompt).toBe("떠나시는 이유 (선택)");
    expect(accountDeletion.confirmTitle).toBe("정말 탈퇴할까요?");
    expect(accountDeletion.confirmBody).toBe(
      "계정과 저장한 장소가 모두 삭제돼요. 되돌릴 수 없어요.",
    );
  });

  it("maps known application error codes without exposing server messages", () => {
    const error = new AppError("AUTH_TOKEN_INVALID", "server detail", 401);

    expect(accountDeletion.errorMessage(error)).toBe(
      "로그인이 만료됐어요. 다시 로그인한 뒤 시도해 주세요.",
    );
  });
});
