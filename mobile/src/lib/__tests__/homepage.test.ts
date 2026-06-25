import { cleanHomepage } from "@/lib/homepage";

describe("cleanHomepage", () => {
  it("extracts href + host label from an anchor tag", () => {
    expect(cleanHomepage('<a href="http://visitjeju.net" target="_blank">제주관광</a>')).toEqual({
      label: "visitjeju.net",
      url: "http://visitjeju.net",
    });
  });

  it("keeps a plain URL and derives a clean host label", () => {
    expect(cleanHomepage("https://www.visitseoul.net/")).toEqual({
      label: "visitseoul.net",
      url: "https://www.visitseoul.net/",
    });
  });

  it("treats raw scheme-less text as a host and adds https", () => {
    expect(cleanHomepage("visitjeju.net")).toEqual({
      label: "visitjeju.net",
      url: "https://visitjeju.net",
    });
  });

  it("prepends https to a scheme-less www host", () => {
    expect(cleanHomepage("www.example.com")).toEqual({
      label: "example.com",
      url: "https://www.example.com",
    });
  });

  it("unescapes entities inside the href", () => {
    expect(cleanHomepage('<a href="http://x.com/?a=1&amp;b=2">x</a>')).toEqual({
      label: "x.com",
      url: "http://x.com/?a=1&b=2",
    });
  });

  it("picks the first URL token out of surrounding text", () => {
    expect(cleanHomepage("공식 홈페이지 https://kto.visitkorea.or.kr 입니다")).toEqual({
      label: "kto.visitkorea.or.kr",
      url: "https://kto.visitkorea.or.kr",
    });
  });

  it("returns null for null / empty / whitespace", () => {
    expect(cleanHomepage(null)).toBeNull();
    expect(cleanHomepage("")).toBeNull();
    expect(cleanHomepage("   ")).toBeNull();
    expect(cleanHomepage("<br/>")).toBeNull();
  });
});
