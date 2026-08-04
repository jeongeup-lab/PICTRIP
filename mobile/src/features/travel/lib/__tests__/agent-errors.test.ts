import { agentErrorMessage } from "@/features/travel/lib/agent-errors";
import { AppError } from "@/lib/app-error";

describe("agentErrorMessage", () => {
  it("branches on the code, never the server message", () => {
    const error = new AppError("AGENT_NO_RESULTS", "no rows matched the filter", 422);
    expect(agentErrorMessage(error)).toContain("조건을 조금 넓혀서");
    expect(agentErrorMessage(error)).not.toContain("no rows");
  });

  it("explains a Gemini outage as a retryable state", () => {
    expect(agentErrorMessage(new AppError("AGENT_INTENT_UNAVAILABLE", "", 502))).toContain(
      "다시 시도",
    );
  });

  it("falls back for unmapped codes and non-AppError throws", () => {
    const fallback = agentErrorMessage(new Error("boom"));
    expect(fallback).toBe("답을 만들지 못했어요. 잠시 후 다시 시도해 주세요.");
    expect(agentErrorMessage(new AppError("INTERNAL_ERROR", "", 500))).toBe(fallback);
  });
  it("축제 조회 실패에 전용 안내를 쓴다", () => {
    const error = new AppError("AGENT_FESTIVAL_UNAVAILABLE", "kto down", 422);
    expect(agentErrorMessage(error)).toContain("축제");
  });
});
