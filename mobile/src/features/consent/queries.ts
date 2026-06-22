import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { getConsents, putConsents } from "@/features/consent/api";
import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

export const consentKeys = { state: ["consents"] as const };

export function useConsents() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: consentKeys.state,
    queryFn: getConsents,
    enabled: isAuthenticated,
  });
}

export function useUpdateConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ConsentPutBody) => putConsents(body),
    onSuccess: (next: ConsentState) => qc.setQueryData(consentKeys.state, next),
  });
}
