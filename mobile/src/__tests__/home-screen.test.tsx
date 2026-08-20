import renderer, { act } from "react-test-renderer";
import { ScrollView, Text } from "react-native";
import HomeScreen from "@/app/(tabs)/index";
import { useHomeLocation } from "@/features/home/hooks/use-home-location";
import {
  useCuration,
  useNearby,
  useRecommendations,
  useRegionLabel,
  useTrending,
} from "@/features/home/queries";
import { queryClient } from "@/lib/query-client";
import type { HomeSpotCard } from "@/features/home/api";

jest.mock("expo-router", () => ({
  router: { push: jest.fn() },
  useScrollToTop: jest.fn(),
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/home/hooks/use-home-location", () => ({ useHomeLocation: jest.fn() }));
jest.mock("@/features/home/queries", () => ({
  useNearby: jest.fn(),
  useTrending: jest.fn(),
  useCuration: jest.fn(),
  useRegionLabel: jest.fn(),
  useRecommendations: jest.fn(),
}));
jest.mock("@/features/channels/components/ChannelChips", () => {
  const React = require("react");
  const { Pressable } = require("react-native");
  return {
    ChannelChips: ({ onOpen }: { onOpen: (k: string) => void }) =>
      React.createElement(Pressable, {
        testID: "channel-chips",
        onPress: () => onOpen("hidden"),
      }),
  };
});
jest.mock("@/features/home/components/NearbyMapCard", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    NearbyMapCard: ({ title, cards }: { title: string; cards: { contentId: string }[] }) =>
      React.createElement(View, {
        testID: "map-card",
        accessibilityLabel: title,
        accessibilityHint: cards.map((c) => c.contentId).join(","),
      }),
  };
});
jest.mock("@/features/home/components/CurationSection", () => {
  const React = require("react");
  const { Pressable } = require("react-native");
  return {
    CurationSection: ({ onOpenSpot }: { onOpenSpot: (id: string) => void }) =>
      React.createElement(Pressable, {
        testID: "curation",
        onPress: () => onOpenSpot("cur-1"),
      }),
  };
});
jest.mock("@/features/home/components/RankList", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    RankList: ({ title, cards }: { title: string; cards: { contentId: string }[] }) =>
      React.createElement(View, {
        testID: "rank-list",
        accessibilityLabel: title,
        accessibilityHint: cards.map((c) => c.contentId).join(","),
      }),
  };
});
jest.mock("@/features/home/components/AiSection", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    AiSection: ({ displayName }: { displayName: string | null }) =>
      React.createElement(View, { testID: "ai-section", accessibilityLabel: displayName ?? "" }),
  };
});

const mockLocation = useHomeLocation as jest.Mock;
const mockNearby = useNearby as jest.Mock;
const mockTrending = useTrending as jest.Mock;
const mockCuration = useCuration as jest.Mock;
const mockRegion = useRegionLabel as jest.Mock;
const mockRecommendations = useRecommendations as jest.Mock;
const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };

const COORDS = { lat: 37.54, lng: 127.07 };

function card(contentId: string): HomeSpotCard {
  return {
    contentId,
    title: `스팟 ${contentId}`,
    regionLabel: "서울특별시 광진구",
    imageUrl: null,
    rank: 1,
    dist: 1000,
    category: null,
    tag: null,
    anchorTitle: null,
    lat: 37.54,
    lng: 127.07,
  };
}

function query(items: HomeSpotCard[], over: Record<string, unknown> = {}) {
  return {
    data: { items },
    isLoading: false,
    isError: false,
    isFetching: false,
    dataUpdatedAt: Date.now(),
    refetch: jest.fn(),
    ...over,
  };
}

let request: jest.Mock;

beforeEach(() => {
  request = jest.fn(async () => {});
  mockLocation.mockReturnValue({ coords: COORDS, status: "granted", request });
  mockNearby.mockReturnValue(query([card("near-1")]));
  mockTrending.mockReturnValue(query([card("trend-1")]));
  mockCuration.mockReturnValue({ data: undefined, isLoading: false });
  mockRegion.mockReturnValue({ data: { label: "광진구 화양동" } });
  mockRecommendations.mockReturnValue({ data: undefined, isLoading: false });
});

let mounted: renderer.ReactTestRenderer | null = null;

afterEach(() => {
  act(() => mounted?.unmount());
  mounted = null;
  jest.clearAllMocks();
});

async function mount() {
  await act(async () => {
    mounted = renderer.create(<HomeScreen />);
  });
  return mounted!;
}

const ranks = (r: renderer.ReactTestRenderer) => r.root.findByProps({ testID: "rank-list" });
const texts = (r: renderer.ReactTestRenderer) =>
  r.root
    .findAllByType(Text)
    .flatMap((n) => (Array.isArray(n.props.children) ? n.props.children : [n.props.children]))
    .filter((c): c is string => typeof c === "string");

describe("HomeScreen", () => {
  it("leads with the map instead of a wordmark", async () => {
    const r = await mount();
    expect(r.root.findAllByProps({ children: "PICTRIP" })).toHaveLength(0);
    expect(r.root.findAllByProps({ testID: "map-card" }).length).toBeGreaterThan(0);
  });

  it("names today and the resolved region in the header", async () => {
    const r = await mount();
    expect(texts(r).some((t) => t.includes("광진구 화양동"))).toBe(true);
    expect(texts(r)).toContain("오늘, 이 근처");
  });

  it("feeds the map the same cards as the ranking", async () => {
    const r = await mount();
    expect(r.root.findByProps({ testID: "map-card" }).props.accessibilityHint).toBe("near-1");
    expect(ranks(r).props.accessibilityHint).toBe("near-1");
  });

  it("swaps to the nationwide ranking when the header title is tapped", async () => {
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "home-scope" }).props.onPress();
    });
    expect(texts(r)).toContain("오늘, 전국");
    expect(ranks(r).props.accessibilityLabel).toBe("전국 인기 순위");
    expect(ranks(r).props.accessibilityHint).toBe("trend-1");
  });

  it("falls back to the nationwide ranking when nothing is nearby", async () => {
    mockNearby.mockReturnValue(query([]));
    const r = await mount();
    expect(ranks(r).props.accessibilityLabel).toBe("전국 인기 순위");
    expect(ranks(r).props.accessibilityHint).toBe("trend-1");
  });

  it("keeps showing the nearby ranking while it is still loading", async () => {
    mockNearby.mockReturnValue(query([], { isLoading: true }));
    const r = await mount();
    expect(ranks(r).props.accessibilityLabel).toBe("주변 인기 순위");
  });

  it("prompts for location when permission is missing", async () => {
    mockLocation.mockReturnValue({ coords: null, status: "denied", request });
    const r = await mount();
    expect(ranks(r).props.accessibilityHint).toBe("trend-1");
    await act(async () => {
      r.root.findByProps({ testID: "home-location-cta" }).props.onPress();
    });
    expect(request).toHaveBeenCalled();
  });

  it("collapses the ranking past the seventh place and expands on demand", async () => {
    mockNearby.mockReturnValue(query(Array.from({ length: 10 }, (_, i) => card(`n${i}`))));
    const r = await mount();
    expect(ranks(r).props.accessibilityHint.split(",")).toHaveLength(7);
    await act(async () => {
      r.root.findByProps({ testID: "home-rank-expand" }).props.onPress();
    });
    expect(ranks(r).props.accessibilityHint.split(",")).toHaveLength(10);
  });

  it("keeps the channel viewer reachable from the chip rail", async () => {
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "channel-chips" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/channels?start=hidden");
  });

  it("opens a spot picked from the curation carousel", async () => {
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "curation" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/spots/cur-1");
  });

  it("renders the AI section under the ranking", async () => {
    const r = await mount();
    expect(r.root.findAllByProps({ testID: "ai-section" }).length).toBeGreaterThan(0);
  });

  it("pull-to-refresh invalidates the home queries and the channel rail", async () => {
    const invalidate = jest.spyOn(queryClient, "invalidateQueries");
    const r = await mount();
    const list = r.root.findAllByType(ScrollView)[0];
    await act(async () => {
      list.props.refreshControl.props.onRefresh();
    });
    const predicate = invalidate.mock.calls[0][0]?.predicate as unknown as (q: {
      queryKey: unknown[];
    }) => boolean;
    expect(predicate({ queryKey: ["home-nearby", null] })).toBe(true);
    expect(predicate({ queryKey: ["home-curation"] })).toBe(true);
    expect(predicate({ queryKey: ["channels"] })).toBe(true);
    expect(predicate({ queryKey: ["saved"] })).toBe(false);
    invalidate.mockRestore();
  });

  it("wires the scroll view into the tab re-tap scroll-to-top hook", async () => {
    const { useScrollToTop } = jest.requireMock("expo-router") as { useScrollToTop: jest.Mock };
    await mount();
    expect(useScrollToTop).toHaveBeenCalled();
  });
});
