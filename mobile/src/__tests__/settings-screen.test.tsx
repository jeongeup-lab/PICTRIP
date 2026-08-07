import renderer, { act } from "react-test-renderer";
import { Share, Text } from "react-native";
import SettingsScreen from "@/app/settings";
import { useSavedList } from "@/features/saved/queries";
import { useNotificationPrefs } from "@/features/profile/stores/notification-prefs-store";
import { DEFAULT_NOTIFICATION_PREFS } from "@/features/profile/lib/notification-prefs";
import type { SpotCard } from "@/lib/api-types";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/saved/queries", () => ({ useSavedList: jest.fn() }));
jest.mock("@/features/profile/hooks/use-app-permissions", () => ({
  PERM_LABEL: { granted: "허용됨", denied: "꺼짐", undetermined: "미설정" },
  useAppPermissions: () => ({ location: "granted", photos: "denied", camera: "undetermined" }),
}));
jest.mock("@/lib/storage", () => ({
  getNotificationPrefsRaw: jest.fn(async () => null),
  setNotificationPrefsRaw: jest.fn(async () => undefined),
}));

const useSavedListMock = useSavedList as jest.Mock;

const SAVED: SpotCard[] = [
  {
    contentId: "126508",
    title: "소매물도",
    firstImageUrl: null,
    addr1: "경남 통영시",
    mapx: 128.5,
    mapy: 34.6,
    category: "자연관광지",
  },
];

let mounted: renderer.ReactTestRenderer | null = null;

async function mount() {
  await act(async () => {
    mounted = renderer.create(<SettingsScreen />);
  });
  return mounted!;
}

const texts = (tree: renderer.ReactTestRenderer) =>
  tree.root
    .findAllByType(Text)
    .map((node) => JSON.stringify(node.props.children))
    .join("|");

beforeEach(() => {
  useSavedListMock.mockReturnValue({ data: SAVED });
  useNotificationPrefs.setState({ prefs: DEFAULT_NOTIFICATION_PREFS, hydrated: false });
});

afterEach(async () => {
  await act(async () => {
    mounted?.unmount();
  });
  mounted = null;
  jest.clearAllMocks();
});

describe("SettingsScreen", () => {
  it("labels each OS permission with its real status", async () => {
    const tree = await mount();
    const shown = texts(tree);
    expect(shown).toContain("허용됨");
    expect(shown).toContain("꺼짐");
    expect(shown).toContain("미설정");
  });

  it("keeps a notification switch per topic", async () => {
    const tree = await mount();
    const toggle = tree.root.findAll(
      (n) => n.props.testID === "notify-crowding" && !!n.props.onValueChange,
    )[0];

    await act(async () => {
      toggle.props.onValueChange(true);
    });

    expect(useNotificationPrefs.getState().prefs).toEqual({
      savedNews: false,
      crowding: true,
      marketing: false,
    });
  });

  it("exports the saved list as CSV", async () => {
    const share = jest.spyOn(Share, "share").mockResolvedValue({ action: "sharedAction" });
    const tree = await mount();
    const row = tree.root.findAll((n) => n.props.testID === "export-saved" && !!n.props.onPress)[0];

    await act(async () => {
      row.props.onPress();
    });

    expect(share).toHaveBeenCalledTimes(1);
    expect(share.mock.calls[0][0]).toEqual({
      message:
        "contentId,title,address,category,lat,lng\n126508,소매물도,경남 통영시,자연관광지,34.6,128.5",
    });
    share.mockRestore();
  });

  it("hides the export row when there is nothing saved", async () => {
    useSavedListMock.mockReturnValue({ data: [] });
    const tree = await mount();
    expect(tree.root.findAllByProps({ testID: "export-saved" })).toHaveLength(0);
  });
});
