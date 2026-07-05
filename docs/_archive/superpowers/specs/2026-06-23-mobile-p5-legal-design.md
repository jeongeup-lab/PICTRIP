# Mobile P5 — 법적고지 · 동의 관리 · 마무리 (설계 스펙)

> 입력: `docs/mockups/16-legal.html`, `docs/specs/screens/S06-profile-legal.md`
> (§4 약관·정책, §5 횡단 인증/계정), `docs/specs/screens/S01-onboarding-auth.md`
> §4 (consent 기록 시점 + 약관 동의 버전 수명주기 S11 §D7), 루트 `CLAUDE.md`(제약).
> 산출: 모바일 3딜리버러블(A 법적고지 / B inert 링크 연결 / C 동의 관리) + 최소
> 백엔드 보강(`GET /users/me/consents`).
>
> 브랜치: `feat/mobile-p5-legal` (P4 `feat/mobile-p4-map` 위 3단 스택). PR #5→#6→#7
> 순으로 머지. 머지/푸시는 사용자 지시 시에만.

빌드 마지막 단계(P5). 무채색(잉크/그레이, 로즈 금지) · 게스트 우선 · 이모지 금지 ·
새 네이티브 모듈 금지(WebView/web-browser는 기존 의존) · JSend 1회 언래핑 · `as any` 금지.

---

## 0. 현황 사실 확인 (코드 검증 완료)

| # | 사실 | 근거 |
|---|---|---|
| F1 | 백엔드 consent 계약은 **`PUT /users/me/consents`만 존재**, `GET` 없음 | `backend/app/modules/users/routes.py` |
| F2 | consent 표면 = `locationConsent`(bool) · `photoConsent`(bool, 기본 false) · `termsVersion`(str). **마케팅/알림 동의는 API에 없음** (`notification_consent` DB 컬럼은 default만, 어디서도 참조 안 함) | `schemas.py` `ConsentIn`/`ConsentOut`, `services.py:put_consents` |
| F3 | P3 `record-consent.ts`는 **로그인 시 photoConsent=false로 하드코딩** upsert → 재로그인마다 photo 동의가 false로 덮어쓰기됨(버그성) | `mobile/src/features/auth/usecases/record-consent.ts` |
| F4 | `expo-web-browser`·`react-native-webview`·`expo-constants` 모두 이미 의존성 | `mobile/package.json` |
| F5 | inert 링크 2곳: 프로필 푸터 `약관·정책`(plain Text), 로그인 카드 약관 문구(plain Text) | `app/(tabs)/profile.tsx`, `features/auth/components/LoginCard.tsx` |
| F6 | `TERMS_VERSION = "2026-06-22"` 상수 존재 | `mobile/src/constants/legal.ts` |
| F7 | 화면 패턴: back-nav(`saved.tsx`), Stack 등록(`app/_layout.tsx`), query+usecase(`features/saved/queries.ts`), WebView(`features/map`) | 검증 |

S06 §8 / §7 reconcile: "약관 = 백엔드 테이블 불필요, S6는 **열람 전용**, 동의 버전
연결은 S1/S7로 이월." → P5에서 **열람(A) + 동의 관리(C)**를 함께 닫는다(이월분 회수).

---

## 1. 잠긴 결정 (P5)

| # | 결정 | 근거 |
|---|---|---|
| **P5-D1** | 법적고지 본문 = **인앱 WebView `https://pictrip.org/legal/{slug}`** (4문서). 호스팅 페이지는 S8 산출물(이 스펙 범위 밖, 미존재여도 화면은 error 상태로 정상 동작) | S06 D1. 신규 네이티브 모듈 없음(F4) |
| **P5-D2** | 법적고지 리스트·본문은 **게스트도 접근**. 동의 관리(C)는 **로그인 전용** | S06 §4(게스트 접근) / consent는 per-user |
| **P5-D3** | WebView 로드 실패 = `재시도` + `브라우저로 열기`(`expo-web-browser.openBrowserAsync`) | S06 §4 error 상태. `Linking`보다 인앱 SafariVC/Custom Tab UX 우수, 이미 의존 |
| **P5-D4** | **백엔드 `GET /users/me/consents` 신규 추가**(최소). 동의 관리 UI가 실제 서버 상태를 읽어 토글·재동의가 theater가 아닌 실 기능이 되게 함. row 없으면 기본값 반환 | F1 갭. 브리프가 GET 사용을 가정. lean한 service 1함수 + route 1개 |
| **P5-D5** | 동의 관리 화면은 **3개 실 필드만 노출**: ① 위치정보(OS 권한 연동) ② 사진 분석(서버 토글) ③ 약관·개인정보 동의 현황(버전/일시 + 재동의). **마케팅 동의 제외**(API 부재 F2 — 추가 시 백엔드 스키마·DB 변경 필요, 별도 후속) | YAGNI. 브리프 "위치/사진/마케팅 **등**"의 의도(granular)는 충족하되 실재 표면만 |
| **P5-D6** | `record-consent.ts`를 **merge 방식으로 수정**: 로그인 시 GET으로 현재 photo 동의를 읽어 보존하고 location(OS)+terms만 갱신 → F3 클로버 버그 해소 | 동의 관리 토글이 재로그인에 살아남아야 일관 |
| **P5-D7** | 사진 분석 토글은 **동의 기록만**(서버 persist) — P2 포토서치 **게이팅은 하지 않음**(이미 머지된 P2 흐름 변경은 범위 밖). 후속으로 명시 | 범위 통제. CLIP in-memory·바이트 폐기라 저장 동의 대상 없음 → 토글은 "기록된 동의 관리" 의미 |
| **P5-D8** | 약관 재동의: 동의 관리 화면에서 기록된 `termsVersion`과 현행 `TERMS_VERSION` 비교. 다르면 `재동의 필요` 배지 + `재동의` 액션(→ PUT 현행 버전). 같으면 `최신` | S01 §4 / S11 §D7 수명주기. 강제 인터셉트(앱 진입 차단)는 후속(lean) |
| **P5-D9** | 브랜치는 **P4 위 3단 스택**(머지 없이). PR 머지는 outward 액션 → 사용자 지시 시에만 | 메모리/브리프 "푸시는 시킬 때만" |

---

## 2. 딜리버러블 A — 법적고지 (화면 16)

### A.1 상수 (`features/legal/constants.ts`)
```ts
export interface LegalDoc { slug: LegalSlug; title: string }
export type LegalSlug = "terms" | "privacy" | "location" | "data-sources";
export const LEGAL_DOCS: readonly LegalDoc[] = [
  { slug: "terms",        title: "이용약관" },
  { slug: "privacy",      title: "개인정보처리방침" },
  { slug: "location",     title: "위치기반서비스 이용약관" },
  { slug: "data-sources", title: "데이터 출처" },
];
export const LEGAL_BASE_URL = "https://pictrip.org/legal";
export function legalUrl(slug: LegalSlug): string { return `${LEGAL_BASE_URL}/${slug}`; }
```
- 라벨은 mockup 16 verbatim. `LegalSlug`로 `[slug]` 라우트 파라미터 검증.

### A.2 리스트 화면 (`src/app/legal/index.tsx`)
- mockup 16 그대로: 네비바(뒤로 ‹ + 타이틀 "약관·정책") + 정적 4행(라벨 + chevron-right).
- `saved.tsx` 네비바 패턴 재사용. 행 탭 → `router.push("/legal/{slug}")`.
- 로딩/에러 없음(정적). 게스트 접근 가능.

### A.3 본문 WebView (`src/app/legal/[slug].tsx` + `features/legal/components/LegalWebView.tsx`)
- `useLocalSearchParams`에서 `slug` 읽고 `LEGAL_DOCS`로 검증·타이틀 조회. 미지 slug → 리스트로 back(또는 "문서를 찾을 수 없어요").
- 네비바: 뒤로 ‹ + 타이틀 = 문서명.
- `LegalWebView`: `react-native-webview` 래퍼.
  - `loading`: 상단 인디터미닛 바 또는 중앙 스피너(`ActivityIndicator`, 무채색 `colors.sec`). `onLoadStart`/`onLoadEnd`.
  - `normal`: 페이지.
  - `error`(`onError`/`onHttpError` 또는 4xx/5xx): 중앙 "불러오지 못했어요" + `재시도`(reload) + `브라우저로 열기`(`WebBrowser.openBrowserAsync(legalUrl(slug))`).
- `originWhitelist`는 `https://pictrip.org`만. 외부 네비게이션은 `onShouldStartLoadWithRequest`로 차단하고 web-browser로.

### A.4 Stack 등록
`app/_layout.tsx`에 `<Stack.Screen name="legal/index" />` + `<Stack.Screen name="legal/[slug]" />` 추가(헤더 숨김, 기본 push).

---

## 3. 딜리버러블 B — inert 링크 연결

### B.1 프로필 푸터 `약관·정책`
`app/(tabs)/profile.tsx`: 현재 plain `<Text style={footLink}>약관·정책</Text>` →
`<Pressable onPress={() => router.push("/legal")}>`. 게스트·로그인 공통 표시(이미 그러함).

### B.2 로그인 카드 약관 문구
`features/auth/components/LoginCard.tsx`: "계속 진행하면 **이용약관** 및 **개인정보처리방침**에
동의하는 것으로 간주돼요." 에서 두 구문을 **탭 가능한 링크**로.
- 단일 `<Text>` 안에 nested `<Text onPress={...}>`로 "이용약관"·"개인정보처리방침"만 밑줄/`colors.sec` 강조.
- `이용약관` → `router.push("/legal/terms")`, `개인정보처리방침` → `router.push("/legal/privacy")`.
- full(로그인 화면)·sheet(넛지) 두 variant 공통 동작(expo-router 전역 push).
- 시트 위에서 push 시 시트는 유지(스택 위로 push) — 복귀 시 시트 그대로.

---

## 4. 딜리버러블 C — 동의 관리

### C.1 백엔드 — `GET /users/me/consents` (최소 보강)
- **schema** (`users/schemas.py`): `ConsentState(BaseModel)` — `locationConsent: bool = False`,
  `photoConsent: bool = False`, `termsVersion: str | None = None`, `consentedAt: datetime | None = None`.
- **service** (`users/services.py`): `get_consents(session, user_id) -> ConsentState`. `UserConsent`를
  user_id로 조회 → 없으면 `ConsentState()`(전부 기본), 있으면 매핑.
- **route** (`users/routes.py`): `GET /users/me/consents` → `ok(state.model_dump())`. `CurrentUserId` 보호.
- **tests** (`backend/tests/...`): row 있음/없음 두 분기. 기존 users 테스트 파일에 추가.
- JSend·`ok()`·mypy·ruff 통과. `pictrip_test` DB로 pytest.

### C.2 모바일 `features/consent/`
- `types.ts`: `ConsentState { locationConsent; photoConsent; termsVersion: string | null; consentedAt: string | null }`.
- `api.ts`: `getConsents(): Promise<ConsentState>` (`api.get`), `putConsents(body): Promise<ConsentState>`
  (`api.put`, body = `{ locationConsent, photoConsent, termsVersion }`). JSend 언래핑은 api-client가 처리.
- `queries.ts`: `consentKeys.state`; `useConsents()`(query, `enabled: isAuthenticated`);
  `useUpdateConsent()`(mutation, onSuccess invalidate + setQueryData echo).
- 셀렉터/머지 헬퍼는 `lib/`로 분리(단위 테스트 대상).

### C.3 화면 (`src/app/consent.tsx`)
네비바(뒤로 ‹ + 타이틀 "동의 관리"). 로그인 전용(미인증 진입 시 방어적으로 back/로그인 유도).
세 섹션(그룹 카드, `SettingsRows` 스타일 재사용):

1. **위치정보 수집·이용 동의** (행 + 상태값 + chevron)
   - 상태 = `expo-location.getForegroundPermissionsAsync()` → `허용`/`거부`/`미설정`.
   - 탭 → `Linking.openSettings()`.
   - `useFocusEffect`로 화면 포커스 시 OS 권한 재확인 → 서버 `locationConsent`와 다르면 PUT 동기화
     (S01 §4 "권한 변경 추적"의 화면-국소 구현; 전역 AppState 훅은 후속).
   - 서브카피: "내 주변 추천에 사용해요. 기기 설정에서 변경할 수 있어요."

2. **사진 분석 이용 동의** (행 + `Switch`)
   - 값 = 서버 `photoConsent`. 토글 → `useUpdateConsent` PUT(낙관적 + 실패 롤백).
   - 무채색 `Switch`(`trackColor` ink/line, `thumbColor` 기본). 이모지 금지.
   - 서브카피: "사진 검색 시 이미지는 기기에서 분석 후 즉시 폐기되며 저장하지 않아요."

3. **약관·개인정보 동의 현황** (행, chevron 없음 또는 액션 버튼)
   - `termsVersion` 표시 + `consentedAt`(있으면 `YYYY.MM.DD`).
   - `termsVersion === TERMS_VERSION` → `최신`(ter). 다르거나 null → `재동의 필요` 배지 +
     `재동의` 버튼 → 약관 보기(`/legal/terms`) 후 PUT 현행 `TERMS_VERSION`(D8). 최소 구현:
     `재동의` 탭 = 즉시 PUT 현행 버전(약관 열람은 같은 화면 약관 링크로 유도).
   - 하단 보조 링크: `약관·정책 보기` → `/legal`.

상태: `loading`(query 로딩 → 그룹 스켈레톤/placeholder), `normal`, `error`(GET 실패 → 인라인 재시도).

### C.4 진입점 — `SettingsRows`에 `동의 관리` 행
`features/profile/components/SettingsRows.tsx`: `위치 권한` 아래 **로그인 시에만** `동의 관리`
행(shield/check 라인-SVG 아이콘 + chevron) 추가 → `router.push("/consent")`.
- 아이콘: `Icon.tsx`에 `shield-check`(또는 `shield`) 라인-SVG 추가(무채색).
- props로 `onConsent?: () => void` 또는 화면에서 직접 `router.push`. authed 분기는 기존 `onLogout` 유무와 동일 패턴.

### C.5 `record-consent.ts` 수정 (D6)
로그인 시:
```ts
const current = await getConsents();           // 신규 GET (실패 시 기본값 폴백)
const perm = await Location.getForegroundPermissionsAsync();
await putConsents({
  locationConsent: perm.granted,
  photoConsent: current.photoConsent,          // 보존 (클로버 버그 해소)
  termsVersion: TERMS_VERSION,
});
```
fire-and-forget 유지. `features/consent/api`의 함수 재사용(중복 axios 호출 제거).

---

## 5. Stack / 라우트 등록 요약
`app/_layout.tsx`에 추가:
- `legal/index`, `legal/[slug]`, `consent` (모두 기본 push, 헤더 숨김).

---

## 6. 파일 영향 요약

| 동작 | 경로 |
|---|---|
| 신규 | `mobile/src/features/legal/constants.ts` |
| 신규 | `mobile/src/features/legal/components/LegalWebView.tsx` |
| 신규 | `mobile/src/app/legal/index.tsx` |
| 신규 | `mobile/src/app/legal/[slug].tsx` |
| 신규 | `mobile/src/features/consent/{types,api,queries}.ts` (+ `lib/` 머지 헬퍼) |
| 신규 | `mobile/src/app/consent.tsx` |
| 수정 | `mobile/src/app/_layout.tsx` (Stack 3 화면 등록) |
| 수정 | `mobile/src/app/(tabs)/profile.tsx` (푸터 약관·정책 → push) |
| 수정 | `mobile/src/features/auth/components/LoginCard.tsx` (약관 링크) |
| 수정 | `mobile/src/features/profile/components/SettingsRows.tsx` (동의 관리 행) |
| 수정 | `mobile/src/features/auth/usecases/record-consent.ts` (merge) |
| 수정 | `mobile/src/components/Icon.tsx` (shield 아이콘) |
| 수정(BE) | `backend/app/modules/users/{routes,schemas,services}.py` (GET consents) |
| 수정(BE) | `backend/tests/...` (GET consents 테스트) |

---

## 7. 검증
- 모바일: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`.
- 백엔드: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && POSTGRES_DB=pictrip_test uv run pytest`.
- 단위 테스트 추가 대상: `features/consent`(머지/셀렉터 헬퍼, api 매핑), `features/legal`(slug 검증·URL 빌더), 백엔드 `get_consents`(2분기). WebView/화면은 경량 렌더 스모크 또는 헬퍼 단위로.

---

## 8. 후속(범위 밖, 명시)
- 마케팅/알림 동의: API·DB 컬럼 신설 필요(P5 제외, D5).
- 포토서치(P2) photoConsent 게이팅(D7).
- 약관 갱신 강제 재동의 인터셉트(앱 진입 차단) — 현재는 동의 관리 화면 내 배지/액션만(D8).
- `pictrip.org/legal/*` 정적 페이지 호스팅 — S8 인프라 산출물.
- 전역 AppState 권한 재동기화 훅 — S10/후속(현재는 동의 관리 화면 focus-국소).
- 실 OAuth 콘솔 자격증명·실 Kakao JS 키 수동 스모크(P3/P4 이월) — 자격증명 확보 시.
