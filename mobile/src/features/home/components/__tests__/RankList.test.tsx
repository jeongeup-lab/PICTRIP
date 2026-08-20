import renderer, { act } from "react-test-renderer";
import { RankList, distanceLabel } from "@/features/home/components/RankList";
import type { HomeSpotCard } from "@/features/home/api";

function card(over: Partial<HomeSpotCard> = {}): HomeSpotCard {
  return {
    contentId: "c1",
    title: "감천문화마을",
    regionLabel: "부산광역시 사하구",
    imageUrl: null,
    rank: null,
    dist: null,
    category: "골목길, 문화거리",
    tag: null,
    anchorTitle: null,
    lat: null,
    lng: null,
    ...over,
  };
}

function hosts(r: renderer.ReactTestRenderer, testID: string) {
  return r.root.findAllByProps({ testID }).filter((n) => typeof n.type === "string");
}

let tree: renderer.ReactTestRenderer | null = null;

afterEach(() => {
  act(() => tree?.unmount());
  tree = null;
});

async function mount(props: Partial<Parameters<typeof RankList>[0]> = {}) {
  await act(async () => {
    tree = renderer.create(
      <RankList
        title="주변 인기 순위"
        note={null}
        cards={[card({ contentId: "a" }), card({ contentId: "b" })]}
        isLoading={false}
        isError={false}
        onRetry={jest.fn()}
        onOpenSpot={jest.fn()}
        {...props}
      />,
    );
  });
  return tree!;
}

describe("distanceLabel", () => {
  it("switches unit at a kilometre", () => {
    expect(distanceLabel(940)).toBe("940m");
    expect(distanceLabel(1000)).toBe("1.0km");
    expect(distanceLabel(2555)).toBe("2.6km");
  });

  it("says nothing when there is no distance to say", () => {
    expect(distanceLabel(null)).toBe("");
    expect(distanceLabel(0)).toBe("");
  });
});

describe("RankList", () => {
  it("renders a row per card", async () => {
    const r = await mount();
    expect(hosts(r, "home-rank-row").length).toBe(2);
  });

  it("shows skeleton rows instead of an empty list while loading", async () => {
    const r = await mount({ isLoading: true, cards: [] });
    expect(hosts(r, "home-rank-skeleton").length).toBe(1);
    expect(hosts(r, "home-rank-row").length).toBe(0);
  });

  it("offers a retry when the ranking fails", async () => {
    const onRetry = jest.fn();
    const r = await mount({ isError: true, cards: [], onRetry });
    await act(async () => {
      r.root.findByProps({ testID: "home-rank-retry" }).props.onPress();
    });
    expect(onRetry).toHaveBeenCalled();
  });

  it("opens the tapped spot", async () => {
    const onOpenSpot = jest.fn();
    const r = await mount({ onOpenSpot });
    await act(async () => {
      r.root
        .findAllByProps({ testID: "home-rank-row" })
        .filter((n) => typeof n.props.onPress === "function")[1]
        .props.onPress();
    });
    expect(onOpenSpot).toHaveBeenCalledWith("b");
  });
});
