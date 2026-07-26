import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { ConversationTurn } from "@/features/travel/components/ConversationTurn";
import type { Turn } from "@/features/travel/stores/conversation-store";
import { playbackDurationMs, STEP_INTERVAL_MS } from "@/features/travel/lib/step-playback";
import type { Chip } from "@/features/travel/lib/chips";

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
  suggestions: [{ label: "실내만", patch: { indoorOnly: true } }],
};

const turn = (over: Partial<Turn> = {}): Turn => ({
  id: "t1",
  question: "여름에 시원한 계곡",
  request: "여름에 시원한 계곡",
  photo: null,
  status: "playing",
  answer,
  errorMessage: null,
  intent: null,
  patch: null,
  ...over,
});

const noop = () => undefined;

function mount(
  t: Turn,
  onPlaybackEnd = noop,
  onSuggest: (chip: Chip, source: Turn) => void = noop,
) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(
      <ConversationTurn
        turn={t}
        onPlaybackEnd={onPlaybackEnd}
        onSuggest={onSuggest}
        onOpenResults={noop}
        onRetry={noop}
        onGrow={noop}
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

describe("ConversationTurn playback", () => {
  it("holds a single spinner row while the request is still in flight", () => {
    const tree = mount(turn({ status: "pending", answer: null }));
    expect(texts(tree)).toContain("여행지를 찾는 중");
    expect(texts(tree)).not.toContain("계곡 유형 조회");
  });

  it("reveals server steps one at a time instead of all at once", () => {
    const tree = mount(turn());
    expect(texts(tree)).toContain("계곡 유형 조회");
    expect(texts(tree)).not.toContain("혼잡도 하위 30% 추림");

    act(() => jest.advanceTimersByTime(STEP_INTERVAL_MS));
    expect(texts(tree)).toContain("혼잡도 하위 30% 추림");
    expect(texts(tree)).not.toContain("주차·편의시설 확인");
  });

  it("withholds the answer and the result rail until playback ends", () => {
    const onPlaybackEnd = jest.fn();
    const tree = mount(turn(), onPlaybackEnd);
    act(() => jest.advanceTimersByTime(2 * STEP_INTERVAL_MS));
    expect(texts(tree)).not.toContain("하위 30%");
    expect(onPlaybackEnd).not.toHaveBeenCalled();

    act(() => jest.advanceTimersByTime(playbackDurationMs(3)));
    expect(texts(tree)).toContain("하위 30%");
    expect(texts(tree)).toContain("전체 1곳 보기");
    expect(onPlaybackEnd).toHaveBeenCalledWith("t1");
    expect(spinners(tree)).toBe(0);
  });

  it("counts the link by the spots it opens, not by a server total", () => {
    const tree = mount(turn({ status: "done" }));
    expect(answer.totalCount).not.toBe(answer.spots.length);
    expect(texts(tree)).toContain(`전체 ${answer.spots.length}곳 보기`);
  });

  it("shows a failed turn as an error line with a retry chip, no steps", () => {
    const tree = mount(
      turn({ status: "failed", answer: null, errorMessage: "조건에 맞는 곳을 찾지 못했어요." }),
    );
    expect(texts(tree)).toContain("조건에 맞는 곳을 찾지 못했어요.");
    expect(texts(tree)).toContain("다시 시도");
    expect(spinners(tree)).toBe(0);
  });

  it("renders a completed turn without replaying it", () => {
    const tree = mount(turn({ status: "done" }));
    expect(texts(tree)).toContain("하위 30%");
    expect(spinners(tree)).toBe(0);
  });

  it("hands the follow-up chip up as a patch alongside its own turn, not as label text", () => {
    const onSuggest = jest.fn();
    const own = turn({ status: "done" });
    const tree = mount(own, noop, onSuggest);
    const chip = tree.root
      .findAllByProps({ testID: "answer-suggestion-실내만" })
      .find((node) => typeof node.props.onPress === "function");

    act(() => chip!.props.onPress());

    expect(onSuggest).toHaveBeenCalledWith(
      { kind: "refine", label: "실내만", patch: { indoorOnly: true } },
      own,
    );
  });
});
