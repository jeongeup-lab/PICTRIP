import { firstSentence } from "@/features/spots/lib/overview";

describe("firstSentence", () => {
  it("returns null for null/empty input", () => {
    expect(firstSentence(null)).toBeNull();
    expect(firstSentence("")).toBeNull();
    expect(firstSentence("   ")).toBeNull();
  });

  it("returns the first sentence up to terminal punctuation", () => {
    expect(firstSentence("First one. Second one.")).toBe("First one.");
    expect(firstSentence("질문인가요? 그다음.")).toBe("질문인가요?");
    expect(firstSentence("한국어 문장입니다。 다음.")).toBe("한국어 문장입니다。");
  });

  it("falls back to the whole trimmed text when no terminator", () => {
    expect(firstSentence("  no terminator here  ")).toBe("no terminator here");
  });
});
