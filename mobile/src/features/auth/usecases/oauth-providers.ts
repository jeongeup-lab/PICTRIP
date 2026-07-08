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

// Kakao rejects custom-scheme redirect URIs (http/https only), so its OAuth
// redirect_uri is our web bounce page, which forwards back to APP_RETURN_URL.
const KAKAO_REDIRECT_URI = "https://pictrip.org/oauthredirect";
const APP_RETURN_URL = "pictrip://oauthredirect";

function providerError(detail?: string): never {
  // The failing stage is surfaced in the message — device-side OAuth failures
  // never reach the backend, so the screen is the only place to read them.
  throw new AppError(
    "OAUTH_PROVIDER_UNAVAILABLE",
    `로그인에 실패했어요. 잠시 후 다시 시도해 주세요.${detail ? ` (${detail})` : ""}`,
    502,
  );
}

// OAuth2 returns error=access_denied when the user declines consent on the
// provider's screen — that's a cancel, not a failure (S01: 취소는 무음 복귀).
function isConsentDeclined(error: string): boolean {
  return error === "access_denied";
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

function parseQueryParams(url: string): Record<string, string> {
  const q = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
  const out: Record<string, string> = {};
  for (const pair of q.split("&")) {
    if (!pair) continue;
    const i = pair.indexOf("=");
    const key = decodeURIComponent(i < 0 ? pair : pair.slice(0, i));
    out[key] = i < 0 ? "" : decodeURIComponent(pair.slice(i + 1).replace(/\+/g, " "));
  }
  return out;
}

/** Kakao OIDC via web bounce: redirect_uri is the https page, but the auth
 * session watches the pictrip:// scheme that page forwards to. We drive the
 * browser manually (not AuthRequest.promptAsync) because the redirect_uri sent
 * to Kakao and the URL that closes the session must differ. */
async function kakaoLogin(): Promise<OAuthOutcome> {
  const clientId = OAUTH.kakao.restKey;
  if (!clientId) return providerError();
  const nonce = Crypto.randomUUID();
  const discovery = await AuthSession.fetchDiscoveryAsync("https://kauth.kakao.com");
  const request = new AuthSession.AuthRequest({
    clientId,
    scopes: ["openid"],
    redirectUri: KAKAO_REDIRECT_URI,
    usePKCE: true,
    extraParams: { nonce },
  });
  const authUrl = await request.makeAuthUrlAsync(discovery);
  const result = await WebBrowser.openAuthSessionAsync(authUrl, APP_RETURN_URL);
  if (result.type === "cancel" || result.type === "dismiss") return "canceled";
  if (result.type !== "success") return providerError(`session:${result.type}`);
  const params = parseQueryParams(result.url);
  if (params.error) {
    return isConsentDeclined(params.error) ? "canceled" : providerError(`kakao:${params.error}`);
  }
  if (params.state !== request.state) return providerError("state-mismatch"); // CSRF guard
  if (!params.code) return providerError("no-code");
  let token: AuthSession.TokenResponse;
  try {
    token = await AuthSession.exchangeCodeAsync(
      {
        clientId,
        code: params.code,
        redirectUri: KAKAO_REDIRECT_URI,
        extraParams: { code_verifier: request.codeVerifier ?? "" },
      },
      discovery,
    );
  } catch (e) {
    return providerError(`exchange:${e instanceof Error ? e.message : String(e)}`);
  }
  if (!token.idToken) return providerError("no-id-token");
  return { idToken: token.idToken, nonce };
}

interface OidcConfig {
  issuer: string;
  clientId: string;
  scopes: string[];
  /** Custom URL scheme the provider redirects back to. Google iOS clients
   *  require the reversed-client-id scheme, not the app's pictrip:// scheme. */
  redirectScheme: string;
}

async function webOidcLogin(cfg: OidcConfig): Promise<OAuthOutcome> {
  if (!cfg.clientId) return providerError();
  const nonce = Crypto.randomUUID();
  const discovery = await AuthSession.fetchDiscoveryAsync(cfg.issuer);
  const redirectUri = AuthSession.makeRedirectUri({
    scheme: cfg.redirectScheme,
    path: REDIRECT_PATH,
  });
  const request = new AuthSession.AuthRequest({
    clientId: cfg.clientId,
    scopes: cfg.scopes,
    redirectUri,
    usePKCE: true,
    extraParams: { nonce },
  });
  const result = await request.promptAsync(discovery);
  if (result.type === "cancel" || result.type === "dismiss") return "canceled";
  if (result.type !== "success") return providerError(`session:${result.type}`);
  if (result.params.error) {
    return isConsentDeclined(result.params.error)
      ? "canceled"
      : providerError(`provider:${result.params.error}`);
  }
  if (!result.params.code) return providerError("no-code");
  let token: AuthSession.TokenResponse;
  try {
    token = await AuthSession.exchangeCodeAsync(
      {
        clientId: cfg.clientId,
        code: result.params.code,
        redirectUri,
        extraParams: { code_verifier: request.codeVerifier ?? "" },
      },
      discovery,
    );
  } catch (e) {
    return providerError(`exchange:${e instanceof Error ? e.message : String(e)}`);
  }
  if (!token.idToken) return providerError("no-id-token");
  return { idToken: token.idToken, nonce };
}

/** Acquire a provider OIDC id_token. Apple = native; Google/Kakao = web OIDC
 * (code+PKCE). Returns "canceled" on user dismiss; throws AppError otherwise. */
export async function getIdToken(provider: Provider): Promise<OAuthOutcome> {
  if (provider === "apple") return appleLogin();
  if (provider === "google") {
    const clientId = OAUTH.google.clientId;
    // Google native OAuth clients redirect to the reversed-client-id scheme
    // (e.g. com.googleusercontent.apps.123-abc://oauthredirect), not pictrip://.
    const redirectScheme =
      "com.googleusercontent.apps." + clientId.replace(/\.apps\.googleusercontent\.com$/, "");
    return webOidcLogin({
      issuer: "https://accounts.google.com",
      clientId,
      scopes: ["openid", "profile", "email"],
      redirectScheme,
    });
  }
  return kakaoLogin();
}
