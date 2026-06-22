# P3 Auth + Save/Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add trigger-based OAuth login (Kakao·Google·Apple OIDC) plus the scrap/save and profile (마이) features it gates, on top of the guest-first P0–P2 app.

**Architecture:** A `src/features/auth/` module owns the login surfaces (shared `LoginCard` → fullscreen route + promise-based root sheet), the OAuth id_token usecases, and the extended auth store. A `src/features/saved/` module owns the bookmark API + TanStack queries with optimistic updates (single-page, limit 60). A `src/features/profile/` module + rewritten profile tab renders the 3 mockup variants. All API calls reuse the existing `api`/`bareClient` (JSend unwrapped once); UI branches on `err.code`.

**Tech Stack:** Expo SDK 56 · RN 0.85 · React 19.2 · TS strict · Expo Router (typed routes) · zustand · TanStack Query · axios · react-native-svg · **new: expo-apple-authentication · expo-auth-session · expo-web-browser · expo-crypto · expo-constants** · jest-expo.

## Global Constraints

- Design SSOT: `docs/mockups/03-login.html`·`13-saved.html`·`14-profile.html`·`15-profile-states.html`. Spec: `docs/superpowers/specs/2026-06-22-mobile-p3-auth-save-design.md`. Locked auth decisions: `docs/specs/screens/S01-onboarding-auth.md`.
- **No emoji. Monochrome tokens only** (`src/constants/theme.ts`). The ONLY color exception = social buttons' brand colors (Kakao `#FEE500`, Google white+border, Apple `#111113`), per mockup 03. Icons = line-SVG `<Icon>` only.
- **No `as any`.** Use `as unknown as T` where a typed cast is unavoidable (matches `api-client.ts`/`bare-client.ts`).
- File naming: components PascalCase; runtime modules (api/lib/stores/usecases/hooks/constants) kebab-case; `src/app/**` follows Expo Router.
- **JSend is unwrapped once** in `api-client`/`bare-client`; feature `api.ts` must **not** re-unwrap. 204 responses unwrap to `undefined` (safe for void calls). UI branches on `err.code` (`AppError`), never `err.message`.
- **Auth model**: access token in memory (auth-store), refresh token in `expo-secure-store`. OAuth = id_token verified by backend at `POST /auth/oauth/{provider}`. Logout/withdraw via Redis jti denylist (backend) — client only needs to call the endpoints + clear local state.
- **Dependencies added via `expo install` only.** No non-Expo native modules.
- **Secrets**: `EXPO_PUBLIC_*` env only, never in code/commits.
- Verification (run in `mobile/` before declaring any task done): `npm run lint && npm run typecheck && npm run format:check && npm test`.
- Commit per task. **Do not push** unless explicitly asked.

## Backend contract (verified against `backend/app/modules/users/`)

- `POST /auth/oauth/{provider}` body `{ idToken, nonce? }` → `TokenPair { accessToken, refreshToken, expiresIn, user }`. provider ∈ `kakao|google|apple`. Errors: `OAUTH_ID_TOKEN_INVALID` (401), `OAUTH_PROVIDER_UNAVAILABLE` (502).
- `POST /auth/refresh` body `{ refreshToken }` → `TokenPair` (already wired in auth-store).
- `POST /auth/logout` body `{ refreshToken? }` → `{}` (idempotent).
- `GET /users/me` (auth) → `UserPublic`. `DELETE /users/me` (auth) → 204.
- `PUT /users/me/consents` (auth) body `{ locationConsent, photoConsent, termsVersion }` → `ConsentOut`.
- `GET /users/me/saved?limit=&cursor=` (auth) → `SpotCard[]` (+ pagination meta, unused in P3). `POST /users/me/saved/{contentId}` (auth) → 201/200. `DELETE /users/me/saved/{contentId}` (auth) → 204. No-token on any `/users/*` → `GUEST_FORBIDDEN` (403).

---

### Task 1: Foundation — deps, config, constants, icons

**Files:**
- Modify: `mobile/package.json` (via `expo install`)
- Modify: `mobile/app.json` (plugins)
- Create: `mobile/.env.example`
- Create: `mobile/src/constants/legal.ts`
- Create: `mobile/src/constants/oauth.ts`
- Create: `mobile/src/lib/app-meta.ts`
- Modify: `mobile/src/components/Icon.tsx`
- Test: `mobile/src/components/__tests__/Icon.test.tsx` (extend)

**Interfaces:**
- Produces:
  - `TERMS_VERSION: string` (`@/constants/legal`)
  - `OAUTH: { google: { iosClientId, androidClientId, webClientId }, kakao: { restKey } }` (`@/constants/oauth`)
  - `APP_VERSION: string` (`@/lib/app-meta`)
  - `IconName` additions: `"log-in"`, `"log-out"`, `"info"`.

- [ ] **Step 1: Install dependencies**

Run (in `mobile/`):
```bash
npx expo install expo-apple-authentication expo-auth-session expo-web-browser expo-crypto expo-constants
```
Expected: all five added to `package.json` dependencies.

- [ ] **Step 2: Register the Apple Sign-In plugin**

Edit `mobile/app.json` — add `"expo-apple-authentication"` to the `plugins` array (after `"expo-image-picker"` block) and add `usesAppleSignIn` to `ios`:
```json
    "ios": {
      "bundleIdentifier": "org.pictrip.app",
      "associatedDomains": ["applinks:pictrip.org"],
      "usesAppleSignIn": true
    },
```
and in `plugins`, append:
```json
      ,"expo-apple-authentication"
```

- [ ] **Step 3: Create `.env.example`**

Create `mobile/.env.example`:
```bash
# Public runtime config (Expo inlines EXPO_PUBLIC_* at build time).
EXPO_PUBLIC_API_BASE=https://api.pictrip.org

# OAuth client IDs / keys — fill from provider consoles (see spec §11).
# Leave blank in dev; the matching social button shows an inline error if used.
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=
EXPO_PUBLIC_KAKAO_REST_KEY=
```

- [ ] **Step 4: Create the constants**

Create `mobile/src/constants/legal.ts`:
```ts
/** Terms version recorded as implied consent at login (S01 §3, S11 §D7).
 * Bump when 약관/개인정보처리방침 are republished to force re-consent (P5). */
export const TERMS_VERSION = "2026-06-22";
```

Create `mobile/src/constants/oauth.ts`:
```ts
import { Platform } from "react-native";

/** OAuth client config from EXPO_PUBLIC_* env (placeholders until consoles set up).
 * Apple needs no client id (native bundle id is the audience). */
export const OAUTH = {
  google: {
    clientId:
      (Platform.OS === "ios"
        ? process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID
        : process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID) ?? "",
    webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? "",
  },
  kakao: {
    restKey: process.env.EXPO_PUBLIC_KAKAO_REST_KEY ?? "",
  },
} as const;
```

Create `mobile/src/lib/app-meta.ts`:
```ts
import Constants from "expo-constants";

/** App version for the 마이 settings row (mockup 14). */
export const APP_VERSION = Constants.expoConfig?.version ?? "0.0.0";
```

- [ ] **Step 5: Add icons**

In `mobile/src/components/Icon.tsx`, add to the `IconName` union (after `"sparkle"`):
```ts
  | "log-in"
  | "log-out"
  | "info"
```
Add to the `PATHS` record:
```ts
  "log-in": { d: "M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" },
  "log-out": { d: "M15 17l5-5-5-5M20 12H9M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3" },
  info: { d: "M12 11v5M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z" },
```

- [ ] **Step 6: Extend the Icon render test**

In `mobile/src/components/__tests__/Icon.test.tsx`, add inside the `describe`:
```tsx
  it.each(["log-in", "log-out", "info"] as const)("renders %s", async (name) => {
    let r: renderer.ReactTestRenderer;
    await act(async () => {
      r = renderer.create(<Icon name={name} />);
    });
    expect(r!.toJSON()).toBeTruthy();
  });
```

- [ ] **Step 7: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/package.json mobile/package-lock.json mobile/app.json mobile/.env.example mobile/src/constants/legal.ts mobile/src/constants/oauth.ts mobile/src/lib/app-meta.ts mobile/src/components/Icon.tsx mobile/src/components/__tests__/Icon.test.tsx
git commit -m "feat(mobile): P3 foundation — auth deps, oauth/legal constants, icons"
```

---

### Task 2: Auth API

**Files:**
- Create: `mobile/src/features/auth/api.ts`
- Test: `mobile/src/features/auth/__tests__/api.test.ts`

**Interfaces:**
- Consumes: `bareClient` (`@/lib/bare-client`), `api` (`@/lib/api-client`), `TokenPair` (`@/lib/api-types`).
- Produces:
  - `oauthLogin(provider: string, idToken: string, nonce?: string): Promise<TokenPair>`
  - `logoutRequest(refreshToken: string | null): Promise<void>`
  - `deleteAccountRequest(): Promise<void>`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/auth/__tests__/api.test.ts`:
```ts
jest.mock("@/lib/bare-client", () => ({ bareClient: { post: jest.fn() } }));
jest.mock("@/lib/api-client", () => ({ api: { delete: jest.fn() } }));

import { bareClient } from "@/lib/bare-client";
import { api } from "@/lib/api-client";
import { oauthLogin, logoutRequest, deleteAccountRequest } from "@/features/auth/api";

describe("auth api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("oauthLogin posts idToken+nonce to the provider path and returns the pair", async () => {
    const pair = { accessToken: "a", refreshToken: "r", expiresIn: 900, user: { id: 1 } };
    (bareClient.post as jest.Mock).mockResolvedValue(pair);
    const res = await oauthLogin("kakao", "tok", "n1");
    expect(bareClient.post).toHaveBeenCalledWith("/auth/oauth/kakao", { idToken: "tok", nonce: "n1" });
    expect(res).toBe(pair);
  });

  it("logoutRequest posts the refresh token", async () => {
    (bareClient.post as jest.Mock).mockResolvedValue({});
    await logoutRequest("r1");
    expect(bareClient.post).toHaveBeenCalledWith("/auth/logout", { refreshToken: "r1" });
  });

  it("deleteAccountRequest calls authed DELETE /users/me", async () => {
    (api.delete as jest.Mock).mockResolvedValue(undefined);
    await deleteAccountRequest();
    expect(api.delete).toHaveBeenCalledWith("/users/me");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/auth/__tests__/api.test.ts`
Expected: FAIL — cannot find module `api`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/auth/api.ts`:
```ts
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

/** Denylist the refresh token server-side. Idempotent; unauthed. */
export async function logoutRequest(refreshToken: string | null): Promise<void> {
  await bareClient.post("/auth/logout", { refreshToken });
}

/** 회원 탈퇴 — authed DELETE; backend anonymizes + unlinks OAuth (204). */
export async function deleteAccountRequest(): Promise<void> {
  await api.delete("/users/me");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/auth/__tests__/api.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/auth/api.ts mobile/src/features/auth/__tests__/api.test.ts
git commit -m "feat(mobile): auth api (oauth login, logout, delete account)"
```

---

### Task 3: OAuth provider usecases (id_token acquisition)

**Files:**
- Create: `mobile/src/features/auth/usecases/oauth-providers.ts`
- Test: `mobile/src/features/auth/usecases/__tests__/oauth-providers.test.ts`

**Interfaces:**
- Consumes: `expo-apple-authentication`, `expo-auth-session`, `expo-web-browser`, `expo-crypto`, `OAUTH` (`@/constants/oauth`), `AppError` (`@/lib/app-error`).
- Produces:
  - `type Provider = "kakao" | "google" | "apple"`
  - `interface OAuthCredential { idToken: string; nonce?: string }`
  - `type OAuthOutcome = OAuthCredential | "canceled"`
  - `getIdToken(provider: Provider): Promise<OAuthOutcome>` — returns `"canceled"` on user cancel; throws `AppError("OAUTH_PROVIDER_UNAVAILABLE", …, 502)` on provider failure / missing config.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/auth/usecases/__tests__/oauth-providers.test.ts`:
```ts
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

import * as Apple from "expo-apple-authentication";
import * as AuthSession from "expo-auth-session";
import { getIdToken } from "@/features/auth/usecases/oauth-providers";
import { AppError } from "@/lib/app-error";

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/auth/usecases/__tests__/oauth-providers.test.ts`
Expected: FAIL — cannot find module `oauth-providers`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/auth/usecases/oauth-providers.ts`:
```ts
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
  throw new AppError("OAUTH_PROVIDER_UNAVAILABLE", "로그인에 실패했어요. 잠시 후 다시 시도해 주세요.", 502);
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
    if (e && typeof e === "object" && "code" in e && (e as { code: string }).code === "ERR_REQUEST_CANCELED") {
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/auth/usecases/__tests__/oauth-providers.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/auth/usecases/oauth-providers.ts mobile/src/features/auth/usecases/__tests__/oauth-providers.test.ts
git commit -m "feat(mobile): oauth id_token usecases (apple native + google/kakao web oidc)"
```

---

### Task 4: Consent snapshot usecase

**Files:**
- Create: `mobile/src/features/auth/usecases/record-consent.ts`
- Test: `mobile/src/features/auth/usecases/__tests__/record-consent.test.ts`

**Interfaces:**
- Consumes: `expo-location`, `api` (`@/lib/api-client`), `TERMS_VERSION` (`@/constants/legal`).
- Produces: `recordConsentSnapshot(): Promise<void>` — PUTs implied consent + location-permission snapshot. Never requests permission.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/auth/usecases/__tests__/record-consent.test.ts`:
```ts
jest.mock("expo-location", () => ({ getForegroundPermissionsAsync: jest.fn() }));
jest.mock("@/lib/api-client", () => ({ api: { put: jest.fn() } }));
jest.mock("@/constants/legal", () => ({ TERMS_VERSION: "2026-06-22" }));

import * as Location from "expo-location";
import { api } from "@/lib/api-client";
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";

describe("recordConsentSnapshot", () => {
  beforeEach(() => jest.clearAllMocks());

  it("PUTs locationConsent=true when permission granted", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (api.put as jest.Mock).mockResolvedValue({});
    await recordConsentSnapshot();
    expect(api.put).toHaveBeenCalledWith("/users/me/consents", {
      locationConsent: true,
      photoConsent: false,
      termsVersion: "2026-06-22",
    });
  });

  it("PUTs locationConsent=false when not granted", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: false });
    (api.put as jest.Mock).mockResolvedValue({});
    await recordConsentSnapshot();
    expect(api.put).toHaveBeenCalledWith(
      "/users/me/consents",
      expect.objectContaining({ locationConsent: false }),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/auth/usecases/__tests__/record-consent.test.ts`
Expected: FAIL — cannot find module `record-consent`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/auth/usecases/record-consent.ts`:
```ts
import * as Location from "expo-location";
import { api } from "@/lib/api-client";
import { TERMS_VERSION } from "@/constants/legal";

/** Record implied consent at login (S01 §3): current terms version + a snapshot
 * of the OS location permission. Never prompts. Caller fires-and-forgets. */
export async function recordConsentSnapshot(): Promise<void> {
  const perm = await Location.getForegroundPermissionsAsync();
  await api.put("/users/me/consents", {
    locationConsent: perm.granted,
    photoConsent: false,
    termsVersion: TERMS_VERSION,
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/auth/usecases/__tests__/record-consent.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/auth/usecases/record-consent.ts mobile/src/features/auth/usecases/__tests__/record-consent.test.ts
git commit -m "feat(mobile): consent snapshot usecase (implied terms + location perm)"
```

---

### Task 5: Auth store — login/logout/delete/dev actions

**Files:**
- Modify: `mobile/src/features/auth/stores/auth-store.ts`
- Test: `mobile/src/features/auth/stores/__tests__/auth-store.test.ts` (extend; keep existing tests passing)

**Interfaces:**
- Consumes: `getIdToken`/`Provider` (Task 3), `oauthLogin`/`logoutRequest`/`deleteAccountRequest` (Task 2), `recordConsentSnapshot` (Task 4), `getRefreshToken` (`@/lib/storage`).
- Produces (added to `AuthState`):
  - `loginWithOAuth(provider: Provider): Promise<"success" | "canceled">` — throws `AppError` on failure.
  - `logout(): Promise<void>`
  - `deleteAccount(): Promise<void>`
  - `devLogin(): void` (`__DEV__` UI smoke only; in-memory fake session, no refresh persisted)

- [ ] **Step 1: Write the failing test (extend existing file)**

Append to `mobile/src/features/auth/stores/__tests__/auth-store.test.ts` (add these mocks at top of file if not present, and a new describe block):
```ts
jest.mock("@/features/auth/usecases/oauth-providers", () => ({ getIdToken: jest.fn() }));
jest.mock("@/features/auth/usecases/record-consent", () => ({ recordConsentSnapshot: jest.fn() }));
jest.mock("@/features/auth/api", () => ({
  oauthLogin: jest.fn(),
  logoutRequest: jest.fn(),
  deleteAccountRequest: jest.fn(),
}));

import { getIdToken } from "@/features/auth/usecases/oauth-providers";
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import { oauthLogin, logoutRequest, deleteAccountRequest } from "@/features/auth/api";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { AppError } from "@/lib/app-error";

const pair = {
  accessToken: "acc",
  refreshToken: "ref",
  expiresIn: 900,
  user: { id: 1, displayName: "이신성", email: "a@b.c", avatarUrl: null, isOnboarded: false, createdAt: null },
};

describe("auth-store P3 actions", () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    (recordConsentSnapshot as jest.Mock).mockResolvedValue(undefined);
    await useAuthStore.getState().clear();
  });

  it("loginWithOAuth success sets the session and records consent", async () => {
    (getIdToken as jest.Mock).mockResolvedValue({ idToken: "t", nonce: "n" });
    (oauthLogin as jest.Mock).mockResolvedValue(pair);
    const res = await useAuthStore.getState().loginWithOAuth("kakao");
    expect(res).toBe("success");
    expect(oauthLogin).toHaveBeenCalledWith("kakao", "t", "n");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user?.id).toBe(1);
    expect(recordConsentSnapshot).toHaveBeenCalled();
  });

  it("loginWithOAuth returns 'canceled' without calling the backend", async () => {
    (getIdToken as jest.Mock).mockResolvedValue("canceled");
    expect(await useAuthStore.getState().loginWithOAuth("apple")).toBe("canceled");
    expect(oauthLogin).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("loginWithOAuth propagates AppError from the backend", async () => {
    (getIdToken as jest.Mock).mockResolvedValue({ idToken: "t" });
    (oauthLogin as jest.Mock).mockRejectedValue(new AppError("OAUTH_ID_TOKEN_INVALID", "x", 401));
    await expect(useAuthStore.getState().loginWithOAuth("google")).rejects.toBeInstanceOf(AppError);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("logout clears the session even if the request fails", async () => {
    await useAuthStore.getState().setSession(pair);
    (logoutRequest as jest.Mock).mockRejectedValue(new Error("net"));
    await useAuthStore.getState().logout();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("deleteAccount clears the session on success", async () => {
    await useAuthStore.getState().setSession(pair);
    (deleteAccountRequest as jest.Mock).mockResolvedValue(undefined);
    await useAuthStore.getState().deleteAccount();
    expect(deleteAccountRequest).toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("devLogin sets a fake in-memory session", () => {
    useAuthStore.getState().devLogin();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().accessToken).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/auth/stores/__tests__/auth-store.test.ts`
Expected: FAIL — `loginWithOAuth is not a function` (and the new mocks load).

- [ ] **Step 3: Implement the new actions**

In `mobile/src/features/auth/stores/auth-store.ts`:

Add imports at the top (after the existing imports):
```ts
import type { User } from "@/lib/api-types";
import { getIdToken, type Provider } from "@/features/auth/usecases/oauth-providers";
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import { oauthLogin, logoutRequest, deleteAccountRequest } from "@/features/auth/api";
```
(Adjust the existing `import type { TokenPair, User } from "@/lib/api-types";` so `User` is imported once — if `User` is already imported, do not duplicate it.)

Add to the `AuthState` interface:
```ts
  loginWithOAuth: (provider: Provider) => Promise<"success" | "canceled">;
  logout: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  devLogin: () => void;
```

Add the implementations inside the store (after `hydrate`):
```ts
  loginWithOAuth: async (provider) => {
    const outcome = await getIdToken(provider);
    if (outcome === "canceled") return "canceled";
    const pair = await oauthLogin(provider, outcome.idToken, outcome.nonce);
    await get().setSession(pair);
    // Consent is best-effort — never block login on it (S01 §3).
    void recordConsentSnapshot().catch(() => undefined);
    return "success";
  },

  logout: async () => {
    const refreshToken = await getRefreshToken();
    try {
      await logoutRequest(refreshToken);
    } catch {
      // Logout is local-authoritative; server denylist is best-effort.
    }
    await get().clear();
  },

  deleteAccount: async () => {
    await deleteAccountRequest();
    await get().clear();
  },

  devLogin: () => {
    const user: User = {
      id: 0,
      displayName: "개발자",
      email: "dev@pictrip.local",
      avatarUrl: null,
      isOnboarded: true,
      createdAt: null,
    };
    // __DEV__ smoke only — no backend call, no refresh persisted.
    set({ accessToken: "dev-access-token", user, isAuthenticated: true });
  },
```
(`getRefreshToken` is already imported in this file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx jest src/features/auth/stores/__tests__/auth-store.test.ts`
Expected: PASS (existing + 6 new).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/auth/stores/auth-store.ts mobile/src/features/auth/stores/__tests__/auth-store.test.ts
git commit -m "feat(mobile): auth-store oauth login/logout/delete + dev login"
```

---

### Task 6: Auth-prompt store + auth gate hook

**Files:**
- Create: `mobile/src/features/auth/stores/auth-prompt-store.ts`
- Create: `mobile/src/features/auth/hooks/use-auth-gate.ts`
- Test: `mobile/src/features/auth/stores/__tests__/auth-prompt-store.test.ts`

**Interfaces:**
- Produces:
  - `type AuthReason = "save" | "saved-list"`
  - `useAuthPromptStore` (zustand) state `{ visible, reason, resolve }` + actions `prompt(reason): Promise<boolean>`, `succeed()`, `dismiss()`.
  - `useAuthGate(): (reason: AuthReason) => Promise<boolean>` — resolves `true` immediately if authenticated, else opens the sheet and resolves on success/dismiss.

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/auth/stores/__tests__/auth-prompt-store.test.ts`:
```ts
import { useAuthPromptStore } from "@/features/auth/stores/auth-prompt-store";

describe("auth-prompt-store", () => {
  beforeEach(() => useAuthPromptStore.setState({ visible: false, reason: null, resolve: null }));

  it("prompt opens the sheet and resolves true on succeed", async () => {
    const p = useAuthPromptStore.getState().prompt("save");
    expect(useAuthPromptStore.getState().visible).toBe(true);
    expect(useAuthPromptStore.getState().reason).toBe("save");
    useAuthPromptStore.getState().succeed();
    await expect(p).resolves.toBe(true);
    expect(useAuthPromptStore.getState().visible).toBe(false);
  });

  it("prompt resolves false on dismiss", async () => {
    const p = useAuthPromptStore.getState().prompt("saved-list");
    useAuthPromptStore.getState().dismiss();
    await expect(p).resolves.toBe(false);
    expect(useAuthPromptStore.getState().resolve).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/auth/stores/__tests__/auth-prompt-store.test.ts`
Expected: FAIL — cannot find module `auth-prompt-store`.

- [ ] **Step 3: Write the store + hook**

Create `mobile/src/features/auth/stores/auth-prompt-store.ts`:
```ts
import { create } from "zustand";

export type AuthReason = "save" | "saved-list";

interface AuthPromptState {
  visible: boolean;
  reason: AuthReason | null;
  resolve: ((ok: boolean) => void) | null;
  prompt: (reason: AuthReason) => Promise<boolean>;
  succeed: () => void;
  dismiss: () => void;
}

/** Imperative login-nudge gate. `prompt()` opens the root sheet and returns a
 * promise that resolves true (logged in) or false (dismissed) so callers can
 * resume the pending action (S01 §3 보류 액션 재개). */
export const useAuthPromptStore = create<AuthPromptState>((set, get) => ({
  visible: false,
  reason: null,
  resolve: null,
  prompt: (reason) =>
    new Promise<boolean>((resolve) => set({ visible: true, reason, resolve })),
  succeed: () => {
    get().resolve?.(true);
    set({ visible: false, reason: null, resolve: null });
  },
  dismiss: () => {
    get().resolve?.(false);
    set({ visible: false, reason: null, resolve: null });
  },
}));
```

Create `mobile/src/features/auth/hooks/use-auth-gate.ts`:
```ts
import { useCallback } from "react";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useAuthPromptStore, type AuthReason } from "@/features/auth/stores/auth-prompt-store";

/** Returns a guard: `await requireAuth(reason)` is true when the user is (or
 * becomes) logged in, false when they dismiss the nudge. */
export function useAuthGate(): (reason: AuthReason) => Promise<boolean> {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const prompt = useAuthPromptStore((s) => s.prompt);
  return useCallback(
    (reason: AuthReason) => (isAuthenticated ? Promise.resolve(true) : prompt(reason)),
    [isAuthenticated, prompt],
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/auth/stores/__tests__/auth-prompt-store.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/auth/stores/auth-prompt-store.ts mobile/src/features/auth/hooks/use-auth-gate.ts mobile/src/features/auth/stores/__tests__/auth-prompt-store.test.ts
git commit -m "feat(mobile): auth-prompt store + useAuthGate (promise-based login nudge)"
```

---

### Task 7: SocialButton + LoginCard components

**Files:**
- Create: `mobile/src/features/auth/components/SocialButton.tsx`
- Create: `mobile/src/features/auth/components/LoginCard.tsx`

> Components here are not unit-tested (heavy provider/native deps); gate = lint + typecheck + format + suite stays green.

**Interfaces:**
- Consumes: `useAuthStore().loginWithOAuth` (Task 5), `Provider` (Task 3), theme tokens, `react-native-svg`.
- Produces:
  - `SocialButton({ provider, onPress, loading, disabled })` where `provider: Provider`.
  - `LoginCard({ variant, onSuccess, onCancel })` — `variant: "full" | "sheet"`. Renders brand/headline + 3 social buttons + terms; drives `loginWithOAuth`; on success calls `onSuccess`.

- [ ] **Step 1: Build SocialButton**

Create `mobile/src/features/auth/components/SocialButton.tsx`:
```tsx
import { Pressable, Text, View, ActivityIndicator, StyleSheet } from "react-native";
import Svg, { Path } from "react-native-svg";
import type { Provider } from "@/features/auth/usecases/oauth-providers";
import { colors } from "@/constants/theme";

interface Props {
  provider: Provider;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
}

const LABEL: Record<Provider, string> = {
  kakao: "카카오로 계속하기",
  google: "Google로 계속하기",
  apple: "Apple로 계속하기",
};

// Brand colors are the documented exception to the monochrome rule (mockup 03).
const STYLE: Record<Provider, { bg: string; fg: string; border?: string }> = {
  kakao: { bg: "#FEE500", fg: "#181600" },
  google: { bg: "#FFFFFF", fg: colors.ink, border: colors.line },
  apple: { bg: "#111113", fg: "#FFFFFF" },
};

function ProviderGlyph({ provider, color }: { provider: Provider; color: string }) {
  if (provider === "kakao") {
    return (
      <Svg width={20} height={20} viewBox="0 0 24 24" fill={color}>
        <Path d="M12 3C6.9 3 2.8 6.2 2.8 10.2c0 2.6 1.8 4.9 4.4 6.2-.2.7-.7 2.5-.8 2.9 0 .2.1.4.4.2.2-.1 2.6-1.8 3.7-2.5.5.1 1 .1 1.5.1 5.1 0 9.2-3.2 9.2-7.2S17.1 3 12 3z" />
      </Svg>
    );
  }
  if (provider === "apple") {
    return (
      <Svg width={20} height={20} viewBox="0 0 24 24" fill={color}>
        <Path d="M16.4 12.8c0-2.2 1.8-3.3 1.9-3.4-1-1.5-2.6-1.7-3.2-1.7-1.4-.1-2.6.8-3.3.8-.7 0-1.7-.8-2.8-.8-1.5 0-2.8.8-3.6 2.2-1.5 2.7-.4 6.6 1.1 8.8.7 1 1.6 2.2 2.7 2.2 1.1 0 1.5-.7 2.8-.7s1.6.7 2.8.7c1.2 0 1.9-1.1 2.6-2.1.8-1.2 1.2-2.3 1.2-2.4-.1 0-2.3-.9-2.3-3.6zM14.3 6.1c.6-.7 1-1.7.9-2.7-.9 0-1.9.6-2.5 1.3-.5.6-1 1.6-.9 2.6 1 0 2-.5 2.5-1.2z" />
      </Svg>
    );
  }
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24">
      <Path fill="#4285F4" d="M22.5 12.2c0-.7-.06-1.4-.18-2.05H12v3.88h5.9a5.05 5.05 0 0 1-2.19 3.31v2.75h3.54c2.07-1.9 3.25-4.7 3.25-7.89Z" />
      <Path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.54-2.75c-.98.66-2.23 1.05-3.74 1.05-2.87 0-5.3-1.94-6.17-4.55H2.18v2.84A11 11 0 0 0 12 23Z" />
      <Path fill="#FBBC05" d="M5.83 14.09a6.6 6.6 0 0 1 0-4.18V7.07H2.18a11 11 0 0 0 0 9.86l3.65-2.84Z" />
      <Path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.14-3.14C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07l3.65 2.84C6.7 7.3 9.13 5.38 12 5.38Z" />
    </Svg>
  );
}

export function SocialButton({ provider, onPress, loading, disabled }: Props) {
  const s = STYLE[provider];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={[
        styles.btn,
        { backgroundColor: s.bg },
        s.border ? { borderWidth: 1, borderColor: s.border } : null,
        (disabled || loading) && styles.dim,
      ]}
    >
      <View style={styles.glyph}>
        {loading ? <ActivityIndicator color={s.fg} /> : <ProviderGlyph provider={provider} color={s.fg} />}
      </View>
      <Text style={[styles.label, { color: s.fg }]}>{LABEL[provider]}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    height: 54,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  glyph: { position: "absolute", left: 18 },
  label: { fontSize: 16, fontWeight: "700" },
  dim: { opacity: 0.6 },
});
```

- [ ] **Step 2: Build LoginCard**

Create `mobile/src/features/auth/components/LoginCard.tsx`:
```tsx
import { useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { SocialButton } from "@/features/auth/components/SocialButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import type { Provider } from "@/features/auth/usecases/oauth-providers";
import { AppError } from "@/lib/app-error";
import { colors, spacing } from "@/constants/theme";

interface Props {
  variant: "full" | "sheet";
  onSuccess: () => void;
  onCancel?: () => void;
}

const PROVIDERS: Provider[] = ["kakao", "google", "apple"];

function BrandSymbol() {
  return (
    <View style={styles.sym}>
      <Svg width={46} height={46} viewBox="0 0 48 48" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
        <Circle cx={20} cy={10} r={3.6} />
        <Path d="M20 13.6 V28.5" />
        <Path d="M20 28.5 L15 40" />
        <Path d="M20 28.5 L25 40" />
        <Path d="M20 18 L26.5 15" />
        <Path d="M20 18.5 L15.5 24" />
        <Rect x={26} y={11.4} width={8} height={5.2} rx={1.6} fill="#fff" stroke="none" />
        <Circle cx={30} cy={14} r={1.3} fill={colors.ink} />
      </Svg>
    </View>
  );
}

export function LoginCard({ variant, onSuccess, onCancel }: Props) {
  const loginWithOAuth = useAuthStore((s) => s.loginWithOAuth);
  const [pending, setPending] = useState<Provider | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handle = async (provider: Provider) => {
    if (pending) return;
    setPending(provider);
    setError(null);
    try {
      const res = await loginWithOAuth(provider);
      if (res === "success") onSuccess();
      else onCancel?.(); // canceled = silent (S01)
    } catch (e) {
      setError(e instanceof AppError ? "잠시 후 다시 시도해 주세요." : "잠시 후 다시 시도해 주세요.");
    } finally {
      setPending(null);
    }
  };

  return (
    <View style={variant === "full" ? styles.full : styles.sheet}>
      {variant === "full" ? (
        <View style={styles.brand}>
          <BrandSymbol />
          <Text style={styles.word}>PicTrip</Text>
        </View>
      ) : (
        <Text style={styles.sheetTitle}>저장하려면 로그인이 필요해요</Text>
      )}

      <View style={styles.social}>
        {PROVIDERS.map((p) => (
          <SocialButton
            key={p}
            provider={p}
            loading={pending === p}
            disabled={pending !== null && pending !== p}
            onPress={() => handle(p)}
          />
        ))}
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Text style={styles.terms}>
        계속 진행하면 이용약관 및 개인정보처리방침에{"\n"}동의하는 것으로 간주돼요.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  full: { flex: 1, justifyContent: "center", paddingBottom: spacing.xxl },
  sheet: { paddingTop: spacing.sm },
  brand: { alignItems: "center", marginBottom: spacing.xxl },
  sym: {
    width: 72,
    height: 72,
    borderRadius: 20,
    backgroundColor: colors.ink,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  word: { fontSize: 28, fontWeight: "800", letterSpacing: -0.84, color: colors.ink },
  sheetTitle: {
    fontSize: 20,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
    textAlign: "center",
    marginBottom: spacing.lg,
  },
  social: { paddingHorizontal: spacing.lg, gap: 11 },
  error: { color: colors.sec, fontSize: 13, textAlign: "center", marginTop: spacing.md },
  terms: {
    textAlign: "center",
    fontSize: 12,
    lineHeight: 19,
    color: colors.ter,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
  },
});
```

- [ ] **Step 3: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/auth/components/SocialButton.tsx mobile/src/features/auth/components/LoginCard.tsx
git commit -m "feat(mobile): SocialButton + LoginCard (full/sheet variants)"
```

---

### Task 8: Login navigation — fullscreen route, nudge sheet, root wiring

**Files:**
- Create: `mobile/src/features/auth/components/AuthPromptSheet.tsx`
- Create: `mobile/src/app/auth/login.tsx`
- Modify: `mobile/src/app/_layout.tsx`

> Screens/overlays are not unit-tested; gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: `useAuthPromptStore` (Task 6), `LoginCard` (Task 7), `Icon`, theme tokens, `expo-router`.
- Produces: route `/auth/login` (fullScreenModal); root-mounted `<AuthPromptSheet/>`.

- [ ] **Step 1: Build the nudge sheet**

Create `mobile/src/features/auth/components/AuthPromptSheet.tsx`:
```tsx
import { Modal, Pressable, View, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { LoginCard } from "@/features/auth/components/LoginCard";
import { useAuthPromptStore } from "@/features/auth/stores/auth-prompt-store";
import { colors, spacing, radii } from "@/constants/theme";

/** Root-mounted bottom sheet for the login nudge (save 등 inline 승격).
 * Driven by the auth-prompt store; resolves the pending action on success. */
export function AuthPromptSheet() {
  const insets = useSafeAreaInsets();
  const visible = useAuthPromptStore((s) => s.visible);
  const succeed = useAuthPromptStore((s) => s.succeed);
  const dismiss = useAuthPromptStore((s) => s.dismiss);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={dismiss}>
      <Pressable style={styles.scrim} onPress={dismiss}>
        <Pressable
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.grabber} />
          <LoginCard variant="sheet" onSuccess={succeed} onCancel={dismiss} />
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, justifyContent: "flex-end", backgroundColor: colors.scrim },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.xs,
  },
  grabber: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
    marginBottom: spacing.md,
  },
});
```

- [ ] **Step 2: Build the fullscreen login route**

Create `mobile/src/app/auth/login.tsx`:
```tsx
import { View, Pressable, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { LoginCard } from "@/features/auth/components/LoginCard";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { colors, spacing } from "@/constants/theme";

export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const devLogin = useAuthStore((s) => s.devLogin);

  const close = () => {
    if (router.canGoBack()) router.back();
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={close} hitSlop={8}>
        <Icon name="chevron-left" size={24} />
      </Pressable>
      <LoginCard variant="full" onSuccess={close} />
      {__DEV__ ? (
        <Pressable
          style={[styles.dev, { bottom: insets.bottom + spacing.sm }]}
          onPress={() => {
            devLogin();
            close();
          }}
        >
          <Text style={styles.devText}>개발용 로그인 (DEV)</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  back: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  dev: { position: "absolute", alignSelf: "center" },
  devText: { color: colors.ter, fontSize: 12, fontWeight: "700", textDecorationLine: "underline" },
});
```

- [ ] **Step 3: Register routes + mount the sheet in the root layout**

In `mobile/src/app/_layout.tsx`, add the two `Stack.Screen` entries after the `photo` screen, and mount `<AuthPromptSheet/>` inside `<SafeAreaProvider>` (sibling of `<Stack>`):
```tsx
import { AuthPromptSheet } from "@/features/auth/components/AuthPromptSheet";
```
```tsx
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="curations/[slug]" />
          <Stack.Screen name="spots/[contentId]" />
          <Stack.Screen name="photo" options={{ presentation: "modal" }} />
          <Stack.Screen name="auth/login" options={{ presentation: "fullScreenModal" }} />
          <Stack.Screen name="saved" />
        </Stack>
        <AuthPromptSheet />
```
(The `saved` screen is created in Task 12; registering it now is harmless — Expo Router only renders it when navigated to. If lint complains about an unused route before Task 12, proceed; the route file lands in Task 12 of the same branch.)

- [ ] **Step 4: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/auth/components/AuthPromptSheet.tsx mobile/src/app/auth/login.tsx mobile/src/app/_layout.tsx
git commit -m "feat(mobile): login fullscreen route + nudge sheet + root wiring"
```

---

### Task 9: Saved API

**Files:**
- Create: `mobile/src/features/saved/api.ts`
- Test: `mobile/src/features/saved/__tests__/api.test.ts`

**Interfaces:**
- Consumes: `api` (`@/lib/api-client`), `SpotCard` (`@/lib/api-types`).
- Produces:
  - `listSaved(): Promise<SpotCard[]>` (single page, `limit=60`)
  - `saveSpot(contentId: string): Promise<void>`
  - `unsaveSpot(contentId: string): Promise<void>`

- [ ] **Step 1: Write the failing test**

Create `mobile/src/features/saved/__tests__/api.test.ts`:
```ts
jest.mock("@/lib/api-client", () => ({ api: { get: jest.fn(), post: jest.fn(), delete: jest.fn() } }));

import { api } from "@/lib/api-client";
import { listSaved, saveSpot, unsaveSpot } from "@/features/saved/api";

describe("saved api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("listSaved gets the saved list with limit 60", async () => {
    const cards = [{ contentId: "1", title: "a", firstImageUrl: null, category: null }];
    (api.get as jest.Mock).mockResolvedValue(cards);
    const res = await listSaved();
    expect(api.get).toHaveBeenCalledWith("/users/me/saved", { params: { limit: 60 } });
    expect(res).toBe(cards);
  });

  it("saveSpot posts to the content path", async () => {
    (api.post as jest.Mock).mockResolvedValue({});
    await saveSpot("123");
    expect(api.post).toHaveBeenCalledWith("/users/me/saved/123");
  });

  it("unsaveSpot deletes the content path", async () => {
    (api.delete as jest.Mock).mockResolvedValue(undefined);
    await unsaveSpot("123");
    expect(api.delete).toHaveBeenCalledWith("/users/me/saved/123");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/saved/__tests__/api.test.ts`
Expected: FAIL — cannot find module `api`.

- [ ] **Step 3: Write minimal implementation**

Create `mobile/src/features/saved/api.ts`:
```ts
import { api } from "@/lib/api-client";
import type { SpotCard } from "@/lib/api-types";

/** Saved spots — single page (limit 60). Pagination meta is dropped by the
 * api-client unwrap; infinite scroll is out of scope for P3 (spec §5). */
export async function listSaved(): Promise<SpotCard[]> {
  return (await api.get("/users/me/saved", { params: { limit: 60 } })) as unknown as SpotCard[];
}

/** Idempotent save (backend returns 201 new / 200 duplicate). */
export async function saveSpot(contentId: string): Promise<void> {
  await api.post(`/users/me/saved/${contentId}`);
}

/** Idempotent unsave (204). */
export async function unsaveSpot(contentId: string): Promise<void> {
  await api.delete(`/users/me/saved/${contentId}`);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/saved/__tests__/api.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/saved/api.ts mobile/src/features/saved/__tests__/api.test.ts
git commit -m "feat(mobile): saved spots api (list/save/unsave)"
```

---

### Task 10: Saved optimistic helper + queries

**Files:**
- Create: `mobile/src/features/saved/lib/optimistic.ts`
- Create: `mobile/src/features/saved/queries.ts`
- Test: `mobile/src/features/saved/lib/__tests__/optimistic.test.ts`

**Interfaces:**
- Consumes: `listSaved`/`saveSpot`/`unsaveSpot` (Task 9), `SpotCard` (`@/lib/api-types`), `useAuthStore` (Task 5), `@tanstack/react-query`.
- Produces:
  - `lib/optimistic.ts`: `removeById(list: SpotCard[], contentId: string): SpotCard[]`, `containsId(list: SpotCard[] | undefined, contentId: string): boolean`.
  - `queries.ts`: `savedKeys.list` (`["saved"]`), `useSavedList()`, `useIsSaved(contentId: string): boolean`, `useSaveMutation()`, `useUnsaveMutation()`.

> Only the pure helpers are unit-tested (no `renderHook` in this project); the hooks are gated by lint + typecheck + suite green.

- [ ] **Step 1: Write the failing test (pure helpers)**

Create `mobile/src/features/saved/lib/__tests__/optimistic.test.ts`:
```ts
import { removeById, containsId } from "@/features/saved/lib/optimistic";
import type { SpotCard } from "@/lib/api-types";

const card = (contentId: string): SpotCard => ({
  contentId,
  title: contentId,
  firstImageUrl: null,
  category: null,
});

describe("saved optimistic helpers", () => {
  const list = [card("a"), card("b"), card("c")];

  it("removeById drops the matching card and keeps order", () => {
    expect(removeById(list, "b").map((c) => c.contentId)).toEqual(["a", "c"]);
  });

  it("removeById is a no-op when absent", () => {
    expect(removeById(list, "z").map((c) => c.contentId)).toEqual(["a", "b", "c"]);
  });

  it("containsId is true only for present ids and false for undefined list", () => {
    expect(containsId(list, "a")).toBe(true);
    expect(containsId(list, "z")).toBe(false);
    expect(containsId(undefined, "a")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/features/saved/lib/__tests__/optimistic.test.ts`
Expected: FAIL — cannot find module `optimistic`.

- [ ] **Step 3: Write the helpers**

Create `mobile/src/features/saved/lib/optimistic.ts`:
```ts
import type { SpotCard } from "@/lib/api-types";

export function removeById(list: SpotCard[], contentId: string): SpotCard[] {
  return list.filter((c) => c.contentId !== contentId);
}

export function containsId(list: SpotCard[] | undefined, contentId: string): boolean {
  return !!list?.some((c) => c.contentId === contentId);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/features/saved/lib/__tests__/optimistic.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the queries**

Create `mobile/src/features/saved/queries.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { SpotCard } from "@/lib/api-types";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { listSaved, saveSpot, unsaveSpot } from "@/features/saved/api";
import { containsId, removeById } from "@/features/saved/lib/optimistic";

export const savedKeys = { list: ["saved"] as const };

/** Saved list — enabled only when authenticated (guests get []). */
export function useSavedList() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: savedKeys.list,
    queryFn: listSaved,
    enabled: isAuthenticated,
  });
}

/** Heart state for a spot, derived from the saved-list cache (spec §5 limit:
 * spots beyond the loaded page may read false until saved). */
export function useIsSaved(contentId: string): boolean {
  const { data } = useSavedList();
  return containsId(data, contentId);
}

export function useSaveMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (contentId: string) => saveSpot(contentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: savedKeys.list }),
  });
}

export function useUnsaveMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (contentId: string) => unsaveSpot(contentId),
    onMutate: async (contentId: string) => {
      await qc.cancelQueries({ queryKey: savedKeys.list });
      const prev = qc.getQueryData<SpotCard[]>(savedKeys.list);
      if (prev) qc.setQueryData<SpotCard[]>(savedKeys.list, removeById(prev, contentId));
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(savedKeys.list, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: savedKeys.list }),
  });
}
```

- [ ] **Step 6: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/saved/lib/optimistic.ts mobile/src/features/saved/queries.ts mobile/src/features/saved/lib/__tests__/optimistic.test.ts
git commit -m "feat(mobile): saved queries + optimistic unsave helpers"
```

---

### Task 11: Saved components (card, rail, empty board)

**Files:**
- Create: `mobile/src/features/saved/components/SavedCard.tsx`
- Create: `mobile/src/features/saved/components/SavedRail.tsx`
- Create: `mobile/src/features/saved/components/EmptyBoard.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green.

**Interfaces:**
- Consumes: `RemoteImage` (`@/components/RemoteImage`), `Icon`, `SpotCard` (`@/lib/api-types`), theme tokens.
- Produces:
  - `SavedCard({ spot, onPress, onUnsave })` — grid card (mockup 13).
  - `SavedRail({ spots, onPressItem })` — horizontal 96px rail (mockup 14).
  - `EmptyBoard({ text, actionLabel, actionIcon, onAction })` — bordered empty board (mockup 15).

- [ ] **Step 1: Build SavedCard**

Create `mobile/src/features/saved/components/SavedCard.tsx`:
```tsx
import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { SpotCard } from "@/lib/api-types";
import { colors, radii } from "@/constants/theme";

interface Props {
  spot: SpotCard;
  onPress: () => void;
  onUnsave: () => void;
}

export function SavedCard({ spot, onPress, onUnsave }: Props) {
  return (
    <Pressable style={styles.card} onPress={onPress}>
      <RemoteImage uri={spot.firstImageUrl} style={styles.img} />
      <View style={styles.ov} pointerEvents="none" />
      <Pressable style={styles.heart} onPress={onUnsave} hitSlop={8}>
        <Icon name="heart-fill" size={19} color={colors.onImage} />
      </Pressable>
      <Text numberOfLines={1} style={styles.name}>
        {spot.title}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { width: "48.5%", height: 150, borderRadius: radii.md, overflow: "hidden", backgroundColor: colors.inset },
  img: { width: "100%", height: "100%" },
  ov: { position: "absolute", inset: 0, backgroundColor: "transparent" },
  heart: {
    position: "absolute",
    top: 9,
    right: 9,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.control,
    alignItems: "center",
    justifyContent: "center",
  },
  name: { position: "absolute", left: 12, right: 12, bottom: 11, color: colors.onImage, fontSize: 14, fontWeight: "600" },
});
```

- [ ] **Step 2: Build SavedRail**

Create `mobile/src/features/saved/components/SavedRail.tsx`:
```tsx
import { ScrollView, Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import type { SpotCard } from "@/lib/api-types";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  spots: SpotCard[];
  onPressItem: (contentId: string) => void;
}

export function SavedRail({ spots, onPressItem }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.rail}
    >
      {spots.map((s) => (
        <Pressable key={s.contentId} style={styles.item} onPress={() => onPressItem(s.contentId)}>
          <View style={styles.imgWrap}>
            <RemoteImage uri={s.firstImageUrl} style={styles.img} />
          </View>
          <Text numberOfLines={1} style={styles.name}>
            {s.title}
          </Text>
          {s.category ? (
            <Text numberOfLines={1} style={styles.cat}>
              {s.category}
            </Text>
          ) : null}
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  rail: { gap: 12, paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  item: { width: 96 },
  imgWrap: { width: 96, height: 96, borderRadius: radii.md, overflow: "hidden", backgroundColor: colors.inset },
  img: { width: "100%", height: "100%" },
  name: { fontSize: 12.5, fontWeight: "600", marginTop: 7, color: colors.ink },
  cat: { fontSize: 11.5, color: colors.ter, marginTop: 2 },
});
```

- [ ] **Step 3: Build EmptyBoard**

Create `mobile/src/features/saved/components/EmptyBoard.tsx`:
```tsx
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Icon, type IconName } from "@/components/Icon";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  text: string;
  actionLabel: string;
  actionIcon: IconName;
  onAction: () => void;
}

export function EmptyBoard({ text, actionLabel, actionIcon, onAction }: Props) {
  return (
    <View style={styles.board}>
      <Text style={styles.text}>{text}</Text>
      <Pressable style={styles.btn} onPress={onAction}>
        <Icon name={actionIcon} size={15} color={colors.ink} />
        <Text style={styles.btnText}>{actionLabel}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  board: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.md,
    paddingVertical: 30,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.bg,
  },
  text: { color: colors.ter, fontSize: 14 },
  btn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 38,
    paddingHorizontal: 18,
    borderRadius: radii.pill,
    backgroundColor: colors.fill,
  },
  btnText: { fontSize: 13.5, fontWeight: "700", color: colors.ink },
});
```

- [ ] **Step 4: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/saved/components/
git commit -m "feat(mobile): saved components (grid card, rail, empty board)"
```

---

### Task 12: Saved grid screen (13)

**Files:**
- Create: `mobile/src/app/saved.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: `useSavedList`/`useUnsaveMutation` (Task 10), `SavedCard` (Task 11), `Skeleton`, `Icon`, theme tokens, `expo-router`.
- Produces: route `/saved` (back nav, no tab bar) — mockup 13.

- [ ] **Step 1: Build the saved grid screen**

Create `mobile/src/app/saved.tsx`:
```tsx
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { Skeleton } from "@/components/Skeleton";
import { SavedCard } from "@/features/saved/components/SavedCard";
import { useSavedList, useUnsaveMutation } from "@/features/saved/queries";
import { colors, spacing } from "@/constants/theme";

export default function SavedScreen() {
  const insets = useSafeAreaInsets();
  const { data, isLoading } = useSavedList();
  const unsave = useUnsaveMutation();

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>스크랩</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.grid}>
        {isLoading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} height={150} width="48.5%" radius={14} />)
        ) : data && data.length > 0 ? (
          data.map((spot) => (
            <SavedCard
              key={spot.contentId}
              spot={spot}
              onPress={() => router.push(`/spots/${spot.contentId}`)}
              onUnsave={() => unsave.mutate(spot.contentId)}
            />
          ))
        ) : (
          <Text style={styles.empty}>아직 스크랩한 곳이 없어요</Text>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  navBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  title: { position: "absolute", left: 0, right: 0, textAlign: "center", fontSize: 17, fontWeight: "700", color: colors.ink },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    rowGap: 12,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xxl,
  },
  empty: { width: "100%", textAlign: "center", color: colors.ter, fontSize: 14, marginTop: spacing.xxl },
});
```

> Verify `Skeleton` accepts a `radius` prop; if not, drop it (the loading blocks just won't be rounded). Check `mobile/src/components/Skeleton.tsx` before implementing.

- [ ] **Step 2: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/app/saved.tsx
git commit -m "feat(mobile): 13 saved grid screen"
```

---

### Task 13: Wire the spot-detail SAVE toggle

**Files:**
- Modify: `mobile/src/app/spots/[contentId].tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: `useAuthGate` (Task 6), `useIsSaved`/`useSaveMutation`/`useUnsaveMutation` (Task 10).

- [ ] **Step 1: Replace the inert save button**

In `mobile/src/app/spots/[contentId].tsx`:

Add imports (after the existing feature imports):
```tsx
import { useState } from "react";
import { useAuthGate } from "@/features/auth/hooks/use-auth-gate";
import { useIsSaved, useSaveMutation, useUnsaveMutation } from "@/features/saved/queries";
```

Inside `SpotScreen`, after the existing hooks (`const { width } = useWindowDimensions();`):
```tsx
  const requireAuth = useAuthGate();
  const persisted = useIsSaved(contentId);
  const [optimistic, setOptimistic] = useState<boolean | null>(null);
  const saved = optimistic ?? persisted;
  const saveMut = useSaveMutation();
  const unsaveMut = useUnsaveMutation();

  const onToggleSave = async () => {
    if (!(await requireAuth("save"))) return;
    const next = !saved;
    setOptimistic(next);
    const rollback = () => setOptimistic(!next);
    if (next) saveMut.mutate(contentId, { onError: rollback });
    else unsaveMut.mutate(contentId, { onError: rollback });
  };
```

Replace the inert save button block:
```tsx
      {/* Save is inert until P3 (auth + POST /users/me/saved). */}
      <Pressable style={[styles.navBtn, styles.save]} hitSlop={8} onPress={() => {}}>
        <Icon name="heart" size={20} color={colors.onImage} />
      </Pressable>
```
with:
```tsx
      <Pressable style={[styles.navBtn, styles.save]} hitSlop={8} onPress={onToggleSave}>
        <Icon name={saved ? "heart-fill" : "heart"} size={20} color={colors.onImage} />
      </Pressable>
```

- [ ] **Step 2: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add "mobile/src/app/spots/[contentId].tsx"
git commit -m "feat(mobile): wire spot-detail save toggle (auth gate + optimistic)"
```

---

### Task 14: Profile components + 14/15 screen rewrite

**Files:**
- Create: `mobile/src/features/profile/components/ProfileHeader.tsx`
- Create: `mobile/src/features/profile/components/GuestLoginRow.tsx`
- Create: `mobile/src/features/profile/components/SettingsRows.tsx`
- Modify: `mobile/src/app/(tabs)/profile.tsx`

> Not unit-tested; gate = lint + typecheck + format + suite green + manual smoke.

**Interfaces:**
- Consumes: `useAuthStore` (Task 5), `useSavedList` (Task 10), `SavedRail`/`EmptyBoard` (Task 11), `RemoteImage`, `Icon`, `APP_VERSION` (`@/lib/app-meta`), theme tokens, `expo-router`, `Linking`, `Alert`.
- Produces: profile components + the 3-variant `ProfileTab`.

- [ ] **Step 1: Build ProfileHeader**

Create `mobile/src/features/profile/components/ProfileHeader.tsx`:
```tsx
import { View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { User } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

export function ProfileHeader({ user }: { user: User }) {
  return (
    <View style={styles.row}>
      <View style={styles.avatar}>
        {user.avatarUrl ? (
          <RemoteImage uri={user.avatarUrl} style={styles.avatarImg} />
        ) : (
          <Icon name="person" size={30} color={colors.ter} />
        )}
      </View>
      <View>
        <Text style={styles.name}>{user.displayName ?? "여행자"}</Text>
        {user.email ? <Text style={styles.email}>{user.email}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 14, padding: spacing.lg, backgroundColor: colors.bg },
  avatar: {
    width: 62,
    height: 62,
    borderRadius: 31,
    overflow: "hidden",
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarImg: { width: "100%", height: "100%" },
  name: { fontSize: 19, fontWeight: "700", letterSpacing: -0.19, color: colors.ink },
  email: { color: colors.sec, fontSize: 13.5, marginTop: 3 },
});
```

- [ ] **Step 2: Build GuestLoginRow**

Create `mobile/src/features/profile/components/GuestLoginRow.tsx`:
```tsx
import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

export function GuestLoginRow({ onPress }: { onPress: () => void }) {
  return (
    <Pressable style={styles.row} onPress={onPress}>
      <View style={styles.avatar}>
        <Icon name="person" size={26} color={colors.ink} />
      </View>
      <View style={styles.tx}>
        <Text style={styles.title}>로그인하기</Text>
        <Text style={styles.sub}>나만의 여행지를 스크랩해 보세요</Text>
      </View>
      <Icon name="chevron-right" size={20} color={colors.ter} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 22, paddingHorizontal: spacing.lg, backgroundColor: colors.bg },
  avatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
  },
  tx: { flex: 1 },
  title: { fontSize: 18, fontWeight: "700", letterSpacing: -0.18, color: colors.ink },
  sub: { color: colors.sec, fontSize: 13, marginTop: 3 },
});
```

- [ ] **Step 3: Build SettingsRows**

Create `mobile/src/features/profile/components/SettingsRows.tsx`:
```tsx
import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { APP_VERSION } from "@/lib/app-meta";
import { colors, spacing } from "@/constants/theme";

export function SettingsRows({ onLogout }: { onLogout?: () => void }) {
  return (
    <View style={styles.group}>
      <Pressable style={[styles.row, styles.first]} onPress={() => Linking.openSettings()}>
        <View style={styles.icon}>
          <Icon name="map-pin" size={21} color={colors.sec} />
        </View>
        <Text style={styles.label}>위치 권한</Text>
        <Icon name="chevron-right" size={20} color={colors.ter} />
      </Pressable>

      <View style={styles.row}>
        <View style={styles.icon}>
          <Icon name="info" size={21} color={colors.sec} />
        </View>
        <Text style={styles.label}>앱 버전</Text>
        <Text style={styles.value}>{APP_VERSION}</Text>
      </View>

      {onLogout ? (
        <Pressable style={styles.row} onPress={onLogout}>
          <View style={styles.icon}>
            <Icon name="log-out" size={21} color={colors.sec} />
          </View>
          <Text style={styles.label}>로그아웃</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  group: { backgroundColor: colors.bg },
  row: { flexDirection: "row", alignItems: "center", gap: 13, paddingVertical: 16, paddingHorizontal: spacing.lg, borderTopWidth: 1, borderTopColor: colors.line },
  first: { borderTopWidth: 0 },
  icon: { width: 21, alignItems: "center" },
  label: { flex: 1, fontSize: 15.5, fontWeight: "600", color: colors.ink },
  value: { color: colors.ter, fontSize: 14 },
});
```

- [ ] **Step 4: Rewrite the profile tab (3 variants)**

Replace `mobile/src/app/(tabs)/profile.tsx` entirely:
```tsx
import { View, Text, Pressable, ScrollView, Alert, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { useSavedList } from "@/features/saved/queries";
import { SavedRail } from "@/features/saved/components/SavedRail";
import { EmptyBoard } from "@/features/saved/components/EmptyBoard";
import { ProfileHeader } from "@/features/profile/components/ProfileHeader";
import { GuestLoginRow } from "@/features/profile/components/GuestLoginRow";
import { SettingsRows } from "@/features/profile/components/SettingsRows";
import { colors, spacing } from "@/constants/theme";

export default function ProfileTab() {
  const insets = useSafeAreaInsets();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const deleteAccount = useAuthStore((s) => s.deleteAccount);
  const { data: saved } = useSavedList();

  const confirmDelete = () =>
    Alert.alert("회원 탈퇴", "탈퇴하면 스크랩과 계정 정보가 삭제돼요. 계속할까요?", [
      { text: "취소", style: "cancel" },
      { text: "탈퇴", style: "destructive", onPress: () => void deleteAccount() },
    ]);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Text style={styles.navTitle}>마이</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {isAuthenticated && user ? (
          <ProfileHeader user={user} />
        ) : (
          <GuestLoginRow onPress={() => router.push("/auth/login")} />
        )}

        <View style={styles.sep} />

        <View style={styles.scrapWrap}>
          <View style={styles.secHead}>
            <Text style={styles.secTitle}>스크랩</Text>
            {isAuthenticated && saved && saved.length > 0 ? (
              <Pressable style={styles.seeAll} onPress={() => router.push("/saved")}>
                <Text style={styles.seeAllText}>전체보기</Text>
                <Icon name="chevron-right" size={15} color={colors.sec} />
              </Pressable>
            ) : null}
          </View>

          {isAuthenticated ? (
            saved && saved.length > 0 ? (
              <SavedRail spots={saved} onPressItem={(id) => router.push(`/spots/${id}`)} />
            ) : (
              <EmptyBoard
                text="아직 스크랩한 곳이 없어요"
                actionLabel="둘러보러 가기"
                actionIcon="home"
                onAction={() => router.push("/(tabs)")}
              />
            )
          ) : (
            <EmptyBoard
              text="로그인하고 마음에 든 곳을 스크랩하세요"
              actionLabel="로그인하기"
              actionIcon="log-in"
              onAction={() => router.push("/auth/login")}
            />
          )}
        </View>

        <View style={styles.sep} />

        <SettingsRows onLogout={isAuthenticated ? () => void logout() : undefined} />

        <View style={styles.foot}>
          <Text style={styles.footLink}>약관·정책</Text>
          {isAuthenticated ? (
            <>
              <View style={styles.footDiv} />
              <Pressable onPress={confirmDelete}>
                <Text style={styles.footLink}>회원 탈퇴</Text>
              </Pressable>
            </>
          ) : null}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  nav: { height: 50, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  navTitle: { fontSize: 17, fontWeight: "700", color: colors.ink },
  sep: { height: 9, backgroundColor: colors.inset },
  scrapWrap: { backgroundColor: colors.bg, paddingBottom: 2 },
  secHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: 11 },
  secTitle: { fontSize: 18, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  seeAll: { flexDirection: "row", alignItems: "center", gap: 3 },
  seeAllText: { color: colors.sec, fontSize: 13.5, fontWeight: "600" },
  foot: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 16, paddingVertical: 24, paddingBottom: 30 },
  footLink: { color: colors.sec, fontSize: 13, fontWeight: "600" },
  footDiv: { width: 1, height: 12, backgroundColor: colors.line },
});
```

- [ ] **Step 5: Verify and commit**

```bash
npm run lint && npm run typecheck && npm run format:check && npm test
```
Expected: all green.
```bash
git add mobile/src/features/profile/ "mobile/src/app/(tabs)/profile.tsx"
git commit -m "feat(mobile): 14/15 profile (login/guest/empty) + logout + withdraw"
```

---

## Manual smoke checklist (after Task 14)

Run `npm start` (or dev client). With `__DEV__` dev login:
- [ ] 마이 탭(게스트) → 로그인 행 + 스크랩 빈 보드 + 약관·정책(로그아웃/탈퇴 없음).
- [ ] 게스트 스팟 상세 하트 탭 → 넛지 시트 등장 → dev 로그인 → 시트 닫히고 하트 채워짐(보류 액션 재개).
- [ ] 마이 탭(로그인/dev) → 헤더 + 스크랩 빈 보드 "둘러보러 가기" + 위치권한/앱버전/로그아웃 + 약관·정책 | 회원탈퇴.
- [ ] 스팟 저장 후 마이 → 스크랩 레일 + 전체보기 → 13 그리드 → 하트 탭 unsave(낙관적 제거) → back.
- [ ] 로그아웃 → 게스트 변형 복귀. 회원탈퇴 Alert → 탈퇴 → 게스트.
- [ ] 풀스크린 로그인(마이 로그인 행) 백 버튼 → 마이 복귀.

> 실 OAuth(카카오·구글·애플) end-to-end는 `EXPO_PUBLIC_*` 자격증명 주입 후 별도 확인(spec §11 콘솔 체크리스트).

## Self-review notes (coverage vs spec)

- §1 범위: 로그인(T7–8) · OAuth 3종(T3) · SAVE 토글(T13) · 13 그리드(T12) · 14/15 마이(T14) · 로그아웃/탈퇴(T5/T14) · consent 기록(T4) · 승격(T6/T13) · 401 분기(T13 게이트 + 기존 api-client). ✓
- §1.2 제외: 법적고지/granular consent 미포함(약관 링크 inert) — 본 플랜에 태스크 없음(의도적). ✓
- §4.3 dev: `devLogin`(T5) + DEV 진입점(T8). ✓
- §5 저장 한계(페이지네이션) 및 단일 페이지 결정: T9/T10에 명시. ✓
- §9 의존성: T1 `expo install`. ✓
- §10 테스트: 순수 로직 TDD(T2–6,9,10) + 화면 게이트. ✓
- 타입 일관성: `Provider`/`OAuthOutcome`(T3) → auth-store(T5)/LoginCard(T7); `savedKeys.list`/`useIsSaved`/mutations(T10) → spot detail(T13)/profile(T14); `SpotCard`(기존) 재사용. ✓
