import renderer, { act } from "react-test-renderer";
import { StyleSheet, Text } from "react-native";
import { Image } from "expo-image";
import {
  AnswerBar,
  COLLAPSED_COPY_PX,
  EXPANDED_COPY_PX,
} from "@/features/travel/components/AnswerBar";
import type { AnswerPart } from "@/features/travel/api";

const OVERVIEW =
  "세병관은 1605년 삼도수군통제영의 객사로 세워진 건물로 " +
  "지금 남아 있는 조선시대 목조 건축물 가운데 규모가 가장 큰 축에 들며 " +
  "정면 아홉 칸 측면 다섯 칸의 팔작지붕을 얹은 국보로 통영 앞바다를 내려다본다";

const SHORT: AnswerPart[] = [{ text: "통영은 굴 요리로 이름났어요.", emphasis: false }];

const answer: AnswerPart[] = [
  { text: "혼잡도 ", emphasis: false },
  { text: "하위 20%", emphasis: true },
  { text: " 안쪽으로만 골랐어요. 제주 동쪽으로 8곳이에요.", emphasis: false },
];

const base = {
  question: "제주에서 한적한 곳",
  answer,
  photoUri: null,
  step: null,
  errorMessage: null,
  expanded: false,
  collapsible: true,
  onToggle: jest.fn(),
  onClose: jest.fn(),
  onRetry: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof AnswerBar>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<AnswerBar {...base} {...props} />);
  });
  return tree!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string =>
  tree.root
    .findAllByType(Text)
    .map((n) => flatten(n.props.children))
    .join("");

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root
    .findAllByProps({ testID: id })
    .find((n) => typeof n.props.onPress === "function");
}

function copyMaxHeight(tree: renderer.ReactTestRenderer): number | undefined {
  const node = tree.root.findAllByProps({ testID: "travel-answer-copy" })[0];
  return StyleSheet.flatten(node.props.style)?.maxHeight as number | undefined;
}

function measureCopy(tree: renderer.ReactTestRenderer, height: number) {
  const node = tree.root
    .findAllByProps({ testID: "travel-answer-copy" })
    .find((n) => typeof n.props.onContentSizeChange === "function");

  act(() => node!.props.onContentSizeChange(280, height));
}

describe("AnswerBar", () => {
  it("접히면 헤드라인만 보이고 보충은 감춘다", () => {
    const shown = texts(mount());

    expect(shown).toContain("안쪽으로만 골랐어요.");
    expect(shown).not.toContain("제주 동쪽으로 8곳이에요.");
  });

  it("펼치면 보충까지 보인다", () => {
    expect(texts(mount({ expanded: true }))).toContain("제주 동쪽으로 8곳이에요.");
  });

  it("질문은 라벨로만 그린다", () => {
    expect(texts(mount())).toContain("제주에서 한적한 곳");
  });

  it("진행 중에는 답변 대신 단계 한 줄을 든다", () => {
    const shown = texts(mount({ step: "질문에서 조건 읽는 중" }));

    expect(shown).toContain("질문에서 조건 읽는 중");
    expect(shown).not.toContain("골랐어요");
  });

  it("실패에는 재시도 버튼이 붙는다", () => {
    const onRetry = jest.fn();
    const tree = mount({ errorMessage: "네트워크가 불안정해요", onRetry });

    expect(texts(tree)).toContain("네트워크가 불안정해요");
    expect(texts(tree)).not.toContain("골랐어요");
    act(() => byId(tree, "travel-retry")!.props.onPress());
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("재시도로 단계가 다시 돌면 실패 표시를 걷는다", () => {
    const shown = texts(mount({ errorMessage: "네트워크가 불안정해요", step: "여행지 찾는 중" }));

    expect(shown).toContain("여행지 찾는 중");
    expect(shown).not.toContain("답변을 못 받았어요");
  });

  it("사진 질문에는 올린 사진을 함께 든다", () => {
    const uri = "file:///photo/jeju.jpg";
    const sources = mount({ photoUri: uri })
      .root.findAllByType(Image)
      .map((n) => n.props.source?.uri);

    expect(sources).toContain(uri);
  });

  it("답변이 없으면 펼침 토글을 그리지 않는다", () => {
    expect(byId(mount({ answer: null }), "travel-answer-toggle")).toBeUndefined();
    expect(byId(mount({ answer: [] }), "travel-answer-toggle")).toBeUndefined();
  });

  it("접을 수 없는 답변에는 토글도 접기 라벨도 그리지 않는다", () => {
    const tree = mount({ collapsible: false, expanded: true });

    expect(byId(tree, "travel-answer-toggle")).toBeUndefined();
    expect(tree.root.findAllByProps({ accessibilityLabel: "답변 접기" })).toHaveLength(0);
    expect(texts(tree)).toContain("제주 동쪽으로 8곳이에요.");
  });

  it("접을 수 있는 답변에는 토글이 그대로 남는다", () => {
    const tree = mount();

    expect(byId(tree, "travel-answer-toggle")).toBeDefined();
    expect(byId(tree, "travel-answer-toggle")!.props.accessibilityLabel).toBe("답변 펼치기");
  });

  it("문장 끝 부호가 없어 쪼갤 수 없는 답변도 접을 길을 준다", () => {
    const onToggle = jest.fn();
    const tree = mount({ answer: [{ text: OVERVIEW, emphasis: false }], onToggle });

    measureCopy(tree, COLLAPSED_COPY_PX * 3);

    act(() => byId(tree, "travel-answer-toggle")!.props.onPress());
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("보충 없는 한 문장이 두 줄 안에 들면 토글을 그리지 않는다", () => {
    const tree = mount({ answer: SHORT });

    measureCopy(tree, COLLAPSED_COPY_PX);

    expect(byId(tree, "travel-answer-toggle")).toBeUndefined();
    expect(tree.root.findAllByProps({ accessibilityLabel: "답변 펼치기" })).toHaveLength(0);
  });

  it("측정 전에는 토글을 먼저 그려두지 않는다", () => {
    expect(
      byId(mount({ answer: [{ text: OVERVIEW, emphasis: false }] }), "travel-answer-toggle"),
    ).toBeUndefined();
  });

  it("긴 답변 뒤에 짧은 답변이 오면 토글을 거둔다", () => {
    const tree = mount({ answer: [{ text: OVERVIEW, emphasis: false }] });
    measureCopy(tree, COLLAPSED_COPY_PX * 3);
    expect(byId(tree, "travel-answer-toggle")).toBeDefined();

    act(() => {
      tree.update(<AnswerBar {...base} answer={SHORT} />);
    });

    expect(byId(tree, "travel-answer-toggle")).toBeUndefined();
  });

  it("진행 중과 실패에는 토글을 그리지 않는다", () => {
    expect(byId(mount({ step: "여행지 찾는 중" }), "travel-answer-toggle")).toBeUndefined();
    expect(
      byId(mount({ errorMessage: "네트워크가 불안정해요" }), "travel-answer-toggle"),
    ).toBeUndefined();
  });

  it("긴 한 문장 답변도 접히면 두 줄 높이 안에 묶인다", () => {
    const tree = mount({ answer: [{ text: `${OVERVIEW}.`, emphasis: false }] });

    expect(copyMaxHeight(tree)).toBe(COLLAPSED_COPY_PX);
  });

  it("펼치면 본문 전체를 보여주되 화면을 삼키지 않게 묶는다", () => {
    const tree = mount({ answer: [{ text: `${OVERVIEW}.`, emphasis: false }], expanded: true });

    expect(texts(tree)).toContain(OVERVIEW);
    expect(copyMaxHeight(tree)).toBe(EXPANDED_COPY_PX);
  });

  it("접힌 헤드라인에서도 강조 조각을 잃지 않는다", () => {
    const emphasised = mount()
      .root.findAllByType(Text)
      .map((n) => flatten(n.props.children));

    expect(emphasised).toContain("하위 20%");
  });

  it("새 대화 버튼은 항상 있다", () => {
    const onClose = jest.fn();
    const tree = mount({ onClose });

    act(() => byId(tree, "travel-new-chat")!.props.onPress());
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
