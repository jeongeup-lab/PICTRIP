import { composeQuestion, PHOTO_ONLY_QUESTION, resultsTitle } from "@/features/travel/lib/question";

describe("composeQuestion", () => {
  it("trims the typed question", () => {
    expect(composeQuestion("  계곡  ", false)).toBe("계곡");
  });

  it("substitutes the photo question when only a photo is attached", () => {
    expect(composeQuestion("   ", true)).toBe(PHOTO_ONLY_QUESTION);
  });

  it("keeps the typed text even when a photo is attached", () => {
    expect(composeQuestion("여기 근처", true)).toBe("여기 근처");
  });

  it("refuses an empty submit with no attachment", () => {
    expect(composeQuestion("", false)).toBeNull();
  });
});

describe("resultsTitle", () => {
  it("passes short questions through", () => {
    expect(resultsTitle("여름에 시원한 계곡")).toBe("여름에 시원한 계곡");
  });

  it("elides questions past 20 characters", () => {
    const long = "가".repeat(30);
    expect(resultsTitle(long)).toBe(`${"가".repeat(20)}…`);
  });
});
