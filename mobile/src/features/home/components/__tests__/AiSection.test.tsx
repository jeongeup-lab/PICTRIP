import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { AiSection, FALLBACK_CAPTION, tasteCaption } from "@/features/home/components/AiSection";
import type { HomeSpotCard, Recommendations } from "@/features/home/api";

const mockShown: string[][] = [];

jest.mock("@/features/home/components/SpotGrid", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    GridSkeleton: () => React.createElement(View, { testID: "grid-skeleton" }),
    SpotGrid: ({ cards }: { cards: HomeSpotCard[] }) => {
      mockShown.push(cards.map((c) => c.contentId));
      return React.createElement(View, { testID: "spot-grid" });
    },
  };
});

const shown = () => mockShown[mockShown.length - 1] ?? [];

beforeEach(() => {
  mockShown.length = 0;
});

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
  lat: null,
  lng: null,
  ...over,
});

const recommendations = (over: Partial<Recommendations> = {}): Recommendations => ({
  ready: true,
  savedCount: 5,
  minSaved: 3,
  items: [card()],
  ...over,
});

const texts = (r: renderer.ReactTestRenderer) =>
  r.root
    .findAllByType(Text)
    .flatMap((n) => (Array.isArray(n.props.children) ? n.props.children : [n.props.children]))
    .filter((c): c is string => typeof c === "string");

async function mount(props: Partial<Parameters<typeof AiSection>[0]> = {}) {
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(
      <AiSection
        displayName="Leesinseong"
        data={recommendations()}
        fallbackCards={[]}
        isLoading={false}
        isError={false}
        onRetry={jest.fn()}
        {...props}
      />,
    );
  });
  return tree!;
}

describe("AiSection", () => {
  it("greets the signed-in user by name", async () => {
    const r = await mount();
    expect(texts(r)).toContain("Leesinseong");
  });

  it("falls back to a neutral name for a guest", async () => {
    const r = await mount({ displayName: null });
    expect(texts(r)).toContain("여행자");
  });

  it("names the scrap count behind a ready recommendation", async () => {
    const r = await mount({ data: recommendations({ savedCount: 7 }) });
    expect(texts(r)).toContain(tasteCaption(7));
    expect(shown()).toEqual(["c1"]);
  });

  it("shows random picks instead of an empty grid before the minimum saves", async () => {
    const r = await mount({
      data: recommendations({ ready: false, savedCount: 1, items: [] }),
      fallbackCards: [card({ contentId: "f1" }), card({ contentId: "f2" })],
    });
    expect(texts(r)).toContain(FALLBACK_CAPTION);
    expect(shown()).toEqual(["f1", "f2"]);
  });

  it("admits the fallback when the backend reports ready but sends nothing", async () => {
    const r = await mount({
      data: recommendations({ ready: true, items: [] }),
      fallbackCards: [card({ contentId: "f1" })],
    });
    expect(texts(r)).toContain(FALLBACK_CAPTION);
  });

  it("caps the grid so the home page stays short", async () => {
    const many = Array.from({ length: 9 }, (_, i) => card({ contentId: `c${i}` }));
    await mount({ data: recommendations({ items: many }) });
    expect(shown()).toHaveLength(4);
  });

  it("offers a retry when the request failed", async () => {
    const r = await mount({ isError: true, onRetry: jest.fn() });
    expect(r.root.findAllByProps({ testID: "home-ai-retry" }).length).toBeGreaterThan(0);
    expect(r.root.findAllByProps({ testID: "spot-grid" })).toHaveLength(0);
  });

  it("keeps a taste picker out of the home screen", async () => {
    const r = await mount({ data: recommendations({ ready: false, items: [] }) });
    expect(r.root.findAllByProps({ testID: "home-taste-cta" })).toHaveLength(0);
  });
});
