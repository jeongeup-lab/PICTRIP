import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import {
  ChatTranscript,
  FAIL_TITLE,
  RETRY_LABEL,
} from "@/features/travel/components/ChatTranscript";
import { SpotCarousel } from "@/features/travel/components/SpotCarousel";
import type { QueryIntent, TravelSpot } from "@/features/travel/api";
import type { Turn } from "@/features/travel/stores/conversation-store";

jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const spot: TravelSpot = {
  contentId: "1",
  title: "장소 1",
  regionLabel: "제주시",
  imageUrl: null,
  tag: "한산",
  lat: 33.01,
  lng: 126,
};

const doneTurn: Turn = {
  id: "t1",
  question: "바다 보이는 카페",
  request: "바다 보이는 카페",
  photo: null,
  intent: null,
  patch: null,
  anchor: null,
  context: null,
  followKey: null,
  status: "done",
  answer: {
    steps: [],
    answer: [{ text: "이 근처가 좋아요", emphasis: false }],
    spots: [spot],
    totalCount: 1,
    intent: {} as QueryIntent,
    suggestions: [],
  },
  errorMessage: null,
};

const base = {
  turns: [doneTurn],
  focusedIndex: 0,
  scrollToIndex: null,
  origin: null,
  followUp: null,
  busy: false,
  onFollowChip: jest.fn(),
  onFocusChange: jest.fn(),
  onDetail: jest.fn(),
  onSaveToggle: jest.fn(),
  onMetricPress: jest.fn(),
  onRetry: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof ChatTranscript>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<ChatTranscript {...base} {...props} />);
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
  return tree.root.findAllByProps({ testID: id }).filter((n) => n.parent?.props?.testID !== id);
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("ChatTranscript", () => {
  it("유저 말풍선과 답변 텍스트를 함께 렌더한다", () => {
    const tree = mount({ turns: [doneTurn] });
    expect(texts(tree)).toContain("바다 보이는 카페");
    expect(texts(tree)).toContain("이 근처가 좋아요");
  });

  it("pending 턴은 스텝 라벨을 보여준다", () => {
    const tree = mount({ turns: [{ ...doneTurn, status: "pending", answer: null }] });
    expect(byId(tree, "travel-turn-step").length).toBeGreaterThan(0);
  });

  it("failed 턴은 재시도 버튼을 보여준다", () => {
    const tree = mount({
      turns: [{ ...doneTurn, status: "failed", answer: null, errorMessage: "네트워크 오류" }],
    });
    const retry = byId(tree, "travel-retry")[0];
    act(() => retry.props.onPress());
    expect(base.onRetry).toHaveBeenCalled();
  });

  it("failed 턴은 실패 제목과 재시도 라벨을 함께 보여준다", () => {
    const tree = mount({
      turns: [{ ...doneTurn, status: "failed", answer: null, errorMessage: "네트워크 오류" }],
    });
    expect(texts(tree)).toContain(FAIL_TITLE);
    expect(texts(tree)).toContain("네트워크 오류");
    expect(texts(tree)).toContain(RETRY_LABEL);
  });

  it("마지막 done 턴 아래에 followUp 문장과 칩을 렌더한다", () => {
    const tree = mount({
      turns: [doneTurn],
      followUp: {
        line: "어떤 곳부터 찾아볼까요?",
        chips: [{ label: "카페", action: { kind: "branch", to: "near" } }],
      },
    });
    expect(texts(tree)).toContain("어떤 곳부터 찾아볼까요?");
    act(() => byId(tree, "travel-follow-0")[0].props.onPress());
    expect(base.onFollowChip).toHaveBeenCalled();
  });

  it("스팟이 없는 done 턴(detail)은 카루셀을 렌더하지 않는다", () => {
    const tree = mount({
      turns: [{ ...doneTurn, answer: { ...doneTurn.answer!, spots: [], totalCount: 0 } }],
    });
    expect(byId(tree, "travel-carousel-slot")).toHaveLength(0);
  });

  it("스팟이 있는 done 턴은 카루셀 슬롯을 렌더한다", () => {
    const tree = mount({ turns: [doneTurn] });
    expect(byId(tree, "travel-carousel-slot").length).toBeGreaterThan(0);
  });

  it("마지막 턴의 카루셀만 포커스와 스크롤을 받는다", () => {
    const older: Turn = { ...doneTurn, id: "t0" };
    const tree = mount({ turns: [older, doneTurn], focusedIndex: 2, scrollToIndex: 2 });
    const carousels = tree.root.findAllByType(SpotCarousel);
    expect(carousels).toHaveLength(2);
    expect(carousels[0].props.focusedIndex).toBe(0);
    expect(carousels[0].props.scrollToIndex).toBeNull();
    expect(carousels[1].props.focusedIndex).toBe(2);
    expect(carousels[1].props.scrollToIndex).toBe(2);
  });

  it("busy면 followUp 칩이 잠긴다", () => {
    const tree = mount({
      turns: [doneTurn],
      busy: true,
      followUp: {
        line: "어떤 곳부터 찾아볼까요?",
        chips: [{ label: "카페", action: { kind: "branch", to: "near" } }],
      },
    });
    expect(byId(tree, "travel-follow-0")[0].props.disabled).toBe(true);
  });

  it("마지막 턴이 done이 아니면 followUp을 렌더하지 않는다", () => {
    const tree = mount({
      turns: [{ ...doneTurn, status: "pending", answer: null }],
      followUp: {
        line: "어떤 곳부터 찾아볼까요?",
        chips: [{ label: "카페", action: { kind: "branch", to: "near" } }],
      },
    });
    expect(texts(tree)).not.toContain("어떤 곳부터 찾아볼까요?");
  });
});
