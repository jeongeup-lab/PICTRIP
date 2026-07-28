import renderer, { act } from "react-test-renderer";
import { PinBoard } from "@/features/travel/components/PinBoard";
import type { TravelSpot } from "@/features/travel/api";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const spot = (contentId: string): TravelSpot => ({
  contentId,
  title: `spot-${contentId}`,
  regionLabel: "강원 삼척",
  imageUrl: null,
  tag: null,
  lat: null,
  lng: null,
});

const noop = () => {};

function mount(over: Partial<Parameters<typeof PinBoard>[0]> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(
      <PinBoard
        filter="all"
        spots={[spot("1"), spot("2"), spot("3")]}
        notice={null}
        onFilter={noop}
        onPhotoStart={noop}
        onSeeAll={noop}
        {...over}
      />,
    );
  });
  return tree!;
}

function pressable(tree: renderer.ReactTestRenderer, testID: string) {
  return tree.root
    .findAllByProps({ testID })
    .find((node) => typeof node.props.onPress === "function");
}

describe("PinBoard", () => {
  it("keeps the photo-start pin as the first cell alongside every spot pin", () => {
    const tree = mount();
    expect(pressable(tree, "travel-photo-start")).toBeDefined();
    expect(pressable(tree, "travel-spot-1")).toBeDefined();
    expect(pressable(tree, "travel-spot-2")).toBeDefined();
    expect(pressable(tree, "travel-spot-3")).toBeDefined();
  });

  it("marks only the active filter chip as selected and reports taps", () => {
    const onFilter = jest.fn();
    const tree = mount({ filter: "hot", onFilter });
    const hot = pressable(tree, "board-filter-hot")!;
    const hidden = pressable(tree, "board-filter-hidden")!;
    expect(hot.props.accessibilityState).toEqual({ selected: true });
    expect(hidden.props.accessibilityState).toEqual({ selected: false });

    act(() => hidden.props.onPress());
    expect(onFilter).toHaveBeenCalledWith("hidden");
  });

  it("shows the see-all link with a count only when the board has pins", () => {
    const withPins = mount();
    expect(pressable(withPins, "board-all")).toBeDefined();
    expect(JSON.stringify(withPins.toJSON())).toContain('["3","곳 보기"]');

    const empty = mount({ spots: [] });
    expect(pressable(empty, "board-all")).toBeUndefined();
  });

  it("renders the location notice above the board when provided", () => {
    const tree = mount({ filter: "around", spots: [], notice: "위치를 켜면 근처를 찾아드려요" });
    expect(JSON.stringify(tree.toJSON())).toContain("위치를 켜면 근처를 찾아드려요");
    expect(pressable(tree, "travel-photo-start")).toBeDefined();
  });
});
