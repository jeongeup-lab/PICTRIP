import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import SettingsScreen from "@/app/settings";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), back: jest.fn() },
  useFocusEffect: (effect: () => void | (() => void)) =>
    jest.requireActual<typeof import("react")>("react").useEffect(effect, [effect]),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/profile/hooks/use-app-permissions", () => ({
  PERM_LABEL: { granted: "허용됨", denied: "꺼짐", undetermined: "미설정" },
  useAppPermissions: () => ({ location: "granted", photos: "denied", camera: "undetermined" }),
}));
jest.mock("@/features/consent/queries", () => ({
  useConsents: jest.fn(() => ({ data: undefined })),
  useUpdateConsent: jest.fn(() => ({ mutate: jest.fn() })),
}));
jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn(async () => ({ granted: true })),
}));

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

  it("contains only system permission rows", async () => {
    const tree = await mount();
    const shown = texts(tree);
    expect(shown).toContain("기기 권한");
    expect(shown).not.toContain("사진으로 찾기에 올린 이미지");
    expect(shown).not.toContain("약관·정책");
    expect(shown).not.toContain("앱 버전");
  });

  it("offers no notification or export rows", async () => {
    const tree = await mount();
    expect(tree.root.findAllByProps({ testID: "export-saved" })).toHaveLength(0);
    expect(
      tree.root.findAll((n) => String(n.props.testID ?? "").startsWith("notify-")),
    ).toHaveLength(0);
    expect(texts(tree)).not.toContain("알림");
  });
});
