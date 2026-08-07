import { bareClient } from "@/lib/bare-client";
import { api } from "@/lib/api-client";
import type { TokenPair } from "@/lib/api-types";

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

export async function emailLogin(email: string, password: string): Promise<TokenPair> {
  return (await bareClient.post("/auth/email/login", {
    email,
    password,
  })) as unknown as TokenPair;
}

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

export async function logoutRequest(refreshToken: string | null): Promise<void> {
  await bareClient.post("/auth/logout", { refreshToken });
}

export async function deleteAccountRequest(refreshToken: string | null): Promise<void> {
  await api.delete("/users/me", { data: { refreshToken } });
}
