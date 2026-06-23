import * as Apple from "expo-apple-authentication";
import * as AuthSession from "expo-auth-session";

import { getIdToken } from "@/features/auth/usecases/oauth-providers";
import { AppError } from "@/lib/app-error";

jest.mock("expo-apple-authentication", () => ({
  signInAsync: jest.fn(),
  AppleAuthenticationScope: { FULL_NAME: 0, EMAIL: 1 },
}));
jest.mock("expo-crypto", () => ({
  randomUUID: jest.fn(() => "raw-nonce"),
  digestStringAsync: jest.fn(async () => "ab+/c="),
  CryptoDigestAlgorithm: { SHA256: "SHA-256" },
  CryptoEncoding: { BASE64: "base64" },
}));
jest.mock("expo-web-browser", () => ({ maybeCompleteAuthSession: jest.fn() }));
jest.mock("expo-auth-session", () => ({
  fetchDiscoveryAsync: jest.fn(async () => ({ authorizationEndpoint: "x", tokenEndpoint: "y" })),
  makeRedirectUri: jest.fn(() => "pictrip://oauthredirect"),
  exchangeCodeAsync: jest.fn(),
  AuthRequest: jest.fn(),
}));
jest.mock("@/constants/oauth", () => ({
  OAUTH: { google: { clientId: "gid", webClientId: "gweb" }, kakao: { restKey: "kkey" } },
}));

describe("getIdToken", () => {
  beforeEach(() => jest.clearAllMocks());

  it("apple returns identityToken + raw nonce", async () => {
    (Apple.signInAsync as jest.Mock).mockResolvedValue({ identityToken: "apple-id-tok" });
    const res = await getIdToken("apple");
    expect(res).toEqual({ idToken: "apple-id-tok", nonce: "raw-nonce" });
  });

  it("apple maps user cancel to 'canceled'", async () => {
    (Apple.signInAsync as jest.Mock).mockRejectedValue({ code: "ERR_REQUEST_CANCELED" });
    expect(await getIdToken("apple")).toBe("canceled");
  });

  it("apple throws AppError on provider failure", async () => {
    (Apple.signInAsync as jest.Mock).mockRejectedValue(new Error("boom"));
    await expect(getIdToken("apple")).rejects.toBeInstanceOf(AppError);
  });

  it("web oidc (google) exchanges code → idToken", async () => {
    const promptAsync = jest.fn(async () => ({ type: "success", params: { code: "c1" } }));
    (AuthSession.AuthRequest as unknown as jest.Mock).mockImplementation(() => ({
      promptAsync,
      codeVerifier: "ver",
    }));
    (AuthSession.exchangeCodeAsync as jest.Mock).mockResolvedValue({ idToken: "g-id-tok" });
    const res = await getIdToken("google");
    expect(res).toEqual({ idToken: "g-id-tok", nonce: "raw-nonce" });
  });

  it("web oidc dismiss maps to 'canceled'", async () => {
    const promptAsync = jest.fn(async () => ({ type: "dismiss" }));
    (AuthSession.AuthRequest as unknown as jest.Mock).mockImplementation(() => ({ promptAsync }));
    expect(await getIdToken("kakao")).toBe("canceled");
  });
});
