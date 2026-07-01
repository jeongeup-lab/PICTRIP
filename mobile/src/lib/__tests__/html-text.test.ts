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

  it("decodes common named and numeric entities", () => {
    expect(htmlToPlainText("Tom &amp; Jerry")).toBe("Tom & Jerry");
    expect(htmlToPlainText("&lt;tag&gt; &quot;q&quot; &#39;a&#39;")).toBe("<tag> \"q\" 'a'");
    expect(htmlToPlainText("a&nbsp;b")).toBe("a b");
    expect(htmlToPlainText("&#54620;&#44544;")).toBe("한글");
  });

  it("decodes &amp; last so escaped entities survive", () => {
    expect(htmlToPlainText("&amp;lt;")).toBe("&lt;");
  });

  it("collapses 3+ newlines to a paragraph break and trims", () => {
    expect(htmlToPlainText("  a<br><br><br><br>b  ")).toBe("a\n\nb");
  });
});
