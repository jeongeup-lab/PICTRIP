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

describe("인용 번호", () => {
  it("카드 범위 안 번호는 탭 가능한 파트로 뗀다", () => {
    const blocks = parseRichText("- **오동도**[1] 좋아요", 3);

    expect(blocks[0].parts).toEqual([
      { text: "오동도", bold: true },
      { text: "1", bold: false, cite: 1 },
      { text: " 좋아요", bold: false },
    ]);
  });

  it("카드 수를 넘는 번호는 본문에서 지운다", () => {
    const blocks = parseRichText("**어딘가**[7] 좋아요", 3);

    expect(blocks[0].parts).toEqual([
      { text: "어딘가", bold: true },
      { text: " 좋아요", bold: false },
    ]);
  });

  it("0번은 카드가 1번부터라 지운다", () => {
    expect(parseRichText("가볼 만해요[0].", 3)[0].parts).toEqual([
      { text: "가볼 만해요", bold: false },
      { text: ".", bold: false },
    ]);
  });

  it("숫자가 아닌 대괄호는 그대로 둔다", () => {
    expect(parseRichText("[참고] 좋아요", 3)[0].parts).toEqual([
      { text: "[참고] 좋아요", bold: false },
    ]);
  });

  it("카드 수를 안 주면 번호를 건드리지 않는다", () => {
    expect(parseRichText("**오동도**[1] 좋아요")[0].parts).toEqual([
      { text: "오동도", bold: true },
      { text: "[1] 좋아요", bold: false },
    ]);
  });

  it("번호를 누르면 그 카드 순번을 알린다", async () => {
    const tapped: number[] = [];
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(
        <RichAnswerText
          text="**오동도**[2] 좋아요"
          spotCount={3}
          onCitePress={(n) => tapped.push(n)}
        />,
      );
    });

    const cite = tree!.root.findAll((node) => node.props.testID === "answer-cite-2")[0];
    await act(async () => cite.props.onPress());

    expect(tapped).toEqual([2]);
    await act(async () => tree!.unmount());
  });
});
