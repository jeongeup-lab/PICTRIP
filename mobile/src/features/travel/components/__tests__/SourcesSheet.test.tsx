import renderer, { act } from "react-test-renderer";
import { Linking, Modal } from "react-native";
import { SOURCES_TITLE, SourcesSheet } from "@/features/travel/components/SourcesSheet";
import type { SourceItem } from "@/features/travel/api";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const BLOG_URL = "https://blog.naver.com/pictrip/42";

const items: SourceItem[] = [
  {
    kind: "naver_blog",
    title: "제주 계곡 산책 후기",
    url: BLOG_URL,
    date: "20260801",
  },
  {
    kind: "kto",
    title: "관광지 원천 데이터",
  },
  {
    kind: "kakao",
    title: "카카오 장소 검색",
    url: "https://place.map.kakao.com/42",
  },
];

async function mount(onClose = jest.fn()) {
  let tree: renderer.ReactTestRenderer | undefined;
  await act(async () => {
    tree = renderer.create(<SourcesSheet visible items={items} onClose={onClose} />);
  });
  if (tree === undefined) throw new Error("SourcesSheet did not mount");
  return tree;
}

function rendered(tree: renderer.ReactTestRenderer): string {
  return JSON.stringify(tree.toJSON());
}

describe("SourcesSheet", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("블로그가 아닌 입력은 보이지 않고 소스 제목은 유지한다", async () => {
    const tree = await mount();
    const output = rendered(tree);

    expect(output).toContain(SOURCES_TITLE);
    expect(output).not.toContain("관광지 원천 데이터");
    expect(output).not.toContain("한국관광공사 TourAPI");
    expect(output).not.toContain("관광지 정보 출처");
    expect(output).not.toContain("카카오 장소 검색");
    expect(tree.root.findAllByProps({ testID: "travel-source-kto" })).toHaveLength(0);
  });

  it("날짜가 있는 블로그 근거를 열 수 있다", async () => {
    const openUrl = jest.spyOn(Linking, "openURL").mockResolvedValue(undefined);
    const tree = await mount();

    expect(rendered(tree)).toContain("2026.08.01");
    await act(async () => {
      tree.root.findByProps({ testID: "travel-source-row" }).props.onPress();
    });

    expect(openUrl).toHaveBeenCalledWith(BLOG_URL);
  });

  it("닫기 요청을 전달한다", async () => {
    const onClose = jest.fn();
    const tree = await mount(onClose);

    await act(async () => {
      tree.root.findByType(Modal).props.onRequestClose();
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("닫기 버튼을 누르면 닫기 요청을 전달한다", async () => {
    const onClose = jest.fn();
    const tree = await mount(onClose);

    await act(async () => {
      tree.root.findByProps({ testID: "travel-sources-close" }).props.onPress();
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
