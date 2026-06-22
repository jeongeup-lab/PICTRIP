import * as AppleAuthentication from "expo-apple-authentication";
import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import * as Crypto from "expo-crypto";
import { OAUTH } from "@/constants/oauth";
import { AppError } from "@/lib/app-error";

WebBrowser.maybeCompleteAuthSession();

export type Provider = "kakao" | "google" | "apple";

export interface OAuthCredential {
  idToken: string;
  nonce?: string;
}

export type OAuthOutcome = OAuthCredential | "canceled";

const REDIRECT_PATH = "oauthredirect";

function providerError(): never {
  throw new AppError(
    "OAUTH_PROVIDER_UNAVAILABLE",
    "로그인에 실패했어요. 잠시 후 다시 시도해 주세요.",
    502,
  );
}

function toBase64Url(b64: string): string {
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function appleLogin(): Promise<OAuthOutcome> {
  const rawNonce = Crypto.randomUUID();
  const hashed = toBase64Url(
    await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, rawNonce, {
      encoding: Crypto.CryptoEncoding.BASE64,
    }),
  );
  try {
    const cred = await AppleAuthentication.signInAsync({
      requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        AppleAuthentication.AppleAuthenticationScope.EMAIL,
      ],
      nonce: hashed,
    });
    if (!cred.identityToken) return providerError();
    return { idToken: cred.identityToken, nonce: rawNonce };
  } catch (e) {
    if (
      e &&
      typeof e === "object" &&
      "code" in e &&
      (e as { code: string }).code === "ERR_REQUEST_CANCELED"
    ) {
      return "canceled";
    }
    return providerError();
  }
}

interface OidcConfig {
  issuer: string;
  clientId: string;
  scopes: string[];
}

async function webOidcLogin(cfg: OidcConfig): Promise<OAuthOutcome> {
  if (!cfg.clientId) return providerError();
  const nonce = Crypto.randomUUID();
  const discovery = await AuthSession.fetchDiscoveryAsync(cfg.issuer);
  const redirectUri = AuthSession.makeRedirectUri({ scheme: "pictrip", path: REDIRECT_PATH });
  const request = new AuthSession.AuthRequest({
    clientId: cfg.clientId,
    scopes: cfg.scopes,
    redirectUri,
    usePKCE: true,
    extraParams: { nonce },
  });
  const result = await request.promptAsync(discovery);
  if (result.type !== "success" || !result.params.code) return "canceled";
  const token = await AuthSession.exchangeCodeAsync(
    {
      clientId: cfg.clientId,
      code: result.params.code,
      redirectUri,
      extraParams: { code_verifier: request.codeVerifier ?? "" },
    },
    discovery,
  );
  if (!token.idToken) return providerError();
  return { idToken: token.idToken, nonce };
}

/** Acquire a provider OIDC id_token. Apple = native; Google/Kakao = web OIDC
 * (code+PKCE). Returns "canceled" on user dismiss; throws AppError otherwise. */
export async function getIdToken(provider: Provider): Promise<OAuthOutcome> {
  if (provider === "apple") return appleLogin();
  if (provider === "google") {
    return webOidcLogin({
      issuer: "https://accounts.google.com",
      clientId: OAUTH.google.clientId,
      scopes: ["openid", "profile", "email"],
    });
  }
  return webOidcLogin({
    issuer: "https://kauth.kakao.com",
    clientId: OAUTH.kakao.restKey,
    scopes: ["openid"],
  });
}
