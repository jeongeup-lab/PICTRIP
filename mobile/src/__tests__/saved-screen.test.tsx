import renderer, { act } from "react-test-renderer";
import SavedScreen from "@/app/saved";
import { useSavedList, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { SavedListRow } from "@/features/saved/components/SavedListRow";
import { useRecentSpots } from "@/features/spots/stores/recent-store";
import { unsaveMessage } from "@/features/saved/lib/undo-message";
import type { SpotCard } from "@/lib/api-types";

jest.mock("expo-router", () => ({ router: { push: jest.fn(), back: jest.fn() } }));
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
jest.mock("@/features/travel/hooks/use-nearby-coords", () => ({ useNearbyCoords: jest.fn() }));
jest.mock("@/features/saved/components/SavedListRow", () => ({
  SavedListRow: jest.fn(() => null),
}));

const useSavedListMock = useSavedList as jest.Mock;
const useSaveMutationMock = useSaveMutation as jest.Mock;
const useUnsaveMutationMock = useUnsaveMutation as jest.Mock;
const useNearbyCoordsMock = useNearbyCoords as jest.Mock;
const SavedListRowMock = SavedListRow as unknown as jest.Mock;

const save = jest.fn();
const unsave = jest.fn();

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

const SEOUL = { lat: 37.5665, lng: 126.978 };
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

const renderedOrder = () =>
  SavedListRowMock.mock.calls.map((call) => (call[0].spot as SpotCard).contentId);

beforeEach(() => {
  useSavedListMock.mockReturnValue({ data: LIST, isLoading: false });
  useSaveMutationMock.mockReturnValue({ mutate: save });
  useUnsaveMutationMock.mockReturnValue({ mutate: unsave });
  useNearbyCoordsMock.mockReturnValue({ coords: SEOUL, askable: false, ask: jest.fn() });
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
  it("keeps the server order until another sort is picked", async () => {
    const tree = await mount();
    expect(renderedOrder()).toEqual(["far", "near"]);

    SavedListRowMock.mockClear();
    await press(tree, "sort-near");
    expect(renderedOrder()).toEqual(["near", "far"]);
  });

  it("shows the distance next to each row once a fix is available", async () => {
    await mount();
    expect(SavedListRowMock.mock.calls[1][0].distance).toBe("1.3km");
  });

  it("unsaves on the swipe action and restores it from the undo toast", async () => {
    const tree = await mount();

    await press(tree, "swipe-far-action");
    expect(unsave).toHaveBeenCalledWith("far");

    const toast = tree.root.findAll(
      (n) => n.props.testID === "unsave-toast" && typeof n.props.message === "string",
    )[0];
    expect(toast.props.message).toBe(unsaveMessage("향일암"));

    await press(tree, "unsave-toast-action");
    expect(save).toHaveBeenCalledWith("far");
  });

  it("offers recently viewed spots when nothing is saved", async () => {
    useSavedListMock.mockReturnValue({ data: [], isLoading: false });
    useRecentSpots.setState({ spots: [spot("seen", { title: "바람의 언덕" })] });

    const tree = await mount();

    expect(tree.root.findAllByProps({ testID: "recent-seen" }).length).toBeGreaterThan(0);
    expect(tree.root.findAllByProps({ testID: "open-travel" }).length).toBeGreaterThan(0);
  });
});
