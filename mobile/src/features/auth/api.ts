import { bareClient } from "@/lib/bare-client";
import { api } from "@/lib/api-client";
import type { TokenPair } from "@/lib/api-types";

export async function oauthLogin(
  provider: string,
  idToken: string,
  nonce?: string,
  authorizationCode?: string,
): Promise<TokenPair> {
  return (await bareClient.post(`/auth/oauth/${provider}`, {
    idToken,
    nonce,
    authorizationCode,
  })) as unknown as TokenPair;
}

export async function logoutRequest(refreshToken: string | null): Promise<void> {
  await bareClient.post("/auth/logout", { refreshToken });
}

export async function deleteAccountRequest(
  refreshToken: string | null,
  reason?: string,
): Promise<void> {
  await api.delete("/users/me", { data: { refreshToken, reason: reason ?? null } });
}
