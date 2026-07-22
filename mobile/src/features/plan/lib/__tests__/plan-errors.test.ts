import { AppError } from "@/lib/app-error";
import { planErrorMessage } from "@/features/plan/lib/plan-errors";

describe("planErrorMessage", () => {
  it("explains that only spoken subtitles are readable when a video has none", () => {
    const message = planErrorMessage(
      new AppError("PLAN_TRANSCRIPT_THIN", "서버 문구는 쓰지 않는다", 422),
    );
    expect(message).toContain("화면 글씨는 읽지 못하고");
  });

  it("branches on the code, never on the server message", () => {
    const message = planErrorMessage(new AppError("PLAN_LLM_BUSY", "arbitrary server text", 429));
    expect(message).not.toContain("arbitrary server text");
    expect(message).toContain("1분");
  });

  it("falls back for unmapped codes", () => {
    expect(planErrorMessage(new AppError("INTERNAL_ERROR", "boom", 500))).toBe(
      "일정을 만들지 못했어요. 잠시 후 다시 시도해 주세요.",
    );
  });

  it("falls back for non-AppError throwables", () => {
    expect(planErrorMessage(new Error("boom"))).toContain("일정을 만들지 못했어요");
  });
});
