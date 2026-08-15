import { AppError } from "@/lib/app-error";
import { accountDeletion } from "@/features/auth/account-deletion";

describe("accountDeletion", () => {
  it("names the losses in the user's words, not ours", () => {
    expect(accountDeletion.losses(3)).toEqual([
      "저장한 장소 3곳",
      "취향에 맞춘 추천",
      "계정 정보와 로그인 연결",
    ]);
  });

  it("drops the count when nothing is saved", () => {
    expect(accountDeletion.losses(0)[0]).toBe("저장한 장소");
  });

  it("keeps the screen copy to a single sentence and a short consent", () => {
    expect(accountDeletion.lead).toBe("탈퇴하면 되돌릴 수 없어요.");
    expect(accountDeletion.acknowledgement).toBe("확인했어요");
  });

  it("maps known application error codes without exposing server messages", () => {
    const error = new AppError("AUTH_TOKEN_INVALID", "server detail", 401);

    expect(accountDeletion.errorMessage(error)).toBe(
      "로그인이 만료됐어요. 다시 로그인한 뒤 시도해 주세요.",
    );
  });
});
