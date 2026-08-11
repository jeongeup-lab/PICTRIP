import renderer, { act } from "react-test-renderer";
import { router } from "expo-router";
import { TastePicker } from "@/features/home/components/TastePicker";
import { useTastePicks } from "@/features/home/queries";
import { useSaveMutation } from "@/features/saved/queries";
import { queryClient } from "@/lib/query-client";
import type { HomeSpotCard } from "@/features/home/api";

jest.mock("expo-router", () => ({ router: { back: jest.fn() } }));
jest.mock("@/features/home/queries", () => ({ useTastePicks: jest.fn() }));
jest.mock("@/features/saved/queries", () => ({ useSaveMutation: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const mockPicks = useTastePicks as jest.Mock;
const mockSaveMutation = useSaveMutation as jest.Mock;
let mutate: jest.Mock;

function picks(n: number): HomeSpotCard[] {
  return Array.from({ length: n }, (_, i) => ({
    contentId: `p${i + 1}`,
    title: `취향 ${i + 1}`,
    regionLabel: "부산광역시 사하구",
    imageUrl: null,
    rank: null,
    dist: null,
    category: "자연관광지",
    tag: null,
    anchorTitle: null,
  }));
}

beforeEach(() => {
  mutate = jest.fn();
  mockSaveMutation.mockReturnValue({ mutate });
  mockPicks.mockReturnValue({ data: { items: picks(3) }, isLoading: false, isError: false });
});

afterEach(() => jest.clearAllMocks());

async function mount() {
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(<TastePicker />);
  });
  return tree!;
}

const json = (r: renderer.ReactTestRenderer) => JSON.stringify(r.toJSON());
const progress = (r: renderer.ReactTestRenderer) =>
  r.root.findByProps({ testID: "taste-progress" }).props.children as string;
const press = async (r: renderer.ReactTestRenderer, testID: string) => {
  await act(async () => {
    r.root.findByProps({ testID }).props.onPress();
  });
};

describe("TastePicker", () => {
  it("starts on the first card with an empty progress counter", async () => {
    const r = await mount();
    expect(json(r)).toContain("취향 1");
    expect(progress(r)).toBe("0/3 저장");
  });

  it("saving a card persists it and advances to the next", async () => {
    const r = await mount();
    await press(r, "taste-keep");
    expect(mutate).toHaveBeenCalledWith("p1");
    expect(json(r)).toContain("취향 2");
    expect(progress(r)).toBe("1/3 저장");
  });

  it("skipping advances without saving", async () => {
    const r = await mount();
    await press(r, "taste-skip");
    expect(mutate).not.toHaveBeenCalled();
    expect(json(r)).toContain("취향 2");
  });

  it("nudges the user when the deck runs out under the minimum", async () => {
    const r = await mount();
    await press(r, "taste-skip");
    await press(r, "taste-skip");
    await press(r, "taste-skip");
    expect(json(r)).toContain("3곳 이상 저장하면 추천이 시작돼요");
  });

  it("confirms the taste is read once enough cards are saved", async () => {
    const r = await mount();
    await press(r, "taste-keep");
    await press(r, "taste-keep");
    await press(r, "taste-keep");
    expect(json(r)).toContain("취향을 다 읽었어요");
  });

  it("refreshes the recommendations on the way out", async () => {
    const invalidate = jest.spyOn(queryClient, "invalidateQueries");
    const r = await mount();
    await press(r, "taste-close");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["home-recommendations"] });
    expect(router.back).toHaveBeenCalled();
    invalidate.mockRestore();
  });

  it("offers a way back when there are no cards to show", async () => {
    mockPicks.mockReturnValue({ data: { items: [] }, isLoading: false, isError: false });
    const r = await mount();
    expect(json(r)).toContain("지금은 보여줄 카드가 없어요");
    expect(r.root.findAllByProps({ testID: "taste-keep" })).toHaveLength(0);
  });
});
