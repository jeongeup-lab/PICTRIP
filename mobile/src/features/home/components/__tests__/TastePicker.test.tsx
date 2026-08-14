import renderer, { act } from "react-test-renderer";
import { router } from "expo-router";
import { TastePicker } from "@/features/home/components/TastePicker";
import { useTastePicks } from "@/features/home/queries";
import { useSavedList, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { queryClient } from "@/lib/query-client";
import type { HomeSpotCard } from "@/features/home/api";

jest.mock("expo-router", () => ({ router: { back: jest.fn() } }));
jest.mock("@/features/home/queries", () => ({ useTastePicks: jest.fn() }));
jest.mock("@/features/saved/queries", () => ({
  useSaveMutation: jest.fn(),
  useSavedList: jest.fn(),
  useUnsaveMutation: jest.fn(),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

const mockPicks = useTastePicks as jest.Mock;
const mockSaveMutation = useSaveMutation as jest.Mock;
const mockUnsaveMutation = useUnsaveMutation as jest.Mock;
const mockSavedList = useSavedList as jest.Mock;
let mutateAsync: jest.Mock;
let unsaveAsync: jest.Mock;

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
  jest.useFakeTimers();
  mutateAsync = jest.fn().mockResolvedValue(undefined);
  unsaveAsync = jest.fn().mockResolvedValue(undefined);
  mockSaveMutation.mockReturnValue({ mutateAsync });
  mockUnsaveMutation.mockReturnValue({ mutateAsync: unsaveAsync });
  mockSavedList.mockReturnValue({ data: [] });
  mockPicks.mockReturnValue({ data: { items: picks(3) }, isLoading: false, isError: false });
});

afterEach(() => {
  jest.clearAllMocks();
  jest.useRealTimers();
});

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
  await act(async () => {
    jest.runAllTimers();
  });
  await act(async () => {});
};

describe("TastePicker", () => {
  it("starts on the first card with an empty progress counter", async () => {
    const r = await mount();
    expect(json(r)).toContain("취향 1");
    expect(progress(r)).toBe("0/3 검토");
    expect(json(r)).toContain("오른쪽으로 밀면 저장, 왼쪽으로 밀면 넘겨요");
  });

  it("saving a card persists it and advances to the next", async () => {
    const r = await mount();
    await press(r, "taste-keep");
    expect(mutateAsync).toHaveBeenCalledWith("p1");
    expect(json(r)).toContain("취향 2");
    expect(progress(r)).toBe("1/3 검토");
  });

  it("holds the card and the counter when the save fails", async () => {
    mutateAsync.mockRejectedValueOnce(new Error("offline"));
    const r = await mount();
    await press(r, "taste-keep");
    expect(json(r)).toContain("취향 1");
    expect(progress(r)).toBe("0/3 검토");
    expect(json(r)).toContain("저장하지 못했어요");
  });

  it("skipping advances the reviewed progress without saving", async () => {
    const r = await mount();
    await press(r, "taste-skip");
    expect(mutateAsync).not.toHaveBeenCalled();
    expect(json(r)).toContain("취향 2");
    expect(progress(r)).toBe("1/3 검토");
  });

  it("undoes a skip locally and restores the prior card", async () => {
    const r = await mount();
    await press(r, "taste-skip");
    expect(r.root.findByProps({ testID: "taste-undo" }).props.disabled).toBe(false);
    await press(r, "taste-undo");
    expect(json(r)).toContain("취향 1");
    expect(progress(r)).toBe("0/3 검토");
    expect(unsaveAsync).not.toHaveBeenCalled();
  });

  it("unsaves a newly saved card before restoring it", async () => {
    const r = await mount();
    await press(r, "taste-keep");
    await press(r, "taste-undo");
    expect(unsaveAsync).toHaveBeenCalledWith("p1");
    expect(json(r)).toContain("취향 1");
    expect(progress(r)).toBe("0/3 검토");
  });

  it("does not resave or unsave a card that was already saved before the session", async () => {
    mockSavedList.mockReturnValue({
      data: [{ contentId: "p1" }, { contentId: "p2" }, { contentId: "p3" }],
    });
    const r = await mount();
    await press(r, "taste-keep");
    expect(mutateAsync).not.toHaveBeenCalled();
    await press(r, "taste-undo");
    expect(unsaveAsync).not.toHaveBeenCalled();
  });

  it("keeps the current card in place and offers a retry when undoing a save fails", async () => {
    unsaveAsync.mockRejectedValueOnce(new Error("offline"));
    const r = await mount();
    await press(r, "taste-keep");
    await press(r, "taste-undo");
    expect(json(r)).toContain("취향 2");
    expect(json(r)).toContain("되돌리지 못했어요");
    expect(r.root.findByProps({ testID: "taste-undo" }).props.disabled).toBe(false);
  });

  it("keeps undo available from completion", async () => {
    const r = await mount();
    await press(r, "taste-skip");
    await press(r, "taste-skip");
    await press(r, "taste-skip");
    expect(r.root.findByProps({ testID: "taste-undo" }).props.disabled).toBe(false);
    await press(r, "taste-undo");
    expect(json(r)).toContain("취향 3");
    expect(progress(r)).toBe("2/3 검토");
  });

  it("suppresses duplicate saves while a decision is pending", async () => {
    let resolveSave: (() => void) | undefined;
    mutateAsync.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveSave = resolve;
        }),
    );
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "taste-keep" }).props.onPress();
      r.root.findByProps({ testID: "taste-keep" }).props.onPress();
    });
    expect(mutateAsync).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveSave?.();
      jest.runAllTimers();
    });
  });

  it("drops cards the user already saved from the deck", async () => {
    mockSavedList.mockReturnValue({ data: [{ contentId: "p1" }] });
    const r = await mount();
    expect(json(r)).toContain("취향 2");
    expect(json(r)).not.toContain("취향 1");
  });

  it("keeps the full deck when every pick is already saved", async () => {
    mockSavedList.mockReturnValue({
      data: [{ contentId: "p1" }, { contentId: "p2" }, { contentId: "p3" }],
    });
    const r = await mount();
    expect(json(r)).toContain("취향 1");
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

  it("counts pre-existing saves toward the completion threshold", async () => {
    mockSavedList.mockReturnValue({
      data: [{ contentId: "x1" }, { contentId: "x2" }],
    });
    const r = await mount();
    await press(r, "taste-keep");
    await press(r, "taste-skip");
    await press(r, "taste-skip");
    expect(json(r)).toContain("취향을 다 읽었어요");
  });

  it("treats a fully pre-saved deck as complete without new saves", async () => {
    mockSavedList.mockReturnValue({
      data: [{ contentId: "p1" }, { contentId: "p2" }, { contentId: "p3" }],
    });
    const r = await mount();
    await press(r, "taste-skip");
    await press(r, "taste-skip");
    await press(r, "taste-skip");
    expect(json(r)).toContain("취향을 다 읽었어요");
  });

  it("refreshes the recommendations on the way out", async () => {
    const invalidate = jest.spyOn(queryClient, "invalidateQueries");
    const r = await mount();
    await act(async () => {
      r.root.findByProps({ testID: "taste-close" }).props.onPress();
    });
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
