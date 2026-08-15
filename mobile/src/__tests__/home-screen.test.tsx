import renderer, { act } from "react-test-renderer";
import { ScrollView, Text } from "react-native";
import HomeScreen from "@/app/(tabs)/index";
import { useHomeLocation } from "@/features/home/hooks/use-home-location";
import {
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
  useRegionLabel: jest.fn(),
  useRecommendations: jest.fn(),
}));
jest.mock("@/features/channels/components/ChannelTiles", () => {
  const React = require("react");
  const { Pressable } = require("react-native");
  return {
    ChannelTiles: ({ onOpen }: { onOpen: (k: string) => void }) =>
      React.createElement(Pressable, {
        testID: "channel-tiles",
        onPress: () => onOpen("hidden"),
      }),
  };
});
jest.mock("@/features/home/components/RankSection", () => {
  const React = require("react");
  const { View } = require("react-native");
  return {
    RankSection: ({ title, cards }: { title: string; cards: HomeSpotCard[] }) =>
      React.createElement(View, {
        testID: "rank-section",
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

const rank = (r: renderer.ReactTestRenderer) => r.root.findByProps({ testID: "rank-section" });
const texts = (r: renderer.ReactTestRenderer) =>
  r.root
    .findAllByType(Text)
    .flatMap((n) => (Array.isArray(n.props.children) ? n.props.children : [n.props.children]))
    .filter((c): c is string => typeof c === "string");

describe("HomeScreen", () => {
  it("renders the PICTRIP wordmark", async () => {
    const r = await mount();
    expect(r.root.findAllByProps({ children: "PICTRIP" }).length).toBeGreaterThan(0);
  });

  it("keeps the channel rail and routes into the channel viewer", async () => {
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "channel-tiles" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/channels?start=hidden");
  });

  it("shows nearby cards under the region-named tab by default", async () => {
    const r = await mount();
    expect(texts(r)).toContain("광진구 화양동");
    expect(rank(r).props.accessibilityLabel).toBe("광진구 화양동 근처 인기 장소");
    expect(rank(r).props.accessibilityHint).toBe("near-1");
  });

  it("swaps to the nationwide ranking when the 전국 인기 tab is picked", async () => {
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "home-scope-national" }).props.onPress();
    });
    expect(rank(r).props.accessibilityLabel).toBe("전국 인기 장소");
    expect(rank(r).props.accessibilityHint).toBe("trend-1");
  });

  it("falls back to the national ranking and prompts for location when permission is missing", async () => {
    mockLocation.mockReturnValue({ coords: null, status: "denied", request });
    const r = await mount();
    expect(rank(r).props.accessibilityHint).toBe("trend-1");
    await act(async () => {
      r.root.findByProps({ testID: "home-location-cta" }).props.onPress();
    });
    expect(request).toHaveBeenCalled();
  });

  it("labels the tab 내 주변 until the reverse geocode lands", async () => {
    mockRegion.mockReturnValue({ data: undefined });
    const r = await mount();
    expect(texts(r)).toContain("내 주변");
  });

  it("asks for location when the user taps back to the nearby tab without coords", async () => {
    mockLocation.mockReturnValue({ coords: null, status: "denied", request });
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "home-scope-nearby" }).props.onPress();
    });
    expect(request).toHaveBeenCalled();
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
    expect(predicate({ queryKey: ["channels"] })).toBe(true);
    expect(predicate({ queryKey: ["saved"] })).toBe(false);
    invalidate.mockRestore();
  });

  it("wires the scroll view into the tab re-tap scroll-to-top hook", async () => {
    const { useScrollToTop } = jest.requireMock("expo-router") as { useScrollToTop: jest.Mock };
    await mount();
    expect(useScrollToTop).toHaveBeenCalled();
  });

  it("does not render a shorts player anywhere on the home screen", async () => {
    const r = await mount();
    expect(r.root.findAllByProps({ testID: "shorts-card" })).toHaveLength(0);
    expect(r.root.findAllByProps({ testID: "shorts-player-sheet" })).toHaveLength(0);
  });
});
