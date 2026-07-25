import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import TravelResultsScreen from "@/app/travel/results";
import { RemoteImage } from "@/components/RemoteImage";
import type { TravelSpot } from "@/features/travel/api";
import { useResults } from "@/features/travel/stores/results-store";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const spot = (over: Partial<TravelSpot> = {}): TravelSpot => ({
  contentId: "126508",
  title: "무릉계곡",
  regionLabel: "강원도 동해시",
  imageUrl: "https://img.pictrip.org/t1/1620/abc/tong.visitkorea.or.kr/a.jpg",
  tag: "하위 8%",
  lat: null,
  lng: null,
  ...over,
});

let mounted: renderer.ReactTestRenderer | null = null;

afterEach(async () => {
  const tree = mounted;
  mounted = null;
  if (tree) await act(async () => tree.unmount());
});

async function mount() {
  await act(async () => {
    mounted = renderer.create(<TravelResultsScreen />);
  });
  return mounted!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string[] =>
  tree.root.findAllByType(Text).map((n) => flatten(n.props.children));

describe("TravelResultsScreen", () => {
  it("renders the handed-over list with its count subtitle", async () => {
    useResults.getState().open("숨은 관광지", [spot(), spot({ contentId: "2", title: "선유담" })]);
    const tree = await mount();
    expect(texts(tree)).toEqual(
      expect.arrayContaining(["숨은 관광지", "2곳", "무릉계곡", "선유담"]),
    );
  });

  it("passes the backend image url into the card untouched", async () => {
    useResults.getState().open("숨은 관광지", [spot()]);
    const tree = await mount();
    const image = tree.root.findByType(RemoteImage);
    expect(image.props.uri).toBe("https://img.pictrip.org/t1/1620/abc/tong.visitkorea.or.kr/a.jpg");
    expect(image.props.commonsWidth).toBeUndefined();
    expect(image.props.midSize).toBeUndefined();
  });

  it("survives an empty handoff", async () => {
    useResults.getState().open("내 근처", []);
    const tree = await mount();
    expect(texts(tree)).toEqual(expect.arrayContaining(["0곳"]));
  });
});
