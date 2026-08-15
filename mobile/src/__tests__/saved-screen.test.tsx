import renderer, { act } from "react-test-renderer";
import SavedScreen, { RESAVE_FAILED, UNSAVE_FAILED } from "@/app/saved";
import { useSavedList, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { SavedCard } from "@/features/saved/components/SavedCard";
import { useRecentSpots } from "@/features/spots/stores/recent-store";
import { unsaveMessage } from "@/features/saved/lib/undo-message";
import type { SpotCard } from "@/lib/api-types";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), navigate: jest.fn(), back: jest.fn() },
}));

const routerPush = jest.requireMock<{ router: { push: jest.Mock } }>("expo-router").router.push;
const routerNavigate = jest.requireMock<{ router: { navigate: jest.Mock } }>("expo-router").router
  .navigate;
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/features/saved/queries", () => ({
  useSavedList: jest.fn(),
  useSaveMutation: jest.fn(),
  useUnsaveMutation: jest.fn(),
  useIsSaved: jest.fn(() => false),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));
jest.mock("@/features/saved/components/SavedCard", () => ({
  SavedCard: jest.fn(() => null),
}));

const useSavedListMock = useSavedList as jest.Mock;
const useSaveMutationMock = useSaveMutation as jest.Mock;
const useUnsaveMutationMock = useUnsaveMutation as jest.Mock;
const SavedCardMock = SavedCard as unknown as jest.Mock;

const save = jest.fn();
const unsave = jest.fn();
const unsaveAsync = jest.fn();

const spot = (contentId: string, over: Partial<SpotCard> = {}): SpotCard => ({
  contentId,
  title: `spot-${contentId}`,
  firstImageUrl: null,
  addr1: null,
  mapx: null,
  mapy: null,
  category: null,
  ...over,
});

const LIST = [
  spot("far", { title: "향일암", addr1: "전남 여수시", mapx: 127.7, mapy: 34.7 }),
  spot("near", { title: "덕수궁", addr1: "서울 중구", mapx: 126.99, mapy: 37.56 }),
];

let mounted: renderer.ReactTestRenderer | null = null;

async function mount() {
  await act(async () => {
    mounted = renderer.create(<SavedScreen />);
  });
  return mounted!;
}

const press = async (tree: renderer.ReactTestRenderer, testID: string) => {
  const target = tree.root.findAll((n) => n.props.testID === testID && !!n.props.onPress)[0];
  await act(async () => {
    target.props.onPress();
  });
};

const unsaveTile = async (contentId: string) => {
  const calls = SavedCardMock.mock.calls.filter(
    (call) => (call[0].spot as SpotCard).contentId === contentId,
  );
  const latest = calls[calls.length - 1]![0] as { onUnsave: () => void };
  await act(async () => {
    latest.onUnsave();
  });
};

const renderedOrder = () =>
  SavedCardMock.mock.calls.map((call) => (call[0].spot as SpotCard).contentId);

beforeEach(() => {
  useSavedListMock.mockReturnValue({ data: LIST, isLoading: false });
  useSaveMutationMock.mockReturnValue({ mutate: save });
  unsaveAsync.mockResolvedValue(undefined);
  useUnsaveMutationMock.mockReturnValue({ mutate: unsave, mutateAsync: unsaveAsync });
  useRecentSpots.setState({ spots: [] });
});

afterEach(async () => {
  await act(async () => {
    mounted?.unmount();
  });
  mounted = null;
  jest.clearAllMocks();
});

describe("SavedScreen", () => {
  it("lays every scrap out as one album in server order", async () => {
    const tree = await mount();

    expect(renderedOrder()).toEqual(["far", "near"]);
    expect(tree.root.findAll((n) => String(n.props.testID ?? "").startsWith("sort-"))).toHaveLength(
      0,
    );
    expect(tree.root.findAllByProps({ testID: "toggle-view" })).toHaveLength(0);
  });

  it("unsaves from the tile heart and restores it from the undo toast", async () => {
    const tree = await mount();

    await unsaveTile("far");
    expect(unsaveAsync).toHaveBeenCalledWith("far");

    const toast = tree.root.findAll(
      (n) => n.props.testID === "unsave-toast" && typeof n.props.message === "string",
    )[0];
    expect(toast.props.message).toBe(unsaveMessage("향일암"));

    await press(tree, "unsave-toast-action");
    expect(save).toHaveBeenCalledWith("far", expect.any(Object));
  });

  it("holds the re-save until the unsave request has settled", async () => {
    let releaseUnsave: () => void = () => undefined;
    unsaveAsync.mockReturnValue(
      new Promise<void>((resolve) => {
        releaseUnsave = () => resolve();
      }),
    );

    const tree = await mount();
    await unsaveTile("far");
    await press(tree, "unsave-toast-action");

    expect(save).not.toHaveBeenCalled();

    await act(async () => {
      releaseUnsave();
    });

    expect(save).toHaveBeenCalledWith("far", expect.any(Object));
  });

  it("reports the failure instead of offering to undo a delete that never happened", async () => {
    unsaveAsync.mockRejectedValue(new Error("network"));

    const tree = await mount();
    await unsaveTile("far");
    await act(async () => undefined);

    const toast = tree.root.findAll(
      (n) => n.props.testID === "unsave-toast" && typeof n.props.message === "string",
    )[0];
    expect(toast.props.message).toBe(UNSAVE_FAILED);
    expect(toast.props.action).toBeNull();
    expect(save).not.toHaveBeenCalled();
  });

  it("says so when the re-save itself fails", async () => {
    save.mockImplementationOnce((_id: string, opts?: { onError?: () => void }) =>
      opts?.onError?.(),
    );

    const tree = await mount();
    await unsaveTile("far");
    await press(tree, "unsave-toast-action");
    await act(async () => undefined);

    const toast = tree.root.findAll(
      (n) => n.props.testID === "unsave-toast" && typeof n.props.message === "string",
    )[0];
    expect(toast.props.message).toBe(RESAVE_FAILED);
  });

  it("still reports a failure that lands after the undo toast expired", async () => {
    let failLate: () => void = () => undefined;
    unsaveAsync.mockReturnValueOnce(
      new Promise<void>((_resolve, reject) => {
        failLate = () => reject(new Error("timeout"));
      }),
    );

    const tree = await mount();
    await unsaveTile("far");

    const toast = tree.root.findAll((n) => n.props.testID === "unsave-toast")[0];
    await act(async () => {
      toast.props.onHide();
    });

    await act(async () => {
      failLate();
    });

    const after = tree.root.findAll(
      (n) => n.props.testID === "unsave-toast" && typeof n.props.message === "string",
    )[0];
    expect(after.props.message).toBe(UNSAVE_FAILED);
  });

  it("keeps the newest undo when an older unsave fails late", async () => {
    let failFirst: () => void = () => undefined;
    unsaveAsync
      .mockReturnValueOnce(
        new Promise<void>((_resolve, reject) => {
          failFirst = () => reject(new Error("network"));
        }),
      )
      .mockResolvedValueOnce(undefined);

    const tree = await mount();
    await unsaveTile("far");
    await unsaveTile("near");

    await act(async () => {
      failFirst();
    });

    const toast = tree.root.findAll(
      (n) => n.props.testID === "unsave-toast" && typeof n.props.message === "string",
    )[0];
    expect(toast.props.message).toBe(unsaveMessage("덕수궁"));
    expect(toast.props.action).not.toBeNull();
  });

  it("keeps the newest undo when an older re-save fails late", async () => {
    let failResave: () => void = () => undefined;
    save.mockImplementationOnce((_id: string, opts?: { onError?: () => void }) => {
      failResave = () => opts?.onError?.();
    });

    const tree = await mount();
    await unsaveTile("far");
    await press(tree, "unsave-toast-action");
    await act(async () => undefined);
    await unsaveTile("near");

    await act(async () => {
      failResave();
    });

    const toast = tree.root.findAll(
      (n) => n.props.testID === "unsave-toast" && typeof n.props.message === "string",
    )[0];
    expect(toast.props.message).toBe(unsaveMessage("덕수궁"));
    expect(toast.props.action).not.toBeNull();
  });

  it("saves from the recent row without opening the spot", async () => {
    useSavedListMock.mockReturnValue({ data: [], isLoading: false });
    useRecentSpots.setState({ spots: [spot("seen", { title: "바람의 언덕" })] });

    const tree = await mount();
    await press(tree, "recent-seen-heart");

    expect(routerPush).not.toHaveBeenCalledWith("/spots/seen");
  });

  it("offers recently viewed spots when nothing is saved", async () => {
    useSavedListMock.mockReturnValue({ data: [], isLoading: false });
    useRecentSpots.setState({ spots: [spot("seen", { title: "바람의 언덕" })] });

    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "recent-seen" }).length).toBeGreaterThan(0);
    expect(tree.root.findAllByProps({ testID: "open-explore" }).length).toBeGreaterThan(0);
  });

  it("opens Explore from the empty scrap CTA", async () => {
    useSavedListMock.mockReturnValue({ data: [], isLoading: false });
    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "open-explore" }).length).toBeGreaterThan(0);
    await press(tree, "open-explore");
    expect(routerNavigate).toHaveBeenCalledWith("/(tabs)/explore");
  });
});
