import { useState } from "react";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";

export interface UseSaveOptimistic {
  saved: boolean;
  toggle: () => Promise<void>;
}

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
