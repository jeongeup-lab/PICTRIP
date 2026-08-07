import renderer, { act } from "react-test-renderer";
import ProfileTab from "@/app/(tabs)/profile";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useSavedList } from "@/features/saved/queries";
import { StatTiles } from "@/features/profile/components/StatTiles";
import { daysSince } from "@/features/profile/lib/stats";
import type { SpotCard, User } from "@/lib/api-types";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/saved/queries", () => ({ useSavedList: jest.fn() }));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));
jest.mock("@/features/profile/hooks/use-app-permissions", () => ({
  PERM_LABEL: { granted: "허용됨", denied: "꺼짐", undetermined: "미설정" },
  useAppPermissions: () => ({ location: "granted", photos: null, camera: null }),
}));
jest.mock("@/features/profile/components/StatTiles", () => ({ StatTiles: jest.fn(() => null) }));

const useSavedListMock = useSavedList as jest.Mock;
const StatTilesMock = StatTiles as unknown as jest.Mock;

const USER: User = {
  id: 7,
  displayName: "이신성",
  email: "sinseong@example.com",
  avatarUrl: null,
  isOnboarded: true,
  createdAt: "2026-03-14T09:00:00Z",
};

const spot = (contentId: string, addr1: string): SpotCard => ({
  contentId,
  title: `spot-${contentId}`,
  firstImageUrl: `https://img/${contentId}.jpg`,
  addr1,
  mapx: null,
  mapy: null,
  category: null,
});

let mounted: renderer.ReactTestRenderer | null = null;

async function mount() {
  await act(async () => {
    mounted = renderer.create(<ProfileTab />);
  });
  return mounted!;
}

const has = (tree: renderer.ReactTestRenderer, testID: string) =>
  tree.root.findAllByProps({ testID }).length > 0;

beforeEach(() => {
  useSavedListMock.mockReturnValue({ data: [] });
  useAuthStore.setState({ user: null, isAuthenticated: false, accessToken: null });
});

afterEach(async () => {
  await act(async () => {
    mounted?.unmount();
  });
  mounted = null;
  jest.clearAllMocks();
});

describe("ProfileTab", () => {
  it("shows the guest hero and blanks the stats when logged out", async () => {
    const tree = await mount();
    expect(has(tree, "guest-hero")).toBe(true);
    expect(has(tree, "profile-hero")).toBe(false);
    expect(StatTilesMock.mock.calls[0][0].stats).toBeNull();
  });

  it("shows the profile hero with saved, region and membership counts when logged in", async () => {
    useAuthStore.setState({ user: USER, isAuthenticated: true, accessToken: "token" });
    useSavedListMock.mockReturnValue({
      data: [spot("1", "경남 통영시"), spot("2", "전남 여수시")],
    });

    const tree = await mount();

    expect(has(tree, "profile-hero")).toBe(true);
    expect(has(tree, "guest-hero")).toBe(false);
    expect(StatTilesMock.mock.calls[0][0].stats).toEqual({
      saved: 2,
      regions: 2,
      days: daysSince(USER.createdAt, Date.now()),
      partial: false,
    });
  });
});
