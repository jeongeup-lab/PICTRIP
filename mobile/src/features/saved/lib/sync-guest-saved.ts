import { saveSpot } from "@/features/saved/api";
import { useGuestSavedStore } from "@/features/saved/stores/guest-saved-store";

export async function syncGuestSavedToServer(): Promise<void> {
  const { items, clear } = useGuestSavedStore.getState();
  if (items.length === 0) return;
  await Promise.allSettled(items.map((spot) => saveSpot(spot.contentId)));
  clear();
}
