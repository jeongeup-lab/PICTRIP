import { LEGAL_DOCS, legalUrl, findLegalDoc } from "@/features/legal/constants";

describe("legal constants", () => {
  it("lists the 3 documents in mockup order with verbatim labels", () => {
    expect(LEGAL_DOCS.map((d) => d.slug)).toEqual(["terms", "privacy", "location"]);
    expect(LEGAL_DOCS.map((d) => d.title)).toEqual([
      "이용약관",
      "개인정보처리방침",
      "위치기반서비스 이용약관",
    ]);
  });

  it("legalUrl builds the hosted page URL", () => {
    expect(legalUrl("terms")).toBe("https://pictrip.org/legal/terms");
    expect(legalUrl("location")).toBe("https://pictrip.org/legal/location");
  });

  it("findLegalDoc resolves a known slug and returns undefined for unknown", () => {
    expect(findLegalDoc("privacy")?.title).toBe("개인정보처리방침");
    expect(findLegalDoc("nope")).toBeUndefined();
  });
});
