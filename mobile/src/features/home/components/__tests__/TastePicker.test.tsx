import renderer, { act } from "react-test-renderer";
import { router } from "expo-router";
import { TastePicker } from "@/features/home/components/TastePicker";
import { useTastePicks } from "@/features/home/queries";
import { useSavedList, useSaveMutation } from "@/features/saved/queries";
import { queryClient } from "@/lib/query-client";
import type { HomeSpotCard } from "@/features/home/api";

jest.mock("expo-router", () => ({ router: { back: jest.fn() } }));
jest.mock("@/features/home/queries", () => ({ useTastePicks: jest.fn() }));
jest.mock("@/features/saved/queries", () => ({
  useSaveMutation: jest.fn(),
  useSavedList: jest.fn(),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const mockPicks = useTastePicks as jest.Mock;
const mockSaveMutation = useSaveMutation as jest.Mock;
const mockSavedList = useSavedList as jest.Mock;
let mutateAsync: jest.Mock;

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
  mutateAsync = jest.fn().mockResolvedValue(undefined);
  mockSaveMutation.mockReturnValue({ mutateAsync });
  mockSavedList.mockReturnValue({ data: [] });
  mockPicks.mockReturnValue({ data: { items: picks(24) }, isLoading: false, isError: false });
});

afterEach(() => {
  jest.clearAllMocks();
});

async function mount() {
  let tree: renderer.ReactTestRenderer;
  await act(async () => {
    tree = renderer.create(<TastePicker />);
  });
  return tree!;
}

const json = (r: renderer.ReactTestRenderer) => JSON.stringify(r.toJSON());

const cards = (r: renderer.ReactTestRenderer) =>
  r.root
    .findAll((n) => typeof n.props.testID === "string" && /^taste-card-/.test(n.props.testID))
    .filter((n) => !!n.props.onPress);

const meter = (r: renderer.ReactTestRenderer) =>
  r.root.findByProps({ testID: "taste-meter" }).props.children as unknown;

const tap = async (r: renderer.ReactTestRenderer, testID: string) => {
  const target = r.root.findAll((n) => n.props.testID === testID && !!n.props.onPress)[0];
  await act(async () => {
    target.props.onPress();
  });
};

const picked = (r: renderer.ReactTestRenderer) =>
  cards(r)
    .filter((n) => n.props.accessibilityState?.selected === true)
    .map((n) => String(n.props.testID).replace("taste-card-", ""));

describe("TastePicker", () => {
  it("shows a page of candidates drawn from a larger pool", async () => {
    const r = await mount();
    expect(cards(r)).toHaveLength(12);
    expect(json(r)).toContain("취향 1");
    expect(json(r)).not.toContain("취향 13");
  });

  it("selects a card on tap and counts it toward the minimum", async () => {
    const r = await mount();
    await tap(r, "taste-card-p1");
    expect(picked(r)).toEqual(["p1"]);
    expect(JSON.stringify(meter(r))).toContain("2곳");
  });

  it("takes the selection back on a second tap", async () => {
    const r = await mount();
    await tap(r, "taste-card-p1");
    await tap(r, "taste-card-p1");
    expect(picked(r)).toEqual([]);
  });

  it("saves nothing until the minimum is reached", async () => {
    const r = await mount();
    await tap(r, "taste-card-p1");
    await tap(r, "taste-card-p2");
    await tap(r, "taste-done");
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("saves every picked card at once, then refreshes home and leaves", async () => {
    const invalidate = jest.spyOn(queryClient, "invalidateQueries");
    const r = await mount();
    await tap(r, "taste-card-p1");
    await tap(r, "taste-card-p3");
    await tap(r, "taste-card-p5");
    await tap(r, "taste-done");

    expect(mutateAsync.mock.calls.map((c) => c[0])).toEqual(["p1", "p3", "p5"]);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["home-recommendations"] });
    expect(router.back).toHaveBeenCalled();
    invalidate.mockRestore();
  });

  it("refreshes only the cards the user has not picked", async () => {
    const r = await mount();
    await tap(r, "taste-card-p2");
    await tap(r, "taste-refresh");

    const shown = cards(r).map((n) => String(n.props.testID).replace("taste-card-", ""));
    expect(shown).toContain("p2");
    expect(shown).toHaveLength(12);
    expect(shown.filter((id) => id !== "p2")).toEqual(
      expect.arrayContaining(["p13", "p14", "p15"]),
    );
    expect(picked(r)).toEqual(["p2"]);
  });

  it("drops spots the user already saved from the pool", async () => {
    mockSavedList.mockReturnValue({ data: [{ contentId: "p1" }] });
    const r = await mount();
    const shown = cards(r).map((n) => String(n.props.testID).replace("taste-card-", ""));
    expect(shown).not.toContain("p1");
    expect(shown).toHaveLength(12);
  });

  it("keeps the user on the screen when a save fails", async () => {
    mutateAsync.mockRejectedValueOnce(new Error("offline"));
    const r = await mount();
    await tap(r, "taste-card-p1");
    await tap(r, "taste-card-p2");
    await tap(r, "taste-card-p3");
    await tap(r, "taste-done");

    expect(json(r)).toContain("저장하지 못했어요");
    expect(router.back).not.toHaveBeenCalled();
    expect(picked(r)).toEqual(["p1", "p2", "p3"]);
  });

  it("offers a way back when there are no cards to show", async () => {
    mockPicks.mockReturnValue({ data: { items: [] }, isLoading: false, isError: false });
    const r = await mount();
    expect(json(r)).toContain("지금은 보여줄 장소가 없어요");
    expect(r.root.findAllByProps({ testID: "taste-done" })).toHaveLength(0);
  });

  it("hides the refresh control when the pool has nothing left to rotate in", async () => {
    mockPicks.mockReturnValue({ data: { items: picks(12) }, isLoading: false, isError: false });
    const r = await mount();
    expect(r.root.findAllByProps({ testID: "taste-refresh" })).toHaveLength(0);
  });

  it("refreshes the recommendations on the way out", async () => {
    const invalidate = jest.spyOn(queryClient, "invalidateQueries");
    const r = await mount();
    await tap(r, "taste-close");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["home-recommendations"] });
    expect(router.back).toHaveBeenCalled();
    invalidate.mockRestore();
  });
});
