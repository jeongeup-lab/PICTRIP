import renderer, { act } from "react-test-renderer";
import { RefreshControl } from "react-native";
import HomeScreen from "@/app/(tabs)/index";
import { useHomeFeed } from "@/features/feed/queries";

jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn() },
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: (props: { children?: unknown }) => props.children,
}));
jest.mock("@/features/feed/queries", () => ({ useHomeFeed: jest.fn() }));

const useHomeFeedMock = useHomeFeed as jest.Mock;
const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };

const feedState = (overrides: Record<string, unknown>) => ({
  data: undefined,
  isLoading: false,
  isError: false,
  isRefetching: false,
  refetch: jest.fn(),
  ...overrides,
});

describe("HomeScreen", () => {
  let tree: renderer.ReactTestRenderer | null = null;

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
    jest.clearAllMocks();
  });

  it("shows the empty placeholder when heroes and rails are both empty", async () => {
    useHomeFeedMock.mockReturnValue(feedState({ data: { heroes: [], rails: [] } }));
    await act(async () => {
      tree = renderer.create(<HomeScreen />);
    });

    // toJSON() is not serializable here (refreshControl embeds a React element),
    // so assert on the rendered element tree instead.
    expect(
      tree!.root.findAllByProps({ children: "곧 새로운 큐레이션을 준비할게요" }).length,
    ).toBeGreaterThan(0);
  });

  it("renders footer legal links that route to terms, privacy and data-sources", async () => {
    useHomeFeedMock.mockReturnValue(feedState({ data: { heroes: [], rails: [] } }));
    await act(async () => {
      tree = renderer.create(<HomeScreen />);
    });

    await act(async () => {
      tree!.root.findByProps({ testID: "footer-terms" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/legal/terms");

    await act(async () => {
      tree!.root.findByProps({ testID: "footer-privacy" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/legal/privacy");

    await act(async () => {
      tree!.root.findByProps({ testID: "footer-data-source" }).props.onPress();
    });
    expect(router.push).toHaveBeenCalledWith("/legal/data-sources");
  });

  it("wires pull-to-refresh to a feed refetch", async () => {
    const refetch = jest.fn();
    useHomeFeedMock.mockReturnValue(feedState({ data: { heroes: [], rails: [] }, refetch }));
    await act(async () => {
      tree = renderer.create(<HomeScreen />);
    });

    await act(async () => {
      tree!.root.findByType(RefreshControl).props.onRefresh();
    });
    expect(refetch).toHaveBeenCalled();
  });
});
