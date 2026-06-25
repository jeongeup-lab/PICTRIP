import { useState } from "react";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";

export interface UseSaveOptimistic {
  /** Heart state to render: local optimistic value, falling back to persisted. */
  saved: boolean;
  /** Toggle handler — auth-gates first, then flips optimistically. */
  toggle: () => Promise<void>;
}

/**
 * Reusable save/unsave heart logic for a spot.
 *
 * Ordering preserved verbatim from the spot screen: the auth gate runs BEFORE
 * any optimistic flip, so a guest who dismisses the nudge never sees a phantom
 * heart. On confirm, the local optimistic state flips, the matching mutation
 * fires, and `onError` rolls the optimistic value back. The mutations
 * themselves own cache invalidation (save) / optimistic list write + rollback
 * (unsave).
 */
export function useSaveOptimistic(contentId: string): UseSaveOptimistic {
  const requireAuth = useAuthGate();
  const persisted = useIsSaved(contentId);
  const [optimistic, setOptimistic] = useState<boolean | null>(null);
  const saved = optimistic ?? persisted;
  const saveMut = useSaveMutation();
  const unsaveMut = useUnsaveMutation();

  const toggle = async () => {
    if (!(await requireAuth("save"))) return;
    const next = !saved;
    setOptimistic(next);
    const rollback = () => setOptimistic(!next);
    if (next) saveMut.mutate(contentId, { onError: rollback });
    else unsaveMut.mutate(contentId, { onError: rollback });
  };

  return { saved, toggle };
}
