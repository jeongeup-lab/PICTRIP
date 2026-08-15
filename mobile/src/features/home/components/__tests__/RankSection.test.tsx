import renderer, { act } from "react-test-renderer";
import { RankSection } from "@/features/home/components/RankSection";
import type { HomeSpotCard } from "@/features/home/api";

jest.mock("@/features/home/components/SpotGrid", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    SpotGrid: ({ cards }: { cards: { contentId: string }[] }) =>
      React.createElement(
        View,
        { testID: "spot-grid" },
        cards.map((c) => React.createElement(View, { key: c.contentId, testID: "grid-item" })),
      ),
  };
});

function cards(n: number): HomeSpotCard[] {
  return Array.from({ length: n }, (_, i) => ({
    contentId: `c${i + 1}`,
    title: `스팟 ${i + 1}`,
    regionLabel: "부산광역시 사하구",
    imageUrl: null,
    rank: i + 1,
    dist: 100 * (i + 1),
    category: null,
    tag: null,
    anchorTitle: null,
  }));
}

async function mount(props: Partial<Parameters<typeof RankSection>[0]> = {}) {
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(
      <RankSection
        title="지금 주변 인기 장소"
        note="9분 전 업데이트"
        cards={cards(10)}
        isLoading={false}
        isError={false}
        onRetry={() => {}}
        {...props}
      />,
    );
  });
  return tree!;
}

const items = (r: renderer.ReactTestRenderer) =>
  r.root.findAllByProps({ testID: "grid-item" }).filter((n) => typeof n.type === "string");

afterEach(() => jest.clearAllMocks());

describe("RankSection", () => {
  it("shows the first four cards behind a 더보기 expander", async () => {
    const r = await mount();
    expect(items(r)).toHaveLength(4);
    expect(JSON.stringify(r.toJSON())).toContain("5~10위 더보기");
  });

  it("expands to the full ranking and collapses again", async () => {
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "home-rank-expand" }).props.onPress();
    });
    expect(items(r)).toHaveLength(10);
    expect(JSON.stringify(r.toJSON())).toContain("접기");
    await act(async () => {
      r.root.findByProps({ testID: "home-rank-expand" }).props.onPress();
    });
    expect(items(r)).toHaveLength(4);
  });

  it("hides the expander when the ranking fits in one screen", async () => {
    const r = await mount({ cards: cards(4) });
    expect(r.root.findAllByProps({ testID: "home-rank-expand" })).toHaveLength(0);
  });

  it("renders the update note next to the title", async () => {
    const r = await mount();
    expect(r.root.findByProps({ testID: "home-section-note" }).props.children).toBe(
      "9분 전 업데이트",
    );
  });

  it("offers a retry that refetches when the section fails", async () => {
    const onRetry = jest.fn();
    const r = await mount({ cards: [], isError: true, onRetry });
    await act(async () => {
      r.root.findByProps({ testID: "home-rank-retry" }).props.onPress();
    });
    expect(onRetry).toHaveBeenCalled();
    expect(r.root.findAllByProps({ testID: "spot-grid" })).toHaveLength(0);
  });

  it("shows skeletons instead of cards while the first page loads", async () => {
    const r = await mount({ cards: [], isLoading: true });
    expect(r.root.findAllByProps({ testID: "spot-grid" })).toHaveLength(0);
    expect(r.root.findAllByProps({ testID: "home-rank-expand" })).toHaveLength(0);
  });
});
