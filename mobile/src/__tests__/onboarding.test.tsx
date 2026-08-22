import renderer, { act } from "react-test-renderer";
import { StyleSheet, Text } from "react-native";
import { router } from "expo-router";
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
jest.mock("@/lib/storage", () => ({
  setOnboardingSeen: jest.fn(),
  getAiTransferConsent: jest.fn(async () => false),
  setAiTransferConsent: jest.fn(async () => {}),
}));
jest.mock("@/features/consent/api", () => ({ putAiTransferConsent: jest.fn(async () => ({})) }));
jest.mock("@/features/consent/queries", () => ({ useConsents: () => ({ data: undefined }) }));
jest.mock("@/features/map/usecases/request-location", () => ({
  getPermissionStatus: jest.fn().mockResolvedValue("denied"),
  requestPermission: jest.fn().mockResolvedValue("denied"),
}));

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

describe("Onboarding access notice", () => {
  let tree: renderer.ReactTestRenderer | null = null;

  afterEach(() => {
    act(() => tree?.unmount());
    tree = null;
  });

  const flatten = (node: unknown): string =>
    Array.isArray(node)
      ? node.map(flatten).join("")
      : typeof node === "string" || typeof node === "number"
        ? String(node)
        : "";

  const texts = (t: renderer.ReactTestRenderer) =>
    t.root.findAllByType(Text).map((n) => flatten(n.props.children));

  const pressLabel = (t: renderer.ReactTestRenderer, label: string) => {
    const labelNode = t.root.findAllByType(Text).find((n) => flatten(n.props.children) === label);
    let node = labelNode?.parent ?? null;
    while (node && typeof node.props.onPress !== "function") node = node.parent;
    if (!node) throw new Error(`no pressable ancestor for "${label}"`);
    act(() => node.props.onPress());
  };

  const acceptTerms = (t: renderer.ReactTestRenderer) => {
    act(() => t.root.findAll((n) => n.props?.testID === "terms-agree-all")[0].props.onPress());
    act(() => t.root.findAll((n) => n.props?.testID === "terms-cta")[0].props.onPress());
  };

  it("routes every tour exit into the terms list before the access notice", async () => {
    await act(async () => {
      tree = renderer.create(<Onboarding />);
    });

    expect(texts(tree!)).not.toContain("필수적 접근 권한");

    pressLabel(tree!, "건너뛰기");

    expect(texts(tree!).join("\n")).toContain("약관에 동의해 주세요");
    expect(texts(tree!).join("\n")).not.toContain("필수적 접근 권한");

    acceptTerms(tree!);

    expect(texts(tree!).join("\n")).toContain("필수적 접근 권한");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("does not let the required rows be skipped", async () => {
    await act(async () => {
      tree = renderer.create(<Onboarding />);
    });
    pressLabel(tree!, "건너뛰기");

    const cta = tree!.root.findAll((n) => n.props?.testID === "terms-cta")[0];
    expect(cta.props.accessibilityState?.disabled ?? cta.props.disabled).toBe(true);
  });

  it("records the cross-border choice made in the list", async () => {
    const storage = jest.requireMock("@/lib/storage") as { setAiTransferConsent: jest.Mock };
    await act(async () => {
      tree = renderer.create(<Onboarding />);
    });
    pressLabel(tree!, "건너뛰기");

    await act(async () => {
      acceptTerms(tree!);
    });

    expect(storage.setAiTransferConsent).toHaveBeenCalledWith(true);
  });

  it("asks for location permission once when it was never decided", async () => {
    const loc = jest.requireMock("@/features/map/usecases/request-location") as {
      getPermissionStatus: jest.Mock;
      requestPermission: jest.Mock;
    };
    loc.getPermissionStatus.mockResolvedValueOnce("undetermined");

    await act(async () => {
      tree = renderer.create(<Onboarding />);
    });
    pressLabel(tree!, "건너뛰기");
    acceptTerms(tree!);
    await act(async () => {
      tree!.root.findAll((n) => n.props?.testID === "access-confirm")[0].props.onPress();
    });

    expect(loc.requestPermission).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith("/(tabs)");
  });
});
