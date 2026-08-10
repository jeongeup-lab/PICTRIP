import { composeQuestion, PHOTO_ONLY_QUESTION } from "@/features/travel/lib/question";

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
