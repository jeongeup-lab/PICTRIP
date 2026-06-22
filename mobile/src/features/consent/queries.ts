import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { getConsents, putConsents } from "@/features/consent/api";
import { applyConsentPut } from "@/features/consent/lib/apply-consent-put";
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
    onMutate: async (body: ConsentPutBody) => {
      await qc.cancelQueries({ queryKey: consentKeys.state });
      const prev = qc.getQueryData<ConsentState>(consentKeys.state);
      if (prev) qc.setQueryData(consentKeys.state, applyConsentPut(prev, body));
      return { prev };
    },
    onError: (_e, _body, ctx) => {
      if (ctx?.prev) qc.setQueryData(consentKeys.state, ctx.prev);
    },
    onSuccess: (next: ConsentState) => qc.setQueryData(consentKeys.state, next),
  });
}
