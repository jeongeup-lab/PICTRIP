import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
import { useGuestSavedStore } from "@/features/saved/stores/guest-saved-store";
import { containsId } from "@/features/saved/lib/optimistic";
import type { SpotCard } from "@/lib/api-types";

export interface UseDiscoverySave {
  saved: boolean;
  toggle: () => void;
}

export function useDiscoverySave(spot: SpotCard): UseDiscoverySave {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const persistedSaved = useIsSaved(spot.contentId);
  const saveMut = useSaveMutation();
  const unsaveMut = useUnsaveMutation();
  const guestItems = useGuestSavedStore((s) => s.items);
  const toggleGuest = useGuestSavedStore((s) => s.toggle);

  if (isAuthenticated) {
    return {
      saved: persistedSaved,
      toggle: () => {
        if (persistedSaved) unsaveMut.mutate(spot.contentId);
        else saveMut.mutate(spot.contentId);
      },
    };
  }

  return {
    saved: containsId(guestItems, spot.contentId),
    toggle: () => toggleGuest(spot),
  };
}
