import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { OPEN_MAP_LABEL, TurnMap } from "@/features/travel/components/TurnMap";
import { placed } from "@/features/travel/lib/spot-geo";
import type { TravelSpot } from "@/features/travel/api";

const spot = (over: Partial<TravelSpot> = {}): TravelSpot => ({
  contentId: "c1",
  title: "무릉계곡",
  regionLabel: "제주 제주시",
  imageUrl: null,
  tag: null,
  lat: 33.5,
  lng: 126.5,
  ...over,
});

const SCATTERED = placed([
  spot({ contentId: "a", regionLabel: "제주 제주시", lat: 33.5, lng: 126.5 }),
  spot({ contentId: "b", regionLabel: "제주 제주시", lat: 33.51, lng: 126.52 }),
  spot({ contentId: "c", regionLabel: "제주 서귀포시", lat: 33.25, lng: 126.56 }),
]);

const noop = () => undefined;

function mount(spots = SCATTERED, live = false) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<TurnMap spots={spots} live={live} onOpen={noop} />);
  });
  return tree!;
}

const texts = (tree: renderer.ReactTestRenderer): string[] =>
  tree.root.findAllByType(Text).map((n) => String(n.props.children));

describe("TurnMap summary bar", () => {
  it("labels the spread instead of narrating it in a sentence", () => {
    const bar = texts(mount());

    expect(bar).toContain("제주시 2곳 · 서귀포시 1곳 · 최대 29km");
    expect(bar.join("")).not.toContain("나뉘어요");
    expect(bar.join("")).not.toContain("떨어져요");
  });

  it("gives the summary room to wrap rather than truncating it", () => {
    const summary = mount().root.findAllByType(Text)[0];

    expect(summary.props.numberOfLines).toBe(2);
  });

  it("names the destination without borrowing the detail chevron", () => {
    const tree = mount();

    expect(OPEN_MAP_LABEL).toBe("지도 열기");
    expect(texts(tree)).toContain(OPEN_MAP_LABEL);
    expect(tree.root.findByProps({ testID: "travel-turn-map" }).props.accessibilityLabel).toBe(
      OPEN_MAP_LABEL,
    );
  });

  it("falls back to a bare count when there is nothing spatial to say", () => {
    expect(texts(mount(placed([spot()])))).toContain("지도에 1곳");
  });
});
