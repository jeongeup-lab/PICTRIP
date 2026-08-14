import { AppError } from "@/lib/app-error";
import { accountDeletion } from "@/features/auth/account-deletion";

describe("accountDeletion", () => {
  it("describes empty and populated saved lists", () => {
    expect(accountDeletion.losses(0)[0]).toBe("스크랩이 모두 삭제돼요");
    expect(accountDeletion.losses(3)[0]).toBe("스크랩 3개가 삭제돼요");
  });

  it("maps known application error codes without exposing server messages", () => {
    const error = new AppError("AUTH_TOKEN_INVALID", "server detail", 401);

    expect(accountDeletion.errorMessage(error)).toBe(
      "로그인이 만료됐어요. 다시 로그인한 뒤 시도해 주세요.",
    );
  });
});
