import { useCallback, useEffect, useRef } from "react";
import type { TravelSpot } from "@/features/travel/api";

export const DOUBLE_TAP_MS = 260;

interface Pending {
  contentId: string;
  timer: ReturnType<typeof setTimeout>;
}

export function useCardTap(
  onSingle: (spot: TravelSpot) => void,
  onDouble: (spot: TravelSpot) => void,
) {
  const pending = useRef<Pending | null>(null);

  const cancel = () => {
    if (pending.current) clearTimeout(pending.current.timer);
    pending.current = null;
  };

  useEffect(() => cancel, []);

  return useCallback(
    (spot: TravelSpot) => {
      const waiting = pending.current;
      cancel();
      if (waiting?.contentId === spot.contentId) {
        onDouble(spot);
        return;
      }
      pending.current = {
        contentId: spot.contentId,
        timer: setTimeout(() => {
          pending.current = null;
          onSingle(spot);
        }, DOUBLE_TAP_MS),
      };
    },
    [onSingle, onDouble],
  );
}
