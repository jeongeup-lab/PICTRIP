import { saveSpot } from "@/features/saved/api";
import { useGuestSavedStore } from "@/features/saved/stores/guest-saved-store";
import { syncGuestSavedToServer } from "@/features/saved/lib/sync-guest-saved";
import type { SpotCard } from "@/lib/api-types";

jest.mock("@/features/saved/api", () => ({ saveSpot: jest.fn() }));

const spot = (id: string): SpotCard => ({
  contentId: id,
  title: id,
  firstImageUrl: null,
  category: null,
});

describe("syncGuestSavedToServer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useGuestSavedStore.setState({ items: [], hydrated: true });
  });

  it("does nothing when the guest list is empty", async () => {
    await syncGuestSavedToServer();
    expect(saveSpot).not.toHaveBeenCalled();
  });

  it("pushes every guest-saved spot to the server then clears the guest list", async () => {
    (saveSpot as jest.Mock).mockResolvedValue(undefined);
    useGuestSavedStore.setState({ items: [spot("a"), spot("b")] });
    await syncGuestSavedToServer();
    expect(saveSpot).toHaveBeenCalledWith("a");
    expect(saveSpot).toHaveBeenCalledWith("b");
    expect(useGuestSavedStore.getState().items).toEqual([]);
  });

  it("still clears the guest list when some saves fail", async () => {
    (saveSpot as jest.Mock).mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(
      undefined,
    );
    useGuestSavedStore.setState({ items: [spot("a"), spot("b")] });
    await syncGuestSavedToServer();
    expect(useGuestSavedStore.getState().items).toEqual([]);
  });
});
