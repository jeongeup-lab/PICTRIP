# Mobile P5 — 법적고지 · 동의 관리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the final mobile screens — legal-document viewer (16), wire the two
inert legal links, and a consent-management screen backed by a new minimal
`GET /users/me/consents` — closing the last mockup and the P3→P5 consent carryover.

**Architecture:** `features/legal/` (constants + WebView wrapper) drives two thin
Expo Router screens (`app/legal/index.tsx`, `app/legal/[slug].tsx`) pointing at
`https://pictrip.org/legal/{slug}`. `features/consent/` (types/api/queries + a pure
merge helper) backs `app/consent.tsx`, reading real server state via a new backend
`GET /users/me/consents` and writing via the existing `PUT`. P3's `record-consent`
is fixed to merge (preserve `photoConsent`) instead of clobbering it.

**Tech Stack:** Expo SDK 56 · RN 0.85 · React 19.2 · TypeScript strict · Expo Router
(typed routes) · TanStack Query · axios · `react-native-webview` · `expo-web-browser`
· `expo-location` (all existing deps). Backend: FastAPI · SQLAlchemy 2.0 async · pytest.

## Global Constraints

- **Monochrome only** — ink/gray from `@/constants/theme`; no rose, no color. No emoji.
- **No new native modules** — `react-native-webview`, `expo-web-browser`, `expo-location`,
  `expo-constants` are already in `mobile/package.json`. Map stays KakaoWebMap (untouched here).
- **No `as any`.** TypeScript strict.
- **JSend unwrapped once** by `@/lib/api-client` (`api.get`/`api.put` return `data`); never double-unwrap.
- **Errors branch on `err.code`** (`AppError`), never `err.message`.
- **File naming:** components PascalCase; runtime modules (api/lib/queries/constants/types) kebab-case;
  `src/app/**` follows Expo Router.
- **Copy SSOT** = mockup `16-legal.html` verbatim for the 4 doc labels: 이용약관 / 개인정보처리방침 /
  위치기반서비스 이용약관 / 데이터 출처. `TERMS_VERSION` lives in `@/constants/legal`.
- **Mobile verify:** `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`.
- **Backend verify:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && POSTGRES_DB=pictrip_test uv run pytest`.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/modules/users/schemas.py` (mod) | add `ConsentState` DTO (nullable terms/consentedAt) |
| `backend/app/modules/users/services.py` (mod) | add `get_consents()` |
| `backend/app/modules/users/routes.py` (mod) | add `GET /users/me/consents` |
| `backend/tests/test_consents.py` (mod) | add GET tests (row / no-row / 401) |
| `mobile/src/features/legal/constants.ts` (new) | `LEGAL_DOCS`, `legalUrl`, `findLegalDoc` |
| `mobile/src/features/legal/components/LegalWebView.tsx` (new) | WebView + loading/error/browser-fallback |
| `mobile/src/app/legal/index.tsx` (new) | 4-row legal list (mockup 16) |
| `mobile/src/app/legal/[slug].tsx` (new) | document WebView screen |
| `mobile/src/features/consent/types.ts` (new) | `ConsentState` type |
| `mobile/src/features/consent/api.ts` (new) | `getConsents`, `putConsents` |
| `mobile/src/features/consent/lib/build-consent-put.ts` (new) | pure merge helper |
| `mobile/src/features/consent/queries.ts` (new) | `useConsents`, `useUpdateConsent` |
| `mobile/src/app/consent.tsx` (new) | consent-management screen |
| `mobile/src/components/Icon.tsx` (mod) | add `shield-check` line-SVG |
| `mobile/src/features/profile/components/SettingsRows.tsx` (mod) | `동의 관리` row (authed) |
| `mobile/src/app/(tabs)/profile.tsx` (mod) | footer `약관·정책` → push `/legal` |
| `mobile/src/features/auth/components/LoginCard.tsx` (mod) | tappable terms/privacy links |
| `mobile/src/features/auth/usecases/record-consent.ts` (mod) | merge (preserve photoConsent) |
| `mobile/src/app/_layout.tsx` (mod) | register `legal/index`, `legal/[slug]`, `consent` |

---

## Task 1: Backend `GET /users/me/consents`

**Files:**
- Modify: `backend/app/modules/users/schemas.py`
- Modify: `backend/app/modules/users/services.py`
- Modify: `backend/app/modules/users/routes.py`
- Test: `backend/tests/test_consents.py`

**Interfaces:**
- Produces: `GET /v1/users/me/consents` → JSend `data = { locationConsent: bool, photoConsent: bool, termsVersion: str | null, consentedAt: str | null }`. No row → all defaults (`false/false/null/null`).

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/test_consents.py`:

```python
async def test_get_consents_returns_defaults_when_no_row(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)

    resp = await client.get("/v1/users/me/consents", headers=_auth(uid))

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data == {
        "locationConsent": False,
        "photoConsent": False,
        "termsVersion": None,
        "consentedAt": None,
    }


async def test_get_consents_echoes_persisted_row(
    client: AsyncClient, override_db_and_seed: AsyncSession
) -> None:
    uid = await _seed_user(override_db_and_seed)
    await client.put(
        "/v1/users/me/consents",
        headers=_auth(uid),
        json={"locationConsent": True, "photoConsent": True, "termsVersion": "v9.0"},
    )

    resp = await client.get("/v1/users/me/consents", headers=_auth(uid))

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["locationConsent"] is True
    assert data["photoConsent"] is True
    assert data["termsVersion"] == "v9.0"
    assert data["consentedAt"] is not None


async def test_get_consents_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/v1/users/me/consents")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_INVALID"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && POSTGRES_DB=pictrip_test uv run pytest tests/test_consents.py -k get_consents -v`
Expected: FAIL — route returns 405 / not found (GET not defined).

- [ ] **Step 3: Add `ConsentState` schema** — append to `backend/app/modules/users/schemas.py`:

```python
class ConsentState(BaseModel):
    """Current consent state for GET /users/me/consents (defaults when no row)."""

    locationConsent: bool = False
    photoConsent: bool = False
    termsVersion: str | None = None
    consentedAt: datetime | None = None
```

- [ ] **Step 4: Add `get_consents` service** — in `backend/app/modules/users/services.py`, add `ConsentState` to the schema import line and append after `put_consents`:

```python
async def get_consents(session: AsyncSession, user_id: int) -> ConsentState:
    """Read the user's consent row; return all-default state when none exists."""
    row = await session.get(UserConsent, user_id)
    if row is None:
        return ConsentState()
    return ConsentState(
        locationConsent=row.location_consent,
        photoConsent=row.photo_consent,
        termsVersion=row.terms_version,
        consentedAt=row.consented_at,
    )
```

(Update the import: `from app.modules.users.schemas import ConsentIn, ConsentOut, ConsentState, OAuthLoginIn, TokenPair, UserPublic`.)

- [ ] **Step 5: Add the route** — in `backend/app/modules/users/routes.py`, add a GET above the existing `put_consents` route:

```python
@router.get(
    "/users/me/consents",
    status_code=status.HTTP_200_OK,
    summary="My current consent state (location/photo/terms)",
)
async def get_consents(
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    state = await services.get_consents(session, user_id)
    return ok(state.model_dump())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && POSTGRES_DB=pictrip_test uv run pytest tests/test_consents.py -v`
Expected: PASS (all consent tests, old + 3 new).

- [ ] **Step 7: Full backend gate**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && POSTGRES_DB=pictrip_test uv run pytest`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/users/schemas.py backend/app/modules/users/services.py backend/app/modules/users/routes.py backend/tests/test_consents.py
git commit -m "feat(backend): GET /users/me/consents (current consent state)"
```

---

## Task 2: Legal constants

**Files:**
- Create: `mobile/src/features/legal/constants.ts`
- Test: `mobile/src/features/legal/__tests__/constants.test.ts`

**Interfaces:**
- Produces: `type LegalSlug`, `LEGAL_DOCS: readonly LegalDoc[]`, `legalUrl(slug): string`, `findLegalDoc(slug: string): LegalDoc | undefined`.

- [ ] **Step 1: Write the failing test** — `mobile/src/features/legal/__tests__/constants.test.ts`:

```ts
import { LEGAL_DOCS, legalUrl, findLegalDoc } from "@/features/legal/constants";

describe("legal constants", () => {
  it("lists the 4 documents in mockup order with verbatim labels", () => {
    expect(LEGAL_DOCS.map((d) => d.slug)).toEqual([
      "terms",
      "privacy",
      "location",
      "data-sources",
    ]);
    expect(LEGAL_DOCS.map((d) => d.title)).toEqual([
      "이용약관",
      "개인정보처리방침",
      "위치기반서비스 이용약관",
      "데이터 출처",
    ]);
  });

  it("legalUrl builds the hosted page URL", () => {
    expect(legalUrl("terms")).toBe("https://pictrip.org/legal/terms");
    expect(legalUrl("data-sources")).toBe("https://pictrip.org/legal/data-sources");
  });

  it("findLegalDoc resolves a known slug and returns undefined for unknown", () => {
    expect(findLegalDoc("privacy")?.title).toBe("개인정보처리방침");
    expect(findLegalDoc("nope")).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npm test -- legal/__tests__/constants`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation** — `mobile/src/features/legal/constants.ts`:

```ts
/** Legal documents (mockup 16). Bodies are hosted static pages (S06 D1);
 * the app only routes to them. Labels are mockup-verbatim. */
export type LegalSlug = "terms" | "privacy" | "location" | "data-sources";

export interface LegalDoc {
  slug: LegalSlug;
  title: string;
}

export const LEGAL_DOCS: readonly LegalDoc[] = [
  { slug: "terms", title: "이용약관" },
  { slug: "privacy", title: "개인정보처리방침" },
  { slug: "location", title: "위치기반서비스 이용약관" },
  { slug: "data-sources", title: "데이터 출처" },
] as const;

export const LEGAL_BASE_URL = "https://pictrip.org/legal";

export function legalUrl(slug: LegalSlug): string {
  return `${LEGAL_BASE_URL}/${slug}`;
}

export function findLegalDoc(slug: string): LegalDoc | undefined {
  return LEGAL_DOCS.find((d) => d.slug === slug);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mobile && npm test -- legal/__tests__/constants`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/legal/constants.ts mobile/src/features/legal/__tests__/constants.test.ts
git commit -m "feat(mobile): legal document constants (16)"
```

---

## Task 3: Legal screens (list + WebView)

**Files:**
- Create: `mobile/src/features/legal/components/LegalWebView.tsx`
- Create: `mobile/src/app/legal/index.tsx`
- Create: `mobile/src/app/legal/[slug].tsx`
- Modify: `mobile/src/app/_layout.tsx`

**Interfaces:**
- Consumes: `LEGAL_DOCS`, `legalUrl`, `findLegalDoc`, `LegalSlug` (Task 2); `Icon` (`@/components/Icon`); `colors`, `spacing` (`@/constants/theme`).
- Produces: routes `/legal` (list) and `/legal/{slug}` (document).

- [ ] **Step 1: Write `LegalWebView`** — `mobile/src/features/legal/components/LegalWebView.tsx`:

```tsx
import { useRef, useState } from "react";
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from "react-native";
import { WebView, type WebViewNavigation } from "react-native-webview";
import * as WebBrowser from "expo-web-browser";
import { colors, spacing } from "@/constants/theme";
import { LEGAL_BASE_URL } from "@/features/legal/constants";

/** In-app document viewer (S06 D1/D3). Loads only pictrip.org/legal/* in the
 * WebView; any other navigation opens in the system browser. On load failure,
 * offers retry + open-in-browser. */
export function LegalWebView({ url }: { url: string }) {
  const ref = useRef<WebView>(null);
  const [loading, setLoading] = useState(true);
  const [errored, setErrored] = useState(false);

  const retry = () => {
    setErrored(false);
    setLoading(true);
    ref.current?.reload();
  };

  const onShouldStart = (req: WebViewNavigation): boolean => {
    if (req.url.startsWith(LEGAL_BASE_URL)) return true;
    void WebBrowser.openBrowserAsync(req.url);
    return false;
  };

  if (errored) {
    return (
      <View style={styles.center}>
        <Text style={styles.errText}>불러오지 못했어요</Text>
        <View style={styles.errActions}>
          <Pressable style={styles.btn} onPress={retry} hitSlop={8}>
            <Text style={styles.btnText}>재시도</Text>
          </Pressable>
          <Pressable
            style={styles.btn}
            onPress={() => void WebBrowser.openBrowserAsync(url)}
            hitSlop={8}
          >
            <Text style={styles.btnText}>브라우저로 열기</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.fill}>
      <WebView
        ref={ref}
        source={{ uri: url }}
        originWhitelist={[`${LEGAL_BASE_URL}/*`]}
        onShouldStartLoadWithRequest={onShouldStart}
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        onError={() => {
          setLoading(false);
          setErrored(true);
        }}
        onHttpError={() => {
          setLoading(false);
          setErrored(true);
        }}
      />
      {loading ? (
        <View style={styles.loadingOverlay} pointerEvents="none">
          <ActivityIndicator color={colors.sec} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.bg },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
    gap: spacing.lg,
  },
  errText: { fontSize: 15, color: colors.sec, fontWeight: "600" },
  errActions: { flexDirection: "row", gap: spacing.md },
  btn: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.line,
  },
  btnText: { fontSize: 14, color: colors.ink, fontWeight: "600" },
});
```

- [ ] **Step 2: Write the list screen** — `mobile/src/app/legal/index.tsx` (mockup 16, `saved.tsx` nav pattern):

```tsx
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { LEGAL_DOCS } from "@/features/legal/constants";
import { colors, spacing } from "@/constants/theme";

export default function LegalListScreen() {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>약관·정책</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.group}>
          {LEGAL_DOCS.map((doc) => (
            <Pressable
              key={doc.slug}
              style={styles.row}
              onPress={() => router.push(`/legal/${doc.slug}`)}
            >
              <Text style={styles.rowLabel}>{doc.title}</Text>
              <Icon name="chevron-right" size={20} color={colors.ter} />
            </Pressable>
          ))}
        </View>
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
  title: {
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  group: { backgroundColor: colors.bg, marginTop: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 17,
    paddingHorizontal: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  rowLabel: { flex: 1, fontSize: 15.5, fontWeight: "600", color: colors.ink },
});
```

- [ ] **Step 3: Write the document screen** — `mobile/src/app/legal/[slug].tsx`:

```tsx
import { View, Text, Pressable, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { Icon } from "@/components/Icon";
import { LegalWebView } from "@/features/legal/components/LegalWebView";
import { findLegalDoc, legalUrl } from "@/features/legal/constants";
import { colors } from "@/constants/theme";

export default function LegalDocScreen() {
  const insets = useSafeAreaInsets();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const doc = findLegalDoc(slug ?? "");

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title} numberOfLines={1}>
          {doc?.title ?? "약관·정책"}
        </Text>
      </View>
      {doc ? (
        <LegalWebView url={legalUrl(doc.slug)} />
      ) : (
        <View style={styles.missing}>
          <Text style={styles.missingText}>문서를 찾을 수 없어요</Text>
        </View>
      )}
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
  title: {
    position: "absolute",
    left: 44,
    right: 44,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  missing: { flex: 1, alignItems: "center", justifyContent: "center" },
  missingText: { fontSize: 15, color: colors.sec, fontWeight: "600" },
});
```

- [ ] **Step 4: Register routes** — in `mobile/src/app/_layout.tsx`, add inside `<Stack>` after the `saved` screen:

```tsx
        <Stack.Screen name="legal/index" />
        <Stack.Screen name="legal/[slug]" />
```

- [ ] **Step 5: Run the gate**

Run: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`
Expected: all green (typed routes `/legal`, `/legal/${string}` resolve; no test regressions).

- [ ] **Step 6: Commit**

```bash
git add mobile/src/features/legal mobile/src/app/legal mobile/src/app/_layout.tsx
git commit -m "feat(mobile): legal list + in-app document WebView (16)"
```

---

## Task 4: Wire the two inert legal links (Deliverable B)

**Files:**
- Modify: `mobile/src/app/(tabs)/profile.tsx`
- Modify: `mobile/src/features/auth/components/LoginCard.tsx`

**Interfaces:**
- Consumes: routes `/legal`, `/legal/terms`, `/legal/privacy` (Task 3).

- [ ] **Step 1: Profile footer link** — in `mobile/src/app/(tabs)/profile.tsx`, replace the plain footer label:

```tsx
          <Text style={styles.footLink}>약관·정책</Text>
```
with:
```tsx
          <Pressable onPress={() => router.push("/legal")}>
            <Text style={styles.footLink}>약관·정책</Text>
          </Pressable>
```
(`router` and `Pressable` are already imported in this file.)

- [ ] **Step 2: LoginCard tappable terms/privacy** — in `mobile/src/features/auth/components/LoginCard.tsx`, add `router` import at top:

```tsx
import { router } from "expo-router";
```
Replace the terms `<Text>` block:
```tsx
      <Text style={styles.terms}>
        계속 진행하면 이용약관 및 개인정보처리방침에{"\n"}동의하는 것으로 간주돼요.
      </Text>
```
with:
```tsx
      <Text style={styles.terms}>
        계속 진행하면{" "}
        <Text style={styles.termsLink} onPress={() => router.push("/legal/terms")}>
          이용약관
        </Text>{" "}
        및{"\n"}
        <Text style={styles.termsLink} onPress={() => router.push("/legal/privacy")}>
          개인정보처리방침
        </Text>
        에 동의하는 것으로 간주돼요.
      </Text>
```
Add to the `StyleSheet.create({ ... })` block:
```tsx
  termsLink: { color: colors.sec, fontWeight: "700", textDecorationLine: "underline" },
```

- [ ] **Step 3: Run the gate**

Run: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add "mobile/src/app/(tabs)/profile.tsx" mobile/src/features/auth/components/LoginCard.tsx
git commit -m "feat(mobile): wire profile + login-card legal links to /legal (B)"
```

---

## Task 5: Consent feature module (types/api/queries + merge helper)

**Files:**
- Create: `mobile/src/features/consent/types.ts`
- Create: `mobile/src/features/consent/api.ts`
- Create: `mobile/src/features/consent/lib/build-consent-put.ts`
- Create: `mobile/src/features/consent/queries.ts`
- Test: `mobile/src/features/consent/lib/__tests__/build-consent-put.test.ts`

**Interfaces:**
- Consumes: `api` (`@/lib/api-client`), `TERMS_VERSION` (`@/constants/legal`), `useAuthStore` (`@/features/auth/stores/auth-store`).
- Produces: `type ConsentState`; `getConsents(): Promise<ConsentState>`; `putConsents(body: ConsentPutBody): Promise<ConsentState>`; `buildConsentPut(current, osGranted, termsVersion): ConsentPutBody`; `consentKeys`; `useConsents()`; `useUpdateConsent()`.

- [ ] **Step 1: Write the failing test** — `mobile/src/features/consent/lib/__tests__/build-consent-put.test.ts`:

```ts
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";
import type { ConsentState } from "@/features/consent/types";

const state = (over: Partial<ConsentState> = {}): ConsentState => ({
  locationConsent: false,
  photoConsent: false,
  termsVersion: null,
  consentedAt: null,
  ...over,
});

describe("buildConsentPut", () => {
  it("uses the live OS grant for location and the given terms version", () => {
    expect(buildConsentPut(state(), true, "2026-06-22")).toEqual({
      locationConsent: true,
      photoConsent: false,
      termsVersion: "2026-06-22",
    });
  });

  it("preserves the current photoConsent (no clobber)", () => {
    expect(
      buildConsentPut(state({ photoConsent: true }), false, "2026-06-22").photoConsent,
    ).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npm test -- consent/lib`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `types.ts`** — `mobile/src/features/consent/types.ts`:

```ts
/** Mirror of backend ConsentState (GET /users/me/consents). */
export interface ConsentState {
  locationConsent: boolean;
  photoConsent: boolean;
  termsVersion: string | null;
  consentedAt: string | null;
}

/** Body for PUT /users/me/consents (all three fields required). */
export interface ConsentPutBody {
  locationConsent: boolean;
  photoConsent: boolean;
  termsVersion: string;
}
```

- [ ] **Step 4: Write the merge helper** — `mobile/src/features/consent/lib/build-consent-put.ts`:

```ts
import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

/** Build a complete PUT body, preserving the server's current photoConsent and
 * setting location from the live OS grant + the supplied terms version. */
export function buildConsentPut(
  current: ConsentState,
  osGranted: boolean,
  termsVersion: string,
): ConsentPutBody {
  return {
    locationConsent: osGranted,
    photoConsent: current.photoConsent,
    termsVersion,
  };
}
```

- [ ] **Step 5: Write `api.ts`** — `mobile/src/features/consent/api.ts`:

```ts
import { api } from "@/lib/api-client";
import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

/** The api-client response interceptor unwraps the JSend envelope, so these
 * resolve to the `data` payload. Cast mirrors features/saved/api.ts exactly. */
export async function getConsents(): Promise<ConsentState> {
  return (await api.get("/users/me/consents")) as unknown as ConsentState;
}

export async function putConsents(body: ConsentPutBody): Promise<ConsentState> {
  return (await api.put("/users/me/consents", body)) as unknown as ConsentState;
}
```

> This matches the verified `features/saved/api.ts` style: `(await api.get(...)) as unknown as T`.
> The interceptor returns unwrapped envelope data; `as unknown as T` is the codebase convention
> (not `as any`).

- [ ] **Step 6: Write `queries.ts`** — `mobile/src/features/consent/queries.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { getConsents, putConsents } from "@/features/consent/api";
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
    onSuccess: (next: ConsentState) => qc.setQueryData(consentKeys.state, next),
  });
}
```

- [ ] **Step 7: Run test + typecheck to verify green**

Run: `cd mobile && npm test -- consent/lib && npm run typecheck`
Expected: PASS + no type errors.

- [ ] **Step 8: Commit**

```bash
git add mobile/src/features/consent
git commit -m "feat(mobile): consent feature module (api/queries/merge helper)"
```

---

## Task 6: Fix `record-consent` to merge (preserve photoConsent)

**Files:**
- Modify: `mobile/src/features/auth/usecases/record-consent.ts`
- Test: `mobile/src/features/auth/usecases/__tests__/record-consent.test.ts` (create or extend)

**Interfaces:**
- Consumes: `getConsents`, `putConsents` (Task 5), `buildConsentPut` (Task 5), `TERMS_VERSION`, `expo-location`.

- [ ] **Step 1: Check for an existing test** — read `mobile/src/features/auth/usecases/__tests__/` to see if `record-consent` already has a test. If yes, extend it; if no, create the file below.

- [ ] **Step 2: Write the failing test** — `mobile/src/features/auth/usecases/__tests__/record-consent.test.ts`:

```ts
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import { getConsents, putConsents } from "@/features/consent/api";

jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ granted: true }),
}));
jest.mock("@/features/consent/api", () => ({
  getConsents: jest.fn(),
  putConsents: jest.fn(),
}));
jest.mock("@/constants/legal", () => ({ TERMS_VERSION: "2026-06-22" }));

const mockGet = getConsents as jest.MockedFunction<typeof getConsents>;
const mockPut = putConsents as jest.MockedFunction<typeof putConsents>;

describe("recordConsentSnapshot", () => {
  beforeEach(() => jest.clearAllMocks());

  it("preserves existing photoConsent and records OS location + current terms", async () => {
    mockGet.mockResolvedValue({
      locationConsent: false,
      photoConsent: true,
      termsVersion: "2026-01-01",
      consentedAt: "2026-01-01T00:00:00Z",
    });
    mockPut.mockResolvedValue({
      locationConsent: true,
      photoConsent: true,
      termsVersion: "2026-06-22",
      consentedAt: "2026-06-22T00:00:00Z",
    });

    await recordConsentSnapshot();

    expect(mockPut).toHaveBeenCalledWith({
      locationConsent: true,
      photoConsent: true,
      termsVersion: "2026-06-22",
    });
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd mobile && npm test -- record-consent`
Expected: FAIL — current impl hardcodes `photoConsent: false` and never calls `getConsents`.

- [ ] **Step 4: Rewrite the usecase** — `mobile/src/features/auth/usecases/record-consent.ts`:

```ts
import * as Location from "expo-location";
import { TERMS_VERSION } from "@/constants/legal";
import { getConsents, putConsents } from "@/features/consent/api";
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";

/** Record implied consent at login (S01 §3): current terms version + a snapshot
 * of the OS location permission, while preserving the user's existing
 * photoConsent (P5 D6 — read-then-merge, no clobber). Never prompts.
 * Caller fires-and-forgets; failures are swallowed by the caller. */
export async function recordConsentSnapshot(): Promise<void> {
  const [current, perm] = await Promise.all([
    getConsents(),
    Location.getForegroundPermissionsAsync(),
  ]);
  await putConsents(buildConsentPut(current, perm.granted, TERMS_VERSION));
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd mobile && npm test -- record-consent`
Expected: PASS.

- [ ] **Step 6: Run the full gate**

Run: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add mobile/src/features/auth/usecases/record-consent.ts mobile/src/features/auth/usecases/__tests__/record-consent.test.ts
git commit -m "fix(mobile): record-consent merges (preserve photoConsent) (D6)"
```

---

## Task 7: Consent-management screen + entry point

**Files:**
- Modify: `mobile/src/components/Icon.tsx`
- Modify: `mobile/src/features/profile/components/SettingsRows.tsx`
- Create: `mobile/src/app/consent.tsx`
- Modify: `mobile/src/app/_layout.tsx`

**Interfaces:**
- Consumes: `useConsents`, `useUpdateConsent` (Task 5); `buildConsentPut` (Task 5); `TERMS_VERSION`; `expo-location`; `Icon`, `colors`, `spacing`.
- Produces: route `/consent`; `Icon name="shield-check"`; `SettingsRows` `동의 관리` row (authed).

- [ ] **Step 1: Add `shield-check` icon** — in `mobile/src/components/Icon.tsx`, read the file first to match its registry shape, then add a monochrome line-SVG entry keyed `"shield-check"` (shield outline + check). Use the same `<Svg stroke="currentColor" .../>` pattern as existing icons, e.g. paths:

```tsx
// shield-check
<>
  <Path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
  <Path d="M9 12l2 2 4-4" />
</>
```

- [ ] **Step 2: Add the `동의 관리` row** — in `mobile/src/features/profile/components/SettingsRows.tsx`, change the signature to accept an authed callback and render the row only when present. Add prop `onConsent?: () => void`; render it right after the `위치 권한` row:

```tsx
      {onConsent ? (
        <Pressable style={styles.row} onPress={onConsent}>
          <View style={styles.icon}>
            <Icon name="shield-check" size={21} color={colors.sec} />
          </View>
          <Text style={styles.label}>동의 관리</Text>
          <Icon name="chevron-right" size={20} color={colors.ter} />
        </Pressable>
      ) : null}
```
Update the component signature: `export function SettingsRows({ onLogout, onConsent }: { onLogout?: () => void; onConsent?: () => void })`.
In `mobile/src/app/(tabs)/profile.tsx`, pass it only when authenticated:
```tsx
        <SettingsRows
          onLogout={isAuthenticated ? () => void logout() : undefined}
          onConsent={isAuthenticated ? () => router.push("/consent") : undefined}
        />
```

- [ ] **Step 3: Write the consent screen** — `mobile/src/app/consent.tsx`:

```tsx
import { useCallback } from "react";
import { View, Text, Pressable, ScrollView, Switch, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useFocusEffect } from "expo-router";
import * as Location from "expo-location";
import { Linking } from "react-native";
import { Icon } from "@/components/Icon";
import { TERMS_VERSION } from "@/constants/legal";
import { useConsents, useUpdateConsent } from "@/features/consent/queries";
import { buildConsentPut } from "@/features/consent/lib/build-consent-put";
import { colors, spacing } from "@/constants/theme";

export default function ConsentScreen() {
  const insets = useSafeAreaInsets();
  const { data, isLoading, isError, refetch } = useConsents();
  const update = useUpdateConsent();

  // Focus-local location-permission re-sync (S01 §4; global AppState hook deferred).
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        if (!data) return;
        const perm = await Location.getForegroundPermissionsAsync();
        if (!cancelled && perm.granted !== data.locationConsent) {
          update.mutate(buildConsentPut(data, perm.granted, data.termsVersion ?? TERMS_VERSION));
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [data, update]),
  );

  const togglePhoto = (next: boolean) => {
    if (!data) return;
    update.mutate({
      locationConsent: data.locationConsent,
      photoConsent: next,
      termsVersion: data.termsVersion ?? TERMS_VERSION,
    });
  };

  const reConsent = () => {
    if (!data) return;
    update.mutate({
      locationConsent: data.locationConsent,
      photoConsent: data.photoConsent,
      termsVersion: TERMS_VERSION,
    });
  };

  const isCurrent = data?.termsVersion === TERMS_VERSION;
  const consentedDate = data?.consentedAt ? data.consentedAt.slice(0, 10).replace(/-/g, ".") : null;

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>동의 관리</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {isLoading ? (
          <Text style={styles.note}>불러오는 중…</Text>
        ) : isError || !data ? (
          <View style={styles.errBox}>
            <Text style={styles.note}>동의 정보를 불러오지 못했어요</Text>
            <Pressable onPress={() => void refetch()} hitSlop={8}>
              <Text style={styles.retry}>재시도</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <View style={styles.group}>
              <Pressable style={styles.row} onPress={() => Linking.openSettings()}>
                <View style={styles.rowMain}>
                  <Text style={styles.label}>위치정보 수집·이용 동의</Text>
                  <Text style={styles.sub}>내 주변 추천에 사용해요. 기기 설정에서 변경할 수 있어요.</Text>
                </View>
                <Text style={styles.value}>{data.locationConsent ? "허용" : "거부"}</Text>
                <Icon name="chevron-right" size={20} color={colors.ter} />
              </Pressable>
            </View>

            <View style={styles.group}>
              <View style={styles.row}>
                <View style={styles.rowMain}>
                  <Text style={styles.label}>사진 분석 이용 동의</Text>
                  <Text style={styles.sub}>
                    사진 검색 시 이미지는 기기에서 분석 후 즉시 폐기되며 저장하지 않아요.
                  </Text>
                </View>
                <Switch
                  value={data.photoConsent}
                  onValueChange={togglePhoto}
                  trackColor={{ false: colors.line, true: colors.ink }}
                />
              </View>
            </View>

            <View style={styles.group}>
              <View style={styles.row}>
                <View style={styles.rowMain}>
                  <Text style={styles.label}>약관·개인정보 동의</Text>
                  <Text style={styles.sub}>
                    버전 {data.termsVersion ?? "—"}
                    {consentedDate ? ` · ${consentedDate}` : ""}
                  </Text>
                </View>
                {isCurrent ? (
                  <Text style={styles.value}>최신</Text>
                ) : (
                  <Pressable style={styles.reBtn} onPress={reConsent} hitSlop={8}>
                    <Text style={styles.reBtnText}>재동의</Text>
                  </Pressable>
                )}
              </View>
              <Pressable style={styles.linkRow} onPress={() => router.push("/legal")}>
                <Text style={styles.linkText}>약관·정책 보기</Text>
                <Icon name="chevron-right" size={18} color={colors.ter} />
              </Pressable>
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.inset },
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.bg,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  navBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  title: {
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  group: { backgroundColor: colors.bg, marginTop: 9 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 16,
    paddingHorizontal: spacing.lg,
  },
  rowMain: { flex: 1, gap: 4 },
  label: { fontSize: 15.5, fontWeight: "600", color: colors.ink },
  sub: { fontSize: 12.5, lineHeight: 18, color: colors.ter },
  value: { fontSize: 14, color: colors.ter },
  reBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.line,
  },
  reBtnText: { fontSize: 13, fontWeight: "700", color: colors.ink },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  linkText: { fontSize: 14, color: colors.sec, fontWeight: "600" },
  note: { textAlign: "center", color: colors.ter, fontSize: 14, marginTop: spacing.xxl },
  errBox: { alignItems: "center", gap: spacing.md, marginTop: spacing.xxl },
  retry: { color: colors.ink, fontSize: 14, fontWeight: "700" },
});
```

- [ ] **Step 4: Register the route** — in `mobile/src/app/_layout.tsx`, add inside `<Stack>`:

```tsx
        <Stack.Screen name="consent" />
```

- [ ] **Step 5: Run the full gate**

Run: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add mobile/src/components/Icon.tsx mobile/src/features/profile/components/SettingsRows.tsx "mobile/src/app/(tabs)/profile.tsx" mobile/src/app/consent.tsx mobile/src/app/_layout.tsx
git commit -m "feat(mobile): consent-management screen + 동의 관리 entry (C)"
```

---

## Self-Review notes

- **Spec coverage:** A (Tasks 2–3) · B (Task 4) · C backend GET (Task 1) · C module (Task 5) ·
  record-consent merge D6 (Task 6) · consent screen + entry D5/D7/D8 (Task 7). Marketing/photo-gating
  explicitly deferred (spec §8) — no task, by design.
- **Type consistency:** `ConsentState` (BE schema / mobile `types.ts`) and `ConsentPutBody`
  share field names `locationConsent`/`photoConsent`/`termsVersion`(+`consentedAt` on state).
  `buildConsentPut` signature is identical in Tasks 5/6/7.
- **api.ts caveat:** Task 5 Step 5 instructs the implementer to mirror `features/saved/api.ts`'s exact
  unwrap style and drop the `as unknown` cast if saved doesn't use it — avoids a guessed wrapper shape.
- **Routes:** `/legal`, `/legal/[slug]`, `/consent` registered in `_layout.tsx` across Tasks 3 & 7.
