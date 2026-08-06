import renderer, { act } from "react-test-renderer";
import { StyleSheet } from "react-native";
import { TravelMapView } from "@/features/travel/components/TravelMapView";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { placed } from "@/features/travel/lib/spot-geo";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 59, bottom: 34, left: 0, right: 0 }),
}));

const { router } = jest.requireMock("expo-router") as { router: { push: jest.Mock } };

const spots = placed([
  {
    contentId: "126508",
    title: "무릉계곡",
    regionLabel: "제주 제주시",
    imageUrl: null,
    tag: null,
    lat: 33.5,
    lng: 126.5,
  },
  {
    contentId: "126509",
    title: "천지연",
    regionLabel: "제주 서귀포시",
    imageUrl: null,
    tag: null,
    lat: 33.25,
    lng: 126.56,
  },
]);

function mount(selectedId: string | null = "126508", onSelect = jest.fn(), onClose = jest.fn()) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(
      <TravelMapView
        spots={spots}
        question="제주에서 한적한 곳"
        selectedId={selectedId}
        onSelect={onSelect}
        onClose={onClose}
      />,
    );
  });
  return tree!;
}

beforeEach(() => jest.clearAllMocks());

describe("TravelMapView", () => {
  it("holds the header clear of the status bar and notch", () => {
    const tree = mount();
    const top = tree.root.findAllByProps({ pointerEvents: "box-none" })[0];

    expect(StyleSheet.flatten(top.props.style).paddingTop).toBeGreaterThanOrEqual(59);
  });

  it("pins the results in accent red", () => {
    const map = mount().root.findByType(KakaoWebMap);

    expect(map.props.accentPins).toBe(true);
    expect(map.props.pins.map((p: { contentId: string }) => p.contentId)).toEqual([
      "126508",
      "126509",
    ]);
    expect(map.props.selectedId).toBe("126508");
  });

  it("centers on the selected spot so the red pin is the one in view", () => {
    const map = mount("126509").root.findByType(KakaoWebMap);

    expect(map.props.center).toEqual({ lat: 33.25, lng: 126.56 });
  });

  it("selects from a card without leaving the map", () => {
    const onSelect = jest.fn();
    const tree = mount("126508", onSelect);

    act(() => tree.root.findByProps({ testID: "travel-map-card-126509" }).props.onPress());

    expect(onSelect).toHaveBeenCalledWith("126509");
    expect(router.push).not.toHaveBeenCalled();
  });

  it("keeps itself on the stack when the detail opens, so back returns to the map", () => {
    const onClose = jest.fn();
    const tree = mount("126508", jest.fn(), onClose);

    act(() => tree.root.findByProps({ testID: "travel-map-detail-126508" }).props.onPress());

    expect(router.push).toHaveBeenCalledWith("/spots/126508");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes from its own button", () => {
    const onClose = jest.fn();
    const tree = mount("126508", jest.fn(), onClose);

    act(() => tree.root.findByProps({ testID: "travel-map-close" }).props.onPress());

    expect(onClose).toHaveBeenCalled();
  });
});
