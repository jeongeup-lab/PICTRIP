import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import LegalListScreen from "@/app/legal/index";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useConsents, useUpdateConsent } from "@/features/consent/queries";
import { LEGAL_DOCS } from "@/features/legal/constants";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), back: jest.fn() },
  useFocusEffect: (effect: () => void | (() => void)) =>
    jest.requireActual<typeof import("react")>("react").useEffect(effect, [effect]),
}));
jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ granted: false }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/consent/queries", () => ({
  useConsents: jest.fn(),
  useUpdateConsent: jest.fn(),
}));

const useConsentsMock = useConsents as jest.Mock;
const useUpdateConsentMock = useUpdateConsent as jest.Mock;
const mutate = jest.fn();

const CONSENTS = {
  locationConsent: true,
  termsVersion: "2026-06-22",
  consentedAt: "2026-03-14T09:00:00Z",
};

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

beforeEach(() => {
  useConsentsMock.mockReturnValue({ data: CONSENTS, isLoading: false, isError: false });
  useUpdateConsentMock.mockReturnValue({ mutate });
  useAuthStore.setState({ user: null, isAuthenticated: true, accessToken: "token" });
});

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
      expect(tree.root.findAllByProps({ testID: `legal-${doc.slug}` }).length).toBeGreaterThan(0);
    });
  });

  it("shows when the terms were agreed to", async () => {
    const tree = await mount();
    expect(texts(tree)).toContain("2026.03.14 동의");
    expect(texts(tree)).toContain("버전 2026-06-22");
  });

  it("offers no photo analysis consent", async () => {
    const tree = await mount();
    expect(texts(tree)).not.toContain("사진 분석");
    expect(tree.root.findAllByProps({ testID: "consent-location" }).length).toBeGreaterThan(0);
  });

  it("hides the consent history from guests", async () => {
    useAuthStore.setState({ isAuthenticated: false, accessToken: null });
    const tree = await mount();
    expect(tree.root.findAllByProps({ testID: "consent-terms" })).toHaveLength(0);
    expect(tree.root.findAllByProps({ testID: "legal-terms" }).length).toBeGreaterThan(0);
  });
});
