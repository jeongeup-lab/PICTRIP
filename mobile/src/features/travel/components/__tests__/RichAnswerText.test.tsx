import renderer, { act } from "react-test-renderer";
import {
  RichAnswerText,
  parseBold,
  parseRichText,
} from "@/features/travel/components/RichAnswerText";

describe("parseBold", () => {
  it("굵게 마커 쌍을 bold 파트로 나눈다", () => {
    expect(parseBold("정읍은 **쌍화차 거리**가 유명해요")).toEqual([
      { text: "정읍은 ", bold: false },
      { text: "쌍화차 거리", bold: true },
      { text: "가 유명해요", bold: false },
    ]);
  });

  it("짝이 안 맞는 마커는 본문 그대로 둔다", () => {
    expect(parseBold("굵게 **열고 안 닫음")).toEqual([
      { text: "굵게 **열고 안 닫음", bold: false },
    ]);
  });

  it("마커가 없으면 통짜 파트 하나다", () => {
    expect(parseBold("그냥 문장")).toEqual([{ text: "그냥 문장", bold: false }]);
  });
});

describe("parseRichText", () => {
  it("줄 시작 하이픈만 불릿으로 본다", () => {
    const blocks = parseRichText("결론이에요.\n- 첫 팁\n- 둘째 팁\n중간 - 하이픈은 본문");

    expect(blocks.map((b) => b.kind)).toEqual(["paragraph", "bullet", "bullet", "paragraph"]);
    expect(blocks[1].parts).toEqual([{ text: "첫 팁", bold: false }]);
  });

  it("빈 줄은 버린다", () => {
    expect(parseRichText("위\n\n아래")).toHaveLength(2);
  });

  it("불릿 안 굵게도 파싱한다", () => {
    const blocks = parseRichText("- **내장산** 단풍");

    expect(blocks[0].parts).toEqual([
      { text: "내장산", bold: true },
      { text: " 단풍", bold: false },
    ]);
  });

  it("다른 마크다운 문법은 파싱하지 않고 그대로 둔다", () => {
    const blocks = parseRichText("# 제목\n*기울임* [링크](url)");

    expect(blocks[0].kind).toBe("paragraph");
    expect(blocks[0].parts).toEqual([{ text: "# 제목", bold: false }]);
    expect(blocks[1].parts).toEqual([{ text: "*기울임* [링크](url)", bold: false }]);
  });
});

describe("RichAnswerText", () => {
  it("본문과 불릿을 함께 그린다", async () => {
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(<RichAnswerText text={"결론.\n- **팁** 하나"} />);
    });

    const out = JSON.stringify(tree!.toJSON());
    expect(out).toContain("결론.");
    expect(out).toContain("팁");
    await act(async () => tree!.unmount());
  });

  it("빈 텍스트면 아무것도 그리지 않는다", async () => {
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(<RichAnswerText text="" />);
    });

    expect(tree!.toJSON()).toBeNull();
    await act(async () => tree!.unmount());
  });
});
