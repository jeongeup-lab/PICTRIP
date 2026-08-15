import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import LegalListScreen from "@/app/legal/index";
import { LEGAL_DOCS } from "@/features/legal/constants";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), back: jest.fn() },
  useFocusEffect: (effect: () => void | (() => void)) =>
    jest.requireActual<typeof import("react")>("react").useEffect(effect, [effect]),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

let mounted: renderer.ReactTestRenderer | null = null;

async function mount() {
  await act(async () => {
    mounted = renderer.create(<LegalListScreen />);
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

describe("LegalListScreen", () => {
  it("lists every legal document", async () => {
    const tree = await mount();
    LEGAL_DOCS.forEach((doc) => {
      const rows = tree.root.findAllByProps({ testID: `legal-${doc.slug}` });
      expect(rows.length).toBeGreaterThan(0);
    });
  });

  it("contains canonical documents without consent history", async () => {
    const tree = await mount();
    expect(texts(tree)).not.toContain("내 동의 내역");
    expect(tree.root.findAllByProps({ testID: "consent-terms" })).toHaveLength(0);
  });
});
