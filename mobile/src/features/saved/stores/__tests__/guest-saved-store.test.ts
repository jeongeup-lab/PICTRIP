import { File } from "expo-file-system";
import { useGuestSavedStore } from "@/features/saved/stores/guest-saved-store";
import type { SpotCard } from "@/lib/api-types";

const spot = (id: string): SpotCard => ({
  contentId: id,
  title: id,
  firstImageUrl: null,
  category: null,
});

describe("guest-saved-store", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (File as unknown as jest.Mock).mockImplementation(() => ({
      exists: false,
      create: jest.fn(),
      write: jest.fn(),
    }));
    useGuestSavedStore.setState({ items: [], hydrated: false });
  });

  it("toggle adds a spot that is not yet saved", () => {
    useGuestSavedStore.getState().toggle(spot("a"));
    expect(useGuestSavedStore.getState().items.map((s) => s.contentId)).toEqual(["a"]);
  });

  it("toggle removes a spot that is already saved", () => {
    useGuestSavedStore.setState({ items: [spot("a"), spot("b")] });
    useGuestSavedStore.getState().toggle(spot("a"));
    expect(useGuestSavedStore.getState().items.map((s) => s.contentId)).toEqual(["b"]);
  });

  it("remove drops the matching spot", () => {
    useGuestSavedStore.setState({ items: [spot("a"), spot("b")] });
    useGuestSavedStore.getState().remove("a");
    expect(useGuestSavedStore.getState().items.map((s) => s.contentId)).toEqual(["b"]);
  });

  it("clear empties the list", () => {
    useGuestSavedStore.setState({ items: [spot("a")] });
    useGuestSavedStore.getState().clear();
    expect(useGuestSavedStore.getState().items).toEqual([]);
  });

  it("hydrate loads persisted items from the guest-saved file", async () => {
    const spots = [spot("a")];
    (File as unknown as jest.Mock).mockImplementation(() => ({
      exists: true,
      text: jest.fn().mockResolvedValue(JSON.stringify(spots)),
    }));
    await useGuestSavedStore.getState().hydrate();
    expect(useGuestSavedStore.getState().items).toEqual(spots);
    expect(useGuestSavedStore.getState().hydrated).toBe(true);
  });
});
