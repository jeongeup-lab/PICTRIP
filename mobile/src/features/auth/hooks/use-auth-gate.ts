import { useCallback } from "react";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useAuthPromptStore, type AuthReason } from "@/features/auth/stores/auth-prompt-store";

export function useAuthGate(): (reason: AuthReason) => Promise<boolean> {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const prompt = useAuthPromptStore((s) => s.prompt);
  return useCallback(
    (reason: AuthReason) => (isAuthenticated ? Promise.resolve(true) : prompt(reason)),
    [isAuthenticated, prompt],
  );
}
