import renderer, { act } from "react-test-renderer";
import { StyleSheet } from "react-native";
import Onboarding from "@/app/onboarding";

const INSET_TOP = 59;

jest.mock("react-native-safe-area-context", () => {
  const { View } = jest.requireActual("react-native");
  return {
    SafeAreaView: View,
    useSafeAreaInsets: () => ({ top: 59, bottom: 34, left: 0, right: 0 }),
  };
});
jest.mock("expo-router", () => ({ router: { replace: jest.fn() } }));
jest.mock("@/lib/storage", () => ({ setOnboardingSeen: jest.fn() }));

describe("Onboarding skip button", () => {
  let tree: renderer.ReactTestRenderer | null = null;

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
  });

  it("sits below the status-bar inset (absolute children ignore SafeAreaView padding)", async () => {
    await act(async () => {
      tree = renderer.create(<Onboarding />);
    });

    const label = tree!.root.find(
      (n) =>
        typeof n.type === "string" &&
        (n.type as string) === "Text" &&
        n.props.children === "건너뛰기",
    );
    let node = label.parent;
    let style: Record<string, unknown> | undefined;
    while (node) {
      const flat = StyleSheet.flatten(node.props.style) as Record<string, unknown> | undefined;
      if (flat?.position === "absolute") {
        style = flat;
        break;
      }
      node = node.parent;
    }

    expect(style).toBeDefined();
    expect(style!.top as number).toBeGreaterThanOrEqual(INSET_TOP);
  });
});
