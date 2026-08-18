import renderer, { act } from "react-test-renderer";
import { Icon } from "@/components/Icon";
import { AssistantTurn, SOURCES_LABEL } from "@/features/travel/components/AssistantTurn";
import { SourcesSheet } from "@/features/travel/components/SourcesSheet";
import type { SourceItem } from "@/features/travel/api";
import type { ChatTurn } from "@/features/travel/stores/chat-store";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const KTO_SOURCE: SourceItem = {
  kind: "kto",
  title: "관광지 원천 데이터",
};

const BLOG_SOURCE: SourceItem = {
  kind: "naver_blog",
  title: "제주 계곡 산책 후기",
  url: "https://blog.naver.com/pictrip/42",
  date: "20260801",
};

const KAKAO_SOURCE: SourceItem = {
  kind: "kakao",
  title: "카카오 장소 검색",
  url: "https://place.map.kakao.com/42",
};

function turnWith(sources: SourceItem[]): ChatTurn {
  return {
    id: "assistant-1",
    question: "제주 계곡 추천해줘",
    photoUri: null,
    request: {
      message: "제주 계곡 추천해줘",
      photo: null,
      context: null,
      intent: null,
      patch: null,
      history: [],
    },
    status: "done",
    steps: [],
    text: "",
    spots: [],
    tagBasis: null,
    applied: [],
    refinements: [],
    sources,
    intent: null,
    errorCode: null,
  };
}

function mount(sources: SourceItem[]): renderer.ReactTestRenderer {
  let tree: renderer.ReactTestRenderer | undefined;
  act(() => {
    tree = renderer.create(
      <AssistantTurn
        turn={turnWith(sources)}
        latest={false}
        origin={null}
        onRetry={jest.fn()}
        onDetail={jest.fn()}
        onSaveToggle={jest.fn()}
        onNotice={jest.fn()}
        onFocusSpot={jest.fn()}
        onRefine={jest.fn()}
      />,
    );
  });
  if (tree === undefined) throw new Error("AssistantTurn did not mount");
  return tree;
}

describe("AssistantTurn sources", () => {
  const mounted: renderer.ReactTestRenderer[] = [];

  afterEach(() => {
    act(() => {
      for (const tree of mounted.splice(0)) tree.unmount();
    });
  });

  it("KTO-only sources do not render a trigger or reach the sheet", () => {
    const tree = mount([KTO_SOURCE]);
    mounted.push(tree);

    expect(tree.root.findAllByProps({ testID: "travel-sources" })).toHaveLength(0);
    expect(tree.root.findByType(SourcesSheet).props.items).toEqual([]);
  });

  it("a mixed response exposes only Naver blog sources in the trigger and sheet", () => {
    const tree = mount([KTO_SOURCE, KAKAO_SOURCE, BLOG_SOURCE]);
    mounted.push(tree);
    const trigger = tree.root.findByProps({ testID: "travel-sources" });

    expect(trigger.props.accessibilityLabel).toBe(`${SOURCES_LABEL} 1개 보기`);
    expect(trigger.findAllByType(Icon).map((icon) => icon.props.name)).toEqual(["globe"]);
    expect(tree.root.findByType(SourcesSheet).props.items).toEqual([BLOG_SOURCE]);
  });
});
