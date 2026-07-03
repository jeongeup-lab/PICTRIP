import { htmlToPlainText } from "@/lib/html-text";

describe("htmlToPlainText", () => {
  it("returns empty string for empty input", () => {
    expect(htmlToPlainText("")).toBe("");
  });

  it("converts <br> and <br/> to newlines", () => {
    expect(htmlToPlainText("a<br>b<br/>c")).toBe("a\nb\nc");
  });

  it("converts block-close tags to newlines", () => {
    expect(htmlToPlainText("<p>first</p><p>second</p>")).toBe("first\nsecond");
    expect(htmlToPlainText("<div>x</div><li>y</li>")).toBe("x\ny");
  });

  it("strips remaining tags", () => {
    expect(htmlToPlainText('<a href="x">link</a> <b>bold</b>')).toBe("link bold");
  });

  it("strips nested tags cleanly", () => {
    expect(htmlToPlainText("<p>a<b>c</b></p>")).toBe("ac");
    expect(htmlToPlainText("<div><span>x</span></div>")).toBe("x");
  });

  it("terminates on malformed unbalanced brackets (fixpoint loop, no hang)", () => {
    expect(htmlToPlainText("<a<b<c")).toBe("<a<b<c");
  });

  it("decodes common named and numeric entities", () => {
    expect(htmlToPlainText("Tom &amp; Jerry")).toBe("Tom & Jerry");
    expect(htmlToPlainText("&lt;tag&gt; &quot;q&quot; &#39;a&#39;")).toBe("<tag> \"q\" 'a'");
    expect(htmlToPlainText("a&nbsp;b")).toBe("a b");
    expect(htmlToPlainText("&#54620;&#44544;")).toBe("한글");
  });

  it("decodes &amp; last so escaped entities survive", () => {
    expect(htmlToPlainText("&amp;lt;")).toBe("&lt;");
  });

  it("does not throw on out-of-range numeric entities (drops them)", () => {
    // String.fromCodePoint throws RangeError above 0x10FFFF; untrusted KTO text
    // can carry huge numeric entities. Guard drops them instead of crashing render.
    expect(htmlToPlainText("a&#99999999999;b")).toBe("ab");
    expect(htmlToPlainText("x&#1114112;y")).toBe("xy"); // 0x110000, one past the max
    expect(htmlToPlainText("ok&#1114111;")).toBe("ok\u{10FFFF}"); // 0x10FFFF still decodes
  });

  it("collapses 3+ newlines to a paragraph break and trims", () => {
    expect(htmlToPlainText("  a<br><br><br><br>b  ")).toBe("a\n\nb");
  });
});
