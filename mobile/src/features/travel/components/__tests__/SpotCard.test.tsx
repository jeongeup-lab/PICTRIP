import renderer, { act } from "react-test-renderer";
import { StyleSheet, Text, type StyleProp, type ViewStyle } from "react-native";
import { SpotCard } from "@/features/travel/components/SpotCard";
import { RemoteImage } from "@/components/RemoteImage";
import type { TravelSpot } from "@/features/travel/api";
import { colors } from "@/constants/theme";

jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({ useSaveOptimistic: jest.fn() }));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const { useSaveOptimistic } = jest.requireMock("@/features/saved/hooks/use-save-optimistic") as {
  useSaveOptimistic: jest.Mock;
};
const { prefetchSpot } = jest.requireMock("@/features/spots/queries") as {
  prefetchSpot: jest.Mock;
};
const toggle = jest.fn();

const spot: TravelSpot = {
  contentId: "126508",
  title: "성산일출봉",
  regionLabel: "서귀포시",
  imageUrl: null,
  tag: "한산",
  lat: 33.4,
  lng: 126.9,
};

const base = {
  spot,
  index: 0,
  tagBasis: "혼잡도 8/3 예측 기준",
  distanceKm: 2.4,
  focused: false,
  onDetail: jest.fn(),
  onSaveToggle: jest.fn(),
  onMetricPress: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof SpotCard>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<SpotCard {...base} {...props} />);
  });
  return tree!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string =>
  tree.root
    .findAllByType(Text)
    .map((n) => flatten(n.props.children))
    .join("");

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root
    .findAllByProps({ testID: id })
    .find((n) => typeof n.props.onPress === "function");
}

function outermost(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAllByProps({ testID: id })[0];
}

function badgeFill(focused: boolean): unknown {
  const style = outermost(mount({ focused }), "travel-card-badge").props
    .style as StyleProp<ViewStyle>;
  return StyleSheet.flatten(style).backgroundColor;
}

beforeEach(() => {
  jest.clearAllMocks();
  toggle.mockResolvedValue(true);
  useSaveOptimistic.mockReturnValue({ saved: false, toggle });
});

describe("SpotCard", () => {
  it("지도 핀과 같은 번호를 단다", () => {
    expect(texts(mount({ index: 2 }))).toContain("3");
  });

  it("사진이 없으면 대체 사진을 대신 그린다", () => {
    const tree = mount({
      spot: { ...spot, imageUrl: null, fallbackImageUrl: "https://kto/fallback.jpg" },
    });

    expect(tree.root.findByType(RemoteImage).props.uri).toBe("https://kto/fallback.jpg");
  });

  it("실제 사진이 있으면 대체 사진을 쓰지 않는다", () => {
    const tree = mount({
      spot: {
        ...spot,
        imageUrl: "https://kto/real.jpg",
        fallbackImageUrl: "https://kto/fallback.jpg",
      },
    });

    expect(tree.root.findByType(RemoteImage).props.uri).toBe("https://kto/real.jpg");
  });

  it("거리는 칩이 아니라 지역 줄에 붙는다", () => {
    expect(texts(mount())).toContain("서귀포시 · 2.4km");
  });

  it("좌표를 모르면 지역만 적는다", () => {
    const shown = texts(mount({ distanceKm: null }));

    expect(shown).toContain("서귀포시");
    expect(shown).not.toContain("km");
  });

  it("성질 태그는 칩으로 남는다", () => {
    expect(texts(mount())).toContain("한산");
  });

  it("거리 태그는 칩을 만들지 않는다", () => {
    const tree = mount({ spot: { ...spot, tag: "2.4km" }, tagBasis: "직선거리 기준" });

    expect(tree.root.findAllByProps({ testID: "travel-metric" })).toHaveLength(0);
  });

  it.each(["870m", "40m"])("미터 거리 태그도 칩이 되지 않는다: %s", (tag) => {
    const tree = mount({ spot: { ...spot, tag }, tagBasis: "직선거리 기준" });

    expect(tree.root.findAllByProps({ testID: "travel-metric" })).toHaveLength(0);
    expect(texts(tree)).toContain(`서귀포시 · ${tag}`);
  });

  it("서버가 잰 거리가 있으면 기기 위치로 잰 값을 쓰지 않는다", () => {
    const shown = texts(mount({ spot: { ...spot, tag: "420m" }, distanceKm: 450 }));

    expect(shown).toContain("서귀포시 · 420m");
    expect(shown).not.toContain("450km");
  });

  it("위치 권한이 없어도 서버가 잰 거리는 남는다", () => {
    const shown = texts(mount({ spot: { ...spot, tag: "420m" }, distanceKm: null }));

    expect(shown).toContain("서귀포시 · 420m");
  });

  it("서버가 거리를 주지 않으면 기기 위치로 잰 값을 쓴다", () => {
    const shown = texts(mount({ spot: { ...spot, tag: null }, distanceKm: 2.4 }));

    expect(shown).toContain("서귀포시 · 2.4km");
  });

  it("근거가 없는 태그는 칩으로만 남고 눌리지 않는다", () => {
    const onMetricPress = jest.fn();
    const tree = mount({ spot: { ...spot, tag: "실내" }, tagBasis: null, onMetricPress });

    expect(texts(tree)).toContain("실내");
    expect(tree.root.findAllByProps({ testID: "travel-metric" }).length).toBeGreaterThan(0);
    expect(byId(tree, "travel-metric")).toBeUndefined();
    expect(onMetricPress).not.toHaveBeenCalled();
  });

  it("칩을 누르면 근거 문구를 위로 올린다", () => {
    const onMetricPress = jest.fn();
    const tree = mount({ onMetricPress });

    act(() => byId(tree, "travel-metric")!.props.onPress());

    expect(onMetricPress).toHaveBeenCalledWith("혼잡도 8/3 예측 기준");
  });

  it("상세보기 버튼과 카드 본문이 같은 곳으로 간다", () => {
    const onDetail = jest.fn();
    const tree = mount({ onDetail });

    act(() => byId(tree, "travel-card-detail")!.props.onPress());
    act(() => byId(tree, `travel-card-126508`)!.props.onPress());

    expect(onDetail).toHaveBeenCalledTimes(2);
  });

  it("본문을 누르기 시작하면 상세를 미리 받는다", () => {
    const tree = mount();

    act(() => byId(tree, "travel-card-126508")!.props.onPressIn());

    expect(prefetchSpot).toHaveBeenCalledWith(spot);
  });

  it("초점이 맞은 카드만 번호에 강조색을 쓴다", () => {
    expect(badgeFill(false)).toBe(colors.ink);
    expect(badgeFill(true)).toBe(colors.accent);
  });

  it("하트는 본문 밖 형제라 저장 탭이 상세를 열지 않는다", () => {
    const tree = mount();

    expect(
      outermost(tree, "travel-card-126508").findAllByProps({ testID: "travel-card-save-126508" }),
    ).toHaveLength(0);
  });

  it("저장 결과를 그대로 알린다", async () => {
    toggle.mockResolvedValueOnce(false);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });

    await act(async () => byId(tree, "travel-card-save-126508")!.props.onPress());

    expect(onSaveToggle).toHaveBeenCalledWith(false);
  });

  it("저장에 실패하면 알리지 않는다", async () => {
    toggle.mockResolvedValueOnce(null);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });

    await act(async () => byId(tree, "travel-card-save-126508")!.props.onPress());

    expect(onSaveToggle).not.toHaveBeenCalled();
  });
});

describe("SpotCard 카카오 전용 카드", () => {
  const external: TravelSpot = {
    ...spot,
    contentId: "kakao:24350794",
    title: "사유",
    regionLabel: "광진구 군자동",
    source: "kakao",
    imageUrl: null,
    saveable: false,
    externalUrl: "http://place.map.kakao.com/24350794",
    distanceM: 240,
    tag: "블로그 4곳",
  };

  it("저장할 수 없는 곳에는 북마크를 세우지 않는다", () => {
    const tree = mount({ spot: external });

    expect(
      tree.root.findAllByProps({ testID: `travel-card-save-${external.contentId}` }),
    ).toHaveLength(0);
  });

  it("상세보기 대신 카카오맵으로 안내한다", () => {
    expect(texts(mount({ spot: external }))).toContain("카카오맵");
    expect(texts(mount({ spot: external }))).not.toContain("상세보기");
  });

  it("사진이 없어도 거리로 자리를 채운다", () => {
    expect(texts(mount({ spot: external, distanceKm: null }))).toContain("240m");
  });

  it("저장 가능한 곳은 예전 그대로 북마크와 상세보기를 세운다", () => {
    const tree = mount();

    expect(
      tree.root.findAllByProps({ testID: `travel-card-save-${spot.contentId}` }).length,
    ).toBeGreaterThan(0);
    expect(texts(tree)).toContain("상세보기");
  });
});
