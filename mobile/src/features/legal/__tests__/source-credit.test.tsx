import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { SourceCredit } from "@/features/legal/components/SourceCredit";
import { LEGAL_DOCS, findLegalDoc, legalUrl } from "@/features/legal/constants";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));

const routerMock = jest.requireMock<{ router: { push: jest.Mock } }>("expo-router").router;

describe("SourceCredit", () => {
  afterEach(() => jest.clearAllMocks());

  it("names 한국관광공사 as the source of the tourism data", async () => {
    let tree: renderer.ReactTestRenderer | null = null;
    await act(async () => {
      tree = renderer.create(<SourceCredit />);
    });
    const shown = tree!.root
      .findAllByType(Text)
      .map((node) => JSON.stringify(node.props.children))
      .join("|");

    expect(shown).toContain("한국관광공사");
  });

  it("opens the data-sources document", async () => {
    let tree: renderer.ReactTestRenderer | null = null;
    await act(async () => {
      tree = renderer.create(<SourceCredit />);
    });
    await act(async () => {
      tree!.root.findByProps({ testID: "source-credit" }).props.onPress();
    });

    expect(routerMock.push).toHaveBeenCalledWith("/legal/data-sources");
  });
});

describe("legal documents", () => {
  it("reaches the data-sources document from inside the app", () => {
    expect(LEGAL_DOCS.map((doc) => doc.slug)).toContain("data-sources");
    expect(findLegalDoc("data-sources")?.title).toBe("데이터 출처와 이용 조건");
    expect(legalUrl("data-sources")).toBe("https://pictrip.org/legal/data-sources");
  });
});
