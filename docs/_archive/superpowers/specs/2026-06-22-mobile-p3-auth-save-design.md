# Mobile P3 — OAuth 로그인 + 저장/프로필 설계

> 2026-06-22 brainstorming 세션. 입력: `docs/mockups/03-login.html`·`13-saved.html`·
> `14-profile.html`·`15-profile-states.html`(UI SSOT), `docs/specs/screens/S01-onboarding-auth.md`
> (잠긴 인증 결정), 백엔드 `app/modules/users/{routes,schemas,services}.py`(계약),
> P0/P1/P2 코드(패턴). 산출물 = 화면/네비/모듈 설계. 구현 플랜은 writing-plans로 분리.

## 0. 목표 한 줄

게스트-우선 앱에 **트리거 기반 OAuth 로그인**(카카오·구글·애플 OIDC)과 그 위에서만
성립하는 **스크랩(저장)·마이(프로필)** 를 붙인다. first-run 흐름(스플래시→온보딩→홈→
디스커버리→포토서치)은 그대로 게스트로 동작하고, 로그인은 저장/마이 데이터를 만질 때만
요구된다.

---

## 1. 범위 & 경계

### 1.1 P3 포함
- **03 로그인**: 단일 `LoginCard` 컴포넌트, 2표면 — 풀스크린(목업 03) + 저장 넛지 바텀시트.
- **OAuth 3종**: 카카오·구글·애플 모두 OIDC `id_token` 획득 → `POST /auth/oauth/{provider}`.
- **스팟 상세(07) SAVE 토글** → `/users/me/saved` 연결(게스트는 넛지로 로그인 유도).
- **13 스크랩 그리드** + 빈 상태.
- **14/15 마이** 3변형: 로그인 / 로그인·스크랩없음 / 게스트.
- **로그아웃**(`/auth/logout`), **회원탈퇴**(`DELETE /users/me`).
- **로그인 시 consent 자동 기록**: 간주 동의(현행 `TERMS_VERSION`) + 위치권한 OS 스냅샷
  → `PUT /users/me/consents`(fire-and-forget).
- 게스트→로그인 **승격**(보류 액션 재개), 401/`GUEST_FORBIDDEN` 분기.

### 1.2 P3 제외 (→ P5)
- 약관/개인정보 **법적고지 본문 화면**(16). P3에서 약관·정책/이용약관 링크는 **inert
  플레이스홀더**(누르면 아무 동작 없음 또는 추후 라우트 자리만).
- **granular 동의 관리 UI**. P3는 로그인 시 자동 기록만 — 토글식 관리 화면은 P5(legal).
- AppState 포그라운드 위치권한 재동기화(S10/후속 백로그).

### 1.3 확정된 보조 결정 (2026-06-22 승인)
- **dev 로그인** = 모바일 전용 가짜 세션(`__DEV__`, 백엔드 무변경). 마이/로그인 표면·네비
  수동 스모크용. 저장 API end-to-end 수동 확인은 실 provider 자격증명 필요(콘솔 체크리스트로
  문서화). 자동 검증은 jest 목으로 전 로직 커버.
- **consent**: 로그인 직후 자동 기록만(관리 UI 없음).

---

## 2. 아키텍처 — 모듈/파일

기존 레이어 규약(`src/features/<domain>/{api,queries,stores,usecases,components,hooks}`)을
그대로 따른다. 파일명: 컴포넌트 PascalCase, 런타임 모듈 kebab-case, `src/app/**`는 Expo Router.

```
src/features/auth/
  api.ts                       oauthLogin(provider,idToken,nonce?)·logout(refreshToken)·deleteAccount()
  usecases/oauth-providers.ts  getIdToken(provider) → { idToken, nonce? }
                                 apple = expo-apple-authentication
                                 google·kakao = expo-auth-session 웹 OIDC + expo-web-browser
  usecases/record-consent.ts   recordConsentSnapshot() — 위치권한 스냅샷 + TERMS_VERSION
  stores/auth-store.ts         (확장) loginWithOAuth·logout·deleteAccount·devLogin
  stores/auth-prompt-store.ts  넛지 시트 상태 { visible, reason, resolve }
  hooks/use-auth-gate.ts       requireAuth(reason): Promise<boolean>
  components/LoginCard.tsx     공유 본문(브랜드 + 3버튼 + 약관 문구), variant: "full" | "sheet"
  components/SocialButton.tsx  provider 버튼 (kakao/google/apple)
  components/AuthPromptSheet.tsx  루트 마운트 넛지 바텀시트

src/features/saved/
  api.ts        listSaved(cursor?)·saveSpot(contentId)·unsaveSpot(contentId)
  queries.ts    useSavedList()(무한)·useSaveMutation()·useUnsaveMutation()·useIsSaved(contentId)
  components/SavedCard.tsx   13 그리드 카드(150px, 이미지+scrim+하트+이름)
  components/SavedRail.tsx   14 프로필 가로 레일(96px 아이템)
  components/EmptyBoard.tsx  빈 스크랩 보드(문구 + CTA)

src/features/profile/
  components/ProfileHeader.tsx  아바타 + 이름 + 이메일
  components/SettingsRows.tsx   위치권한 / 앱버전 / 로그아웃 행 그룹
  components/GuestLoginRow.tsx  게스트 로그인 유도 행

src/constants/legal.ts         TERMS_VERSION, 약관/개인정보 링크 자리(P5 라우트 예약)
src/lib/app-meta.ts            APP_VERSION (expo-constants에서 읽기)
```

라우트(신규/수정):
```
src/app/auth/login.tsx         03 풀스크린 로그인 (presentation: fullScreenModal)
src/app/saved.tsx              13 스크랩 그리드 (card push, back, 탭바 없음)
src/app/(tabs)/profile.tsx     14/15 마이 (재작성 — ComingSoon 대체)
src/app/_layout.tsx            (수정) auth/login·saved Stack.Screen 추가 + <AuthPromptSheet/> 마운트
src/app/spots/[contentId].tsx  (수정) inert SAVE 버튼 → 토글 연결
```

---

## 3. 네비게이션 & 표면 (S01 §5.1 준수)

| 화면 | 라우트 | presentation | 진입 | 이탈 |
|---|---|---|---|---|
| 03 풀스크린 로그인 | `auth/login` | `fullScreenModal` | 마이 게스트 로그인 행(15b) | 성공=직전(마이) 복귀, 취소=pop |
| 03 넛지 시트 | (라우트 아님) 루트 `<AuthPromptSheet>` | 바텀시트 | 저장 시도 등 인라인 | 성공=resolve(true)+닫힘, 취소=resolve(false) |
| 13 스크랩 그리드 | `saved` | card push (back, no tabbar) | 마이 "전체보기" | back → 마이 |
| 14/15 마이 | `(tabs)/profile` | tab | 마이 탭 | — |

- **풀스크린 vs 시트 구분**: 같은 `LoginCard`를 `variant`로 렌더. 풀스크린은 라우트, 시트는
  promise 기반 루트 오버레이(보류 액션 재개를 깔끔히 처리하기 위해 라우트 대신 store+resolve).
- 모달/스택 규칙: 로그인·사진 플로우는 탭 위 모달; 스팟상세·스크랩그리드는 push.

---

## 4. 인증 흐름

### 4.1 공통 시퀀스
```
버튼 탭 → getIdToken(provider)               (provider 네이티브/웹 OIDC 시트)
        → POST /auth/oauth/{provider} {idToken, nonce?}   (bareClient — 토큰 없음)
        → setSession(pair): refresh=secure-store, access=메모리, user=store
        → recordConsentSnapshot() (fire-and-forget; 실패 무시)
        → 보류 액션 재개(시트) / 직전 화면 복귀(풀스크린)
```

### 4.2 provider별 id_token 획득 (S01 §3 검증 규약과 정합)
- **Apple** — `expo-apple-authentication`. raw nonce 생성(`expo-crypto`) → `SHA-256` 해시를
  요청에 전달, 응답 `identityToken`(=id_token) + raw nonce를 백엔드로(백엔드가 base64url
  무패딩 비교). 이름은 최초 1회만(없어도 진행).
- **Google** — `expo-auth-session` OIDC(discovery=Google) + `expo-web-browser`. `response_type`에
  `id_token` 포함(implicit/PKCE), `scope=openid email profile`, redirect = `pictrip` scheme.
  플랫폼별 client_id(iOS/Android/web) env.
- **Kakao** — `expo-auth-session` + Kakao OIDC(`iss=kauth.kakao.com`, `scope=openid`),
  REST 키 + redirect. id_token 수신.
- 모두 `{ idToken, nonce? }` 반환 → 동일 `oauthLogin` 경로.

### 4.3 자격증명 / dev
- 모든 키는 `EXPO_PUBLIC_*` env 플레이스홀더(`mobile/.env.example`에 키 목록 + 콘솔 셋업
  체크리스트). 자격증명 부재 시 실 버튼은 인라인 에러(provider 미구성)로 graceful.
- `__DEV__` **devLogin()**: 백엔드 호출 없이 메모리 가짜 `User` + 가짜 accessToken 세팅
  (refresh 미저장). 마이 로그인/빈 상태·로그인 표면·네비 수동 스모크 전용. 진입점은
  `__DEV__`에서만 보이는 작은 행/버튼(예: 로그인 카드 하단).

### 4.4 상태 (S01 §3)
| 상태 | UX |
|---|---|
| loading | 누른 버튼만 인라인 스피너, 3버튼 비활성(중복 탭 차단). 전면 오버레이 없음 |
| 취소 | 무음 복귀 — 에러 아님, 버튼 원복 |
| provider/백엔드 실패 | 인라인 에러 "잠시 후 다시 시도해 주세요" + 버튼 재활성. `err.code` 분기 |
| 성공 | 시트=닫고 보류 액션 재개 / 풀스크린=직전 복귀 |

---

## 5. 저장(스크랩) 토글

- **게이트**: 스팟 상세 하트 탭 → 게스트면 `requireAuth("save")`(넛지 시트) → 성공 시
  자동으로 저장 재개. 로그인 상태면 즉시 토글.
- **낙관적 업데이트**: `useSaveMutation`(POST, 201/200 멱등) / `useUnsaveMutation`(DELETE, 204
  멱등). 하트 즉시 반영, 실패 시 롤백 + 스크랩 리스트 invalidate.
- **현재 저장 여부**: 백엔드에 per-spot 존재 체크 엔드포인트 없음 → `useIsSaved(contentId)`는
  **스크랩 리스트 캐시에서 파생**. 한계: 페이지네이션으로 첫 페이지 밖 저장분은 초기 하트가
  빈 상태로 보일 수 있음(멱등이라 토글 정확성은 유지). P3 허용, 스펙에 명시.
- **13 그리드 / 14 레일**: `useSavedList` 무한 쿼리(`limit`, `cursor`, `hasMore`). 그리드
  하트 탭 = 해당 항목 unsave(낙관적 제거).

---

## 6. 마이(프로필) — 3변형 (목업 14/15)

공통: 네비바 "마이"(중앙). 스크롤 본문.

- **로그인(14)**: ProfileHeader(아바타 62px + 이름 + 이메일) · "스크랩" 섹션(있으면 가로 레일 +
  "전체보기"→`saved`, 없으면 EmptyBoard "아직 스크랩한 곳이 없어요" + "둘러보러 가기"→홈) ·
  위치권한 행(`Linking.openSettings()`) · 앱버전 행(`APP_VERSION`) · 로그아웃 행 ·
  foot(약관·정책 | 회원탈퇴).
- **게스트(15b)**: GuestLoginRow("로그인하기 / 나만의 여행지를 스크랩해 보세요" → 풀스크린 03) ·
  스크랩 EmptyBoard("로그인하고 마음에 든 곳을 스크랩하세요" + "로그인하기") · 위치권한 ·
  앱버전 · foot(약관·정책만 — 로그아웃/탈퇴 없음).
- **로그아웃**: `POST /auth/logout`(refreshToken 동봉) → `clear()`. 멱등.
- **회원탈퇴**: `Alert` 확인 → `DELETE /users/me`(authed, 204) → `clear()` → 게스트.

---

## 7. 에러 / 401 분기

- `api-client`의 기존 `AUTH_TOKEN_EXPIRED → refresh → retry`(1회) 유지.
- `GUEST_FORBIDDEN`(403, 토큰 미전송)·`AUTH_TOKEN_INVALID`(401) → 게스트로 간주. 저장 등
  보호 액션에서 만나면 넛지로 승격. 마이는 게스트 변형 표시.
- `OAUTH_ID_TOKEN_INVALID`·`OAUTH_PROVIDER_UNAVAILABLE` → 로그인 인라인 에러.
- 모든 분기는 `err.code`(`AppError`) 기준. `err.message`로 분기 금지. traceId는 콘솔만.

---

## 8. 규약 준수 (CLAUDE.md)

- **무채색 토큰만**(`src/constants/theme.ts`). 예외 = 소셜 버튼 브랜드색(카카오 `#FEE500`,
  구글 흰+보더, 애플 `#111113`) — 목업 03 그대로.
- **이모지 금지** → line-SVG `<Icon>`. 필요한 아이콘(로그인/로그아웃/사람/하트필 등) `Icon.tsx`에 추가.
- **`as any` 금지** → `as unknown as T`(api-client/bare-client 패턴).
- **JSend 1회 언래핑**: 새 `api.ts`는 재언래핑 금지. 204(unsave/delete)는 `unwrapData`가
  `undefined` 반환 → void 처리 안전.
- **의존성은 `expo install`로만**. 새 비-Expo 네이티브 모듈 금지(제약 준수 = Expo 관리형만).
- **시크릿 금지** — `EXPO_PUBLIC_*` env만, 코드/커밋에 키 미포함.

---

## 9. 신규 의존성

`expo install`: `expo-apple-authentication`, `expo-auth-session`, `expo-web-browser`,
`expo-crypto`, `expo-constants`. 모두 Expo 관리형 config-plugin 모듈(P2의 `expo-image-picker`와
동급). `app.json` 플러그인에 `expo-apple-authentication`(usesAppleSignIn) 등록.

---

## 10. 테스트 전략

순수 로직 TDD(jest + 목, P2 패턴):
- `oauth-providers`(provider별 분기, nonce 해시, 취소/실패 매핑)
- `auth/api`(3 엔드포인트 호출 형태)
- `auth-store`(loginWithOAuth 성공/실패, logout, deleteAccount, devLogin)
- `auth-prompt-store` + `use-auth-gate`(resolve true/false)
- `saved/api`·`saved/queries`(낙관적 업데이트 + 롤백 + invalidate)
- `record-consent`(스냅샷 페이로드)

화면(`src/app/**`)은 단위 미테스트(라우터 목 과도) — 게이트 = lint + typecheck +
format:check + 전체 suite green + 수동 스모크 체크리스트.

검증(매 태스크): `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`.
커밋은 태스크별, 푸시는 요청 시에만.

---

## 11. 콘솔 셋업 체크리스트 (실 자격증명 — 별도 작업)

> P3 코드는 플레이스홀더로 동작. 실 OAuth는 아래 셋업 후 `.env`에 키 주입.

- **Kakao**: 개발자 콘솔 앱 생성 → OIDC 활성화 + `scope=openid` → REST 키 → redirect URI
  (`pictrip://` / web) 등록.
- **Google**: GCP OAuth client(iOS `org.pictrip.app` / Android `org.pictrip.app`+SHA-1 / web) →
  client_id 3종.
- **Apple**: Apple Developer → App ID(`org.pictrip.app`) Sign in with Apple capability →
  (웹 폴백 시 Service ID/Key). 네이티브는 `expo-apple-authentication`로 충분.

---

## 12. 미해결/이월

- 실 저장 API end-to-end **수동** 스모크는 실 자격증명 확보 후(콘솔 체크리스트).
- `useIsSaved` 페이지네이션 한계(§5) — 필요 시 후속에서 백엔드 존재 체크 엔드포인트 검토.
- 약관/개인정보 본문·granular consent 관리 = P5(legal).
