import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { putAiTransferConsent } from "@/features/consent/api";
import { AI_TRANSFER_VERSION } from "@/features/consent/lib/ai-transfer";
import { useConsents } from "@/features/consent/queries";
import { getAiTransferConsent, setAiTransferConsent } from "@/lib/storage";

/**
 * 로그인 사용자는 서버가 증빙(시점·고지 버전)을 들고, 비로그인은 기기에만 남는다.
 * `/agent/chat` 이 OptionalUserId 라 비로그인도 질문할 수 있어서 두 경로가 다 필요하다.
 * 로그인하면 기기에 남은 동의를 서버로 올려 증빙을 맞춘다.
 */
export function useAiTransferConsent() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data: consents } = useConsents();
  const [localGranted, setLocalGranted] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    void getAiTransferConsent().then((stored) => {
      if (!active) return;
      setLocalGranted(stored);
      setLoaded(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const serverGranted = consents?.aiTransferConsent ?? false;
  const granted = isAuthenticated ? serverGranted || localGranted : localGranted;

  useEffect(() => {
    if (!isAuthenticated || !loaded) return;
    if (!localGranted || serverGranted) return;
    void putAiTransferConsent({ granted: true, version: AI_TRANSFER_VERSION }).catch(
      () => undefined,
    );
  }, [isAuthenticated, loaded, localGranted, serverGranted]);

  const decide = useCallback(
    async (next: boolean) => {
      setLocalGranted(next);
      await setAiTransferConsent(next);
      if (!isAuthenticated) return;
      await putAiTransferConsent({ granted: next, version: AI_TRANSFER_VERSION }).catch(
        () => undefined,
      );
    },
    [isAuthenticated],
  );

  return { granted, loaded, decide };
}
