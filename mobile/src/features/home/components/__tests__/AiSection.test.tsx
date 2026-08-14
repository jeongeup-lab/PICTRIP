import renderer, { act } from "react-test-renderer";
import { router } from "expo-router";
import { AiSection } from "@/features/home/components/AiSection";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import type { HomeSpotCard, Recommendations } from "@/features/home/api";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("@/features/auth/hooks/use-auth-gate", () => ({ useAuthGate: jest.fn() }));
jest.mock("@/features/home/components/SpotGrid", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    SpotGrid: ({ cards }: { cards: HomeSpotCard[] }) =>
      React.createElement(
        View,
        { testID: "spot-grid" },
        cards.map((c) =>
          React.createElement(View, {
            key: c.contentId,
            testID: "grid-item",
          }),
        ),
      ),
  };
});

const mockGate = useAuthGate as jest.Mock;
let gate: jest.Mock;

const card = (over: Partial<HomeSpotCard> = {}): HomeSpotCard => ({
  contentId: "c1",
  title: "비애드 카페앤바",
  regionLabel: "서울특별시 광진구",
  imageUrl: null,
  rank: null,
  dist: 660,
  category: "카페",
  tag: null,
  anchorTitle: "밀크컨셉 건대점",
  ...over,
});

const recommendations = (over: Partial<Recommendations> = {}): Recommendations => ({
  ready: true,
  savedCount: 5,
  minSaved: 3,
  items: [card()],
  ...over,
});

beforeEach(() => {
  gate = jest.fn(async () => true);
  mockGate.mockReturnValue(gate);
});

afterEach(() => jest.clearAllMocks());

async function mount(props: Partial<Parameters<typeof AiSection>[0]> = {}) {
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(
      <AiSection
        displayName="Leesinseong"
        data={recommendations()}
        isLoading={false}
        isError={false}
        onRetry={jest.fn()}
        {...props}
      />,
    );
  });
  return tree!;
}

const json = (r: renderer.ReactTestRenderer) => JSON.stringify(r.toJSON());

describe("AiSection", () => {
  it("greets the signed-in user by name", async () => {
    const r = await mount();
    expect(json(r)).toContain("Leesinseong");
    expect(json(r)).toContain("님을 위한 AI 추천 장소");
  });

  it("falls back to a neutral name for a guest", async () => {
    const r = await mount({ displayName: null, data: undefined });
    expect(json(r)).toContain("여행자");
  });

  it("renders the recommendation grid without saved-similarity copy", async () => {
    const r = await mount();
    expect(r.root.findAllByProps({ testID: "grid-item" }).length).toBeGreaterThan(0);
    expect(json(r)).not.toContain("저장한 장소와 닮은 곳을 골랐어요.");
    expect(json(r)).not.toContain("비슷한 곳");
  });

  it("shows the taste CTA instead of a grid before the minimum saves", async () => {
    const r = await mount({ data: recommendations({ ready: false, savedCount: 1, items: [] }) });
    expect(r.root.findAllByProps({ testID: "spot-grid" })).toHaveLength(0);
    expect(r.root.findAllByProps({ testID: "home-taste-cta" }).length).toBeGreaterThan(0);
  });

  it("keeps the CTA free of remaining-count and how-it-works copy", async () => {
    const r = await mount({ data: recommendations({ ready: false, savedCount: 1, items: [] }) });
    expect(json(r)).not.toContain("추천이 시작돼요");
    expect(json(r)).not.toContain("추천해 드려요");
    expect(json(r)).toContain("취향 카드로 시작하기");
    expect(json(r)).toContain("카드 고르러 가기");
  });

  it("offers a retry instead of the taste CTA when the request failed", async () => {
    const onRetry = jest.fn();
    const r = await mount({ data: undefined, isError: true, onRetry });
    expect(r.root.findAllByProps({ testID: "home-taste-cta" })).toHaveLength(0);
    await act(async () => {
      r.root.findByProps({ testID: "home-ai-retry" }).props.onPress();
    });
    expect(onRetry).toHaveBeenCalled();
  });

  it("shows the CTA when the backend reports ready but sends nothing", async () => {
    const r = await mount({ data: recommendations({ items: [] }) });
    expect(r.root.findAllByProps({ testID: "spot-grid" })).toHaveLength(0);
    expect(r.root.findAllByProps({ testID: "home-taste-cta" }).length).toBeGreaterThan(0);
  });

  it("opens the taste picker once the auth gate passes", async () => {
    const r = await mount({ data: recommendations({ ready: false, savedCount: 0, items: [] }) });
    await act(async () => {
      r.root.findByProps({ testID: "home-taste-cta" }).props.onPress();
    });
    expect(gate).toHaveBeenCalledWith("save");
    expect(router.push).toHaveBeenCalledWith("/taste");
  });

  it("does not open the picker when the user declines to sign in", async () => {
    gate.mockResolvedValue(false);
    const r = await mount({ data: recommendations({ ready: false, savedCount: 0, items: [] }) });
    await act(async () => {
      r.root.findByProps({ testID: "home-taste-cta" }).props.onPress();
    });
    expect(router.push).not.toHaveBeenCalled();
  });
});
