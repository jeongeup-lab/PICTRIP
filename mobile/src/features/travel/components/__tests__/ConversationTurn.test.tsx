import renderer, { act } from "react-test-renderer";
import { FlatList, Text } from "react-native";
import { ConversationTurn } from "@/features/travel/components/ConversationTurn";
import { SpotCard } from "@/features/travel/components/SpotCard";
import { StepList } from "@/features/travel/components/StepList";
import type { Turn } from "@/features/travel/stores/conversation-store";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const answer = {
  steps: [
    { tool: "category_search", label: "계곡 유형 조회", badge: "128곳" },
    { tool: "concentration", label: "혼잡도 하위 30% 추림", badge: "12곳" },
    { tool: "nearby", label: "주차·편의시설 확인", badge: "4곳" },
  ],
  answer: [
    { text: "넷 다 이번 주말 예측이 ", emphasis: false },
    { text: "하위 30%", emphasis: true },
    { text: "예요.", emphasis: false },
  ],
  spots: [
    {
      contentId: "126508",
      title: "무릉계곡",
      regionLabel: "강원도 동해시",
      imageUrl: null,
      tag: "하위 8%",
      lat: null,
      lng: null,
    },
  ],
  totalCount: 12,
  intent: { categoryKeywords: ["계곡"], regionHints: [] },
  suggestions: ["실내만"],
  refinements: [{ label: "실내만", patch: { indoorOnly: true } }],
};

const turn = (over: Partial<Turn> = {}): Turn => ({
  id: "t1",
  question: "여름에 시원한 계곡",
  request: "여름에 시원한 계곡",
  photo: null,
  status: "done",
  answer,
  errorMessage: null,
  intent: null,
  patch: null,
  anchor: null,
  context: null,
  ...over,
});

const noop = () => undefined;

function mount(t: Turn, anchorId: string | null = null, onGrow = noop, onOpenMap = noop) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(
      <ConversationTurn
        turn={t}
        anchorId={anchorId}
        onSpotPress={noop}
        onSpotAnchor={noop}
        onOpenMap={onOpenMap}
        onRetry={noop}
        onGrow={onGrow}
      />,
    );
  });
  return tree!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string[] =>
  tree.root.findAllByType(Text).map((n) => flatten(n.props.children));

const spinners = (tree: renderer.ReactTestRenderer) =>
  tree.root.findAllByProps({ testID: "step-spinner" }).length;

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

describe("ConversationTurn while waiting", () => {
  it("names the stages that actually run for a free-text question", () => {
    const tree = mount(turn({ status: "pending", answer: null }));
    expect(texts(tree)).toContain("질문에서 조건 읽는 중");
    expect(texts(tree)).toContain("여행지 찾는 중");
    expect(texts(tree)).not.toContain("계곡 유형 조회");
  });

  it("drops the intent stage when the request carries a prepared intent", () => {
    const tree = mount(
      turn({
        status: "pending",
        answer: null,
        request: "",
        intent: { categoryKeywords: [], regionHints: [] },
      }),
    );
    expect(texts(tree)).not.toContain("질문에서 조건 읽는 중");
    expect(texts(tree)).toContain("여행지 찾는 중");
  });

  it("leaves every waiting stage unchecked", () => {
    const tree = mount(turn({ status: "pending", answer: null }));
    const list = tree.root.findByType(StepList);
    expect(list.props.shown).toBe(2);
    expect(list.props.completed).toBe(0);
    expect(spinners(tree)).toBeGreaterThan(0);
  });
});

describe("ConversationTurn once the answer lands", () => {
  it("shows the answer and the rail with no further delay", () => {
    const tree = mount(turn());
    expect(texts(tree)).toContain("하위 30%");
    expect(tree.root.findAllByType(SpotCard)).toHaveLength(1);
    expect(spinners(tree)).toBe(0);
  });

  it("shows every server step at once, all completed", () => {
    const tree = mount(turn());
    expect(texts(tree)).toContain("계곡 유형 조회");
    expect(texts(tree)).toContain("혼잡도 하위 30% 추림");
    expect(texts(tree)).toContain("주차·편의시설 확인");
  });

  it("does not advance anything on a timer", () => {
    const tree = mount(turn());
    const before = texts(tree).join("");
    act(() => jest.advanceTimersByTime(5000));
    expect(texts(tree).join("")).toBe(before);
  });

  it("says what the card tags are measured against", () => {
    const tree = mount(turn({ answer: { ...answer, tagBasis: "혼잡도 8/3 예측 기준" } }));

    expect(texts(tree)).toContain("혼잡도 8/3 예측 기준");
  });

  it("stays silent when the server names no basis", () => {
    const tree = mount(turn());

    expect(tree.root.findAllByProps({ testID: "turn-basis-t1" })).toHaveLength(0);
  });

  it("carries the overview excerpt down to the card", () => {
    const withBlurb = { ...answer.spots[0], blurb: "우도 동쪽의 백사장이다." };
    const tree = mount(turn({ answer: { ...answer, spots: [withBlurb] } }));

    expect(texts(tree)).toContain("우도 동쪽의 백사장이다.");
  });

  it("offers no feedback control that goes nowhere", () => {
    const tree = mount(turn());
    expect(tree.root.findAllByProps({ testID: "turn-vote-t1" })).toHaveLength(0);
  });

  it("offers a map for results that carry coordinates", () => {
    const tree = mount(
      turn({ answer: { ...answer, spots: [{ ...answer.spots[0], lat: 33.5, lng: 126.5 }] } }),
    );

    expect(tree.root.findAllByProps({ testID: "travel-turn-map" }).length).toBeGreaterThan(0);
  });

  it("hides the map when no result can be pinned", () => {
    const tree = mount(turn());

    expect(tree.root.findAllByProps({ testID: "travel-turn-map" })).toHaveLength(0);
  });

  it("hands the whole turn to the map opener", () => {
    const onOpenMap = jest.fn();
    const mapped = turn({
      answer: { ...answer, spots: [{ ...answer.spots[0], lat: 33.5, lng: 126.5 }] },
    });
    const tree = mount(mapped, null, noop, onOpenMap);

    act(() => {
      tree.root.findByProps({ testID: "travel-turn-map" }).props.onPress();
    });

    expect(onOpenMap).toHaveBeenCalledWith(mapped);
  });

  it("puts every result on the rail without a see-all link", () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      ...answer.spots[0],
      contentId: `c${i}`,
      title: `spot-${i}`,
    }));
    const tree = mount(turn({ answer: { ...answer, spots: many } }));
    const rail = tree.root.findByType(FlatList);
    expect(rail.props.data).toHaveLength(20);
    expect(texts(tree).join("")).not.toContain("전체");
  });

  it("keeps the card tap on the detail route and puts anchoring on its own button", () => {
    const tree = mount(turn());
    const card = tree.root.findByType(SpotCard);

    expect(card.props.onPress).toBeDefined();
    expect(card.props.onAnchor).toBeDefined();
    expect(
      tree.root.findAllByProps({ testID: "travel-spot-anchor-126508" }).length,
    ).toBeGreaterThan(0);
  });

  it("marks the anchored card selected and dims the rest", () => {
    const two = [answer.spots[0], { ...answer.spots[0], contentId: "126509", title: "다른계곡" }];
    const tree = mount(turn({ answer: { ...answer, spots: two } }), "126508");
    const cards = tree.root.findAllByType(SpotCard);
    expect(cards).toHaveLength(2);
    expect(cards[0].props.selected).toBe(true);
    expect(cards[0].props.dimmed).toBe(false);
    expect(cards[1].props.selected).toBe(false);
    expect(cards[1].props.dimmed).toBe(true);
  });

  it("keeps follow-up chips out of the answer block", () => {
    const tree = mount(turn());
    expect(tree.root.findAllByProps({ testID: "answer-suggestion-실내만" })).toHaveLength(0);
  });
});

describe("ConversationTurn when the request fails", () => {
  it("shows an error line with a retry chip, no steps", () => {
    const tree = mount(
      turn({ status: "failed", answer: null, errorMessage: "조건에 맞는 곳을 찾지 못했어요." }),
    );
    expect(texts(tree)).toContain("조건에 맞는 곳을 찾지 못했어요.");
    expect(texts(tree)).toContain("다시 시도");
    expect(spinners(tree)).toBe(0);
  });
});
