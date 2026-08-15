import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { AiConsentSheet } from "@/features/travel/components/AiConsentSheet";
import { AI_CONSENT } from "@/features/travel/lib/ai-consent";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const routerMock = jest.requireMock<{ router: { push: jest.Mock } }>("expo-router").router;

const render = async (props: Partial<Parameters<typeof AiConsentSheet>[0]> = {}) => {
  let tree: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    tree = renderer.create(
      <AiConsentSheet visible onAgree={jest.fn()} onDecline={jest.fn()} {...props} />,
    );
  });
  if (tree === null) throw new Error("sheet did not mount");
  return tree as renderer.ReactTestRenderer;
};

const textOf = (tree: renderer.ReactTestRenderer) =>
  tree.root
    .findAllByType(Text)
    .map((node) => JSON.stringify(node.props.children))
    .join("|");

describe("AiConsentSheet", () => {
  afterEach(() => jest.clearAllMocks());

  it("names the provider, what is sent, and what is not", async () => {
    const shown = textOf(await render());

    expect(shown).toContain("Google Gemini");
    expect(shown).toContain("Google LLC의 Gemini API로 전송됩니다");
    expect(shown).toContain("사진은 Gemini로 전송되지 않아요");
  });

  it("tells the user what still works if they decline", async () => {
    expect(textOf(await render())).toContain("사진으로 찾기와 둘러보기는 그대로 이용할 수 있어요");
  });

  it("routes to the privacy policy for the cross-border transfer notice", async () => {
    const tree = await render();

    await act(async () => {
      tree.root.findByProps({ testID: "ai-consent-policy" }).props.onPress();
    });

    expect(routerMock.push).toHaveBeenCalledWith("/legal/privacy");
  });

  it("reports agree and decline separately", async () => {
    const onAgree = jest.fn();
    const onDecline = jest.fn();
    const tree = await render({ onAgree, onDecline });

    await act(async () => {
      tree.root.findByProps({ testID: "ai-consent-agree" }).props.onPress();
    });
    expect(onAgree).toHaveBeenCalledTimes(1);
    expect(onDecline).not.toHaveBeenCalled();

    await act(async () => {
      tree.root.findByProps({ testID: "ai-consent-decline" }).props.onPress();
    });
    expect(onDecline).toHaveBeenCalledTimes(1);
  });

  it("treats a tap on the scrim as declining", async () => {
    const onDecline = jest.fn();
    const tree = await render({ onDecline });

    await act(async () => {
      tree.root.findByProps({ testID: "ai-consent-scrim" }).props.onPress();
    });

    expect(onDecline).toHaveBeenCalledTimes(1);
  });

  it("keeps the decline notice available to the caller", () => {
    expect(AI_CONSENT.declined).toBe("동의하지 않아 질문을 보내지 않았어요");
  });
});
