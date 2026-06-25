import { bareClient } from "@/lib/bare-client";
import { api } from "@/lib/api-client";
import type { TokenPair } from "@/lib/api-types";

/** Exchange a provider OIDC id_token for our token pair. Unauthed (bareClient). */
export async function oauthLogin(
  provider: string,
  idToken: string,
  nonce?: string,
): Promise<TokenPair> {
  return (await bareClient.post(`/auth/oauth/${provider}`, {
    idToken,
    nonce,
  })) as unknown as TokenPair;
}

/** Email/password login → our token pair. Unauthed (bareClient). */
export async function emailLogin(email: string, password: string): Promise<TokenPair> {
  return (await bareClient.post("/auth/email/login", {
    email,
    password,
  })) as unknown as TokenPair;
}

/** Email/password signup → our token pair. Unauthed (bareClient). */
export async function emailSignup(
  email: string,
  password: string,
  name?: string,
): Promise<TokenPair> {
  return (await bareClient.post("/auth/email/signup", {
    email,
    password,
    name,
  })) as unknown as TokenPair;
}

/** Denylist the refresh token server-side. Idempotent; unauthed. */
export async function logoutRequest(refreshToken: string | null): Promise<void> {
  await bareClient.post("/auth/logout", { refreshToken });
}

/** 회원 탈퇴 — authed DELETE; backend anonymizes + unlinks OAuth (204). */
export async function deleteAccountRequest(): Promise<void> {
  await api.delete("/users/me");
}
