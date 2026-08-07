import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import {
  ConversationTurn,
  PENDING_HINT,
  TAP_HINT,
} from "@/features/travel/components/ConversationTurn";
import { ResultRow } from "@/features/travel/components/ResultRow";
import { StepList } from "@/features/travel/components/StepList";
import type { LatLng } from "@/features/map/lib/geo";
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

interface MountOptions {
  anchorId?: string | null;
  anchored?: boolean;
  origin?: LatLng | null;
  showTapHint?: boolean;
  onGrow?: () => void;
  onSpotTap?: (spot: { contentId: string }) => void;
  onSpotDetail?: (spot: { contentId: string }) => void;
}

function mount(t: Turn, options: MountOptions = {}) {
  const {
    anchorId = null,
    anchored = false,
    origin = null,
    showTapHint = false,
    onGrow = noop,
    onSpotTap = noop,
    onSpotDetail = noop,
  } = options;
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(
      <ConversationTurn
        turn={t}
        anchorId={anchorId}
        anchored={anchored}
        origin={origin}
        showTapHint={showTapHint}
        onSpotTap={onSpotTap}
        onSpotDetail={onSpotDetail}
        onRetry={noop}
        onGrow={onGrow}
        onSaveToggle={noop}
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

const pinned = (over: Partial<(typeof answer)["spots"][number]> = {}) => ({
  ...answer,
  spots: [{ ...answer.spots[0], lat: 37.5, lng: 129.0, ...over }],
});

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

  it("leaves every waiting stage unchecked and points at the map", () => {
    const tree = mount(turn({ status: "pending", answer: null }));
    const list = tree.root.findByType(StepList);
    expect(list.props.shown).toBe(2);
    expect(list.props.completed).toBe(0);
    expect(spinners(tree)).toBeGreaterThan(0);
    expect(texts(tree)).toContain(PENDING_HINT);
  });
});

describe("ConversationTurn once the answer lands", () => {
  it("shows the answer and the result rows with no further delay", () => {
    const tree = mount(turn());
    expect(texts(tree)).toContain("하위 30%");
    expect(tree.root.findAllByType(ResultRow)).toHaveLength(1);
    expect(spinners(tree)).toBe(0);
    expect(texts(tree)).not.toContain(PENDING_HINT);
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

  it("teaches the row tap grammar once and then stops", () => {
    expect(texts(mount(turn(), { showTapHint: true }))).toContain(TAP_HINT);
    expect(texts(mount(turn()))).not.toContain(TAP_HINT);
  });

  it("offers no feedback control that goes nowhere", () => {
    const tree = mount(turn());
    expect(tree.root.findAllByProps({ testID: "turn-vote-t1" })).toHaveLength(0);
  });

  it("counts the results when nothing can be measured", () => {
    expect(texts(mount(turn()))).toContain("추천 1곳");
  });

  it("measures each result once an origin is known", () => {
    const tree = mount(turn({ answer: pinned() }), { origin: { lat: 37.4, lng: 129.0 } });

    expect(tree.root.findByType(ResultRow).props.distanceKm).toBeGreaterThan(0);
  });

  it("never claims an ordering the list does not apply", () => {
    const withOrigin = mount(turn({ answer: pinned() }), { origin: { lat: 37.4, lng: 129.0 } });
    const anchoredTurn = mount(turn({ answer: pinned() }), {
      anchored: true,
      origin: { lat: 37.4, lng: 129.0 },
    });

    for (const tree of [withOrigin, anchoredTurn]) {
      expect(texts(tree)).toContain("추천 1곳");
      expect(texts(tree).join(" ")).not.toContain("가까운 순");
    }
  });

  it("measures from the anchor while one is held", () => {
    const tree = mount(turn({ answer: pinned() }), {
      anchored: true,
      origin: { lat: 37.4, lng: 129.0 },
    });

    expect(tree.root.findByType(ResultRow).props.tone).toBe("result");
  });

  it("leaves the distance out when the spot carries no coordinates", () => {
    const tree = mount(turn(), { origin: { lat: 37.4, lng: 129.0 } });

    expect(tree.root.findByType(ResultRow).props.distanceKm).toBeNull();
  });

  it("puts every result in the list without a see-all link", () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      ...answer.spots[0],
      contentId: `c${i}`,
      title: `spot-${i}`,
    }));
    const tree = mount(turn({ answer: { ...answer, spots: many } }));
    expect(tree.root.findAllByType(ResultRow)).toHaveLength(20);
    expect(texts(tree).join("")).not.toContain("전체");
  });

  it("routes every row tap through one handler, with no separate anchor button", () => {
    const onSpotTap = jest.fn();
    const tree = mount(turn(), { onSpotTap });
    const row = tree.root.findByType(ResultRow);

    act(() => row.props.onPress());

    expect(onSpotTap).toHaveBeenCalledWith(answer.spots[0]);
    expect(tree.root.findAllByProps({ testID: "travel-spot-anchor-126508" })).toHaveLength(0);
  });

  it("gives screen readers a detail action — a double tap never reaches onDouble there", () => {
    const onSpotDetail = jest.fn();
    const tree = mount(turn(), { onSpotDetail });
    const row = tree.root.findByType(ResultRow);

    act(() => row.props.onDetail());

    expect(onSpotDetail).toHaveBeenCalledWith(answer.spots[0]);
  });

  it("marks the anchored row selected and dims the rest", () => {
    const two = [answer.spots[0], { ...answer.spots[0], contentId: "126509", title: "다른계곡" }];
    const tree = mount(turn({ answer: { ...answer, spots: two } }), {
      anchorId: "126508",
      anchored: true,
    });
    const rows = tree.root.findAllByType(ResultRow);
    expect(rows).toHaveLength(2);
    expect(rows[0].props.selected).toBe(true);
    expect(rows[0].props.dimmed).toBe(false);
    expect(rows[1].props.selected).toBe(false);
    expect(rows[1].props.dimmed).toBe(true);
  });

  it("leaves a turn alone when the anchor belongs to another turn", () => {
    const tree = mount(turn(), { anchorId: "999999", anchored: true });
    const rows = tree.root.findAllByType(ResultRow);

    expect(rows.every((c) => c.props.dimmed === false)).toBe(true);
    expect(rows.every((c) => c.props.selected === false)).toBe(true);
  });

  it("keeps follow-up chips out of the answer block", () => {
    const tree = mount(turn());
    expect(tree.root.findAllByProps({ testID: "answer-suggestion-실내만" })).toHaveLength(0);
  });
});

describe("ConversationTurn when the request fails", () => {
  it("shows an error line with a retry button, no steps", () => {
    const tree = mount(
      turn({ status: "failed", answer: null, errorMessage: "조건에 맞는 곳을 찾지 못했어요." }),
    );
    expect(texts(tree)).toContain("조건에 맞는 곳을 찾지 못했어요.");
    expect(texts(tree)).toContain("다시 시도");
    expect(spinners(tree)).toBe(0);
  });
});
