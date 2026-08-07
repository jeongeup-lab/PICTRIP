import { unsaveMessage, withObjectParticle } from "@/features/saved/lib/undo-message";

describe("withObjectParticle", () => {
  it("uses 을 after a final consonant", () => {
    expect(withObjectParticle("상족암")).toBe("상족암을");
  });

  it("uses 를 after a vowel ending", () => {
    expect(withObjectParticle("소매물도")).toBe("소매물도를");
  });

  it("falls back to 를 for non-hangul names", () => {
    expect(withObjectParticle("DDP")).toBe("DDP를");
  });

  it("ignores trailing whitespace", () => {
    expect(withObjectParticle("향일암 ")).toBe("향일암을");
  });
});

describe("unsaveMessage", () => {
  it("names the spot that was removed", () => {
    expect(unsaveMessage("가천 다랭이마을")).toBe("가천 다랭이마을을 스크랩에서 뺐어요");
  });
});
