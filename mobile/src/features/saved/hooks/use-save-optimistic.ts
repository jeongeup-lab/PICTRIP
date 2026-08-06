import { useState } from "react";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";

export interface UseSaveOptimistic {
  saved: boolean;
  toggle: () => Promise<boolean | null>;
}

export function useSaveOptimistic(contentId: string): UseSaveOptimistic {
  const requireAuth = useAuthGate();
  const persisted = useIsSaved(contentId);
  const [optimistic, setOptimistic] = useState<boolean | null>(null);
  const saved = optimistic ?? persisted;
  const saveMut = useSaveMutation();
  const unsaveMut = useUnsaveMutation();

  const toggle = async (): Promise<boolean | null> => {
    if (!(await requireAuth("save"))) return null;
    const next = !saved;
    setOptimistic(next);
    try {
      if (next) await saveMut.mutateAsync(contentId);
      else await unsaveMut.mutateAsync(contentId);
      return next;
    } catch {
      setOptimistic(!next);
      return null;
    }
  };

  return { saved, toggle };
}
