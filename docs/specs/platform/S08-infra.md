# S8 — 인프라 설계 (배포 토폴로지 · Redis · 정적 호스팅 · 딥링크 · CI/CD)

> 입력 SSOT: `session-context.md`(잠긴 결정·결정 로그·교차 reconcile), `CLAUDE.md`,
> 화면 스펙 S1·S2·S3·S5·S6의 인프라/캐시/딥링크 후속 항목, **현 인프라(실측)** —
> `.github/workflows/*`, `backend/app/core/{db,redis,auth}.py`, `deploy/homeserver/*`.
> 설계 철학: 인프라는 **"이상 설계 → 현실 reconcile"**. 백지 아님, 현 홈서버 기준.

## 0. 요약 (확정 결정)

1. **배포 토폴로지** = 현행 유지(CT112 api+redis+tunnel+runner / CT110 Postgres / CT111
   pipeline) + **apex `pictrip.org` = Cloudflare Pages** 신규(홈서버와 완전 분리).
2. **Redis 인증 = 덴리스트 단일 모델**(S1 원복). 현 회전+도난감지 기계(rt:active/deny/
   grace, sess:, user:sessions ZSET, Lua)는 폐기 → `denyjti:{jti}` 한 키로 대체.
   근거: 이 앱엔 과설계 + 회전 모델은 단일 홈서버에서 **fail-closed**(Redis 한 번 비면
   전원 강제 로그아웃)라 운영 리스크.
3. **Redis 영속성** = AOF `appendfsync everysec` 추가(+RDB 스냅샷 유지). eviction =
   `noeviction` + `maxmemory 256mb`(조용히 토큰 잃지 않고 시끄럽게 실패).
4. **정적 호스팅 = Cloudflare Pages**(legal 4페이지 무채색 + `.well-known/*` 딥링크
   연결파일 + 공유 리다이렉트 페이지). FastAPI static 서빙·앱 번들·Notion 전부 기각.
5. **딥링크 = iOS Universal Links / Android App Links.** 앱 있음→해당 화면 / 없음→스토어.
   deferred deep link 없음(설치 후 홈). 공유 URL = `https://pictrip.org/{spots|curations}/…`.
6. **CI/CD** = 현행(backend push-to-main 자동배포 · mobile `v*`→EAS) 유지 + CF Pages
   네이티브 Git 연동(워크플로 0) + CT112 디스크 prune 주간 systemd timer로 룰화.

---

## 1. 배포 토폴로지

```
                          인터넷
                            │
           ┌────────────────┴─────────────────┐
           │                                   │
   Cloudflare Pages                    Cloudflare Tunnel (named)
   apex  pictrip.org                   api.pictrip.org → CT112:8000
   (정적, Git 자동배포)                       │
   ├─ /legal/*                                │
   ├─ /.well-known/AASA·assetlinks            │
   └─ /{spots|curations}/…  (리다이렉트)       │
                                              │
  ┌───────────────────────────────────────── Proxmox 홈서버 (단일 노드) ──────┐
  │                                           │                                │
  │  CT112  pictrip-api (192.168.219.101)     │   CT110  pictrip-db            │
  │  ├─ pictrip-api   (uvicorn, --workers 1)  │   └─ Postgres 16 + pgvector    │
  │  ├─ pictrip-redis (redis:7-alpine)        │      (spots ~68k, halfvec 임베딩)│
  │  ├─ cloudflared   (pictrip-tunnel.service)│         ▲ LAN (POSTGRES_HOST)  │
  │  └─ GH self-hosted runner (deploy)        │─────────┘                      │
  │                                           │   CT111  pictrip-pipeline (껍데기)│
  └────────────────────────────────────────────────────────────────────────────┘
```

- **신규 컴포넌트는 Cloudflare Pages 하나뿐.** 나머지는 전부 현행. CF zone(`pictrip.org`)은
  이미 보유(`api.pictrip.org`가 named tunnel hostname) → apex/서브도메인 추가비용 0.
- **DNS**: `api.pictrip.org` = 기존 터널 CNAME(불변). apex `pictrip.org` = CF Pages 커스텀
  도메인. `www` = apex로 301(선택).
- **분리 원칙**: 공개 법무/마케팅/딥링크 가용성을 **홈서버 업타임·디스크에 묶지 않는다.**
  스토어·OAuth 심사 URL 안정성을 위해 정적은 CF Pages, 동적 API만 터널.
- **헬스/백업/디스크**(현행): api `/health` 로컬+공개 smoke(`deploy.sh`), 야간 `pg_dump`(CT110),
  Redis AOF/RDB(아래), 디스크 prune timer(§5.3).

---

## 2. Redis 설계 (단일 인스턴스, 네임스페이스 통합)

### 2.1 키 네임스페이스 / TTL / 정책

| 키 | 타입 | TTL | 실패 모드 | 출처 |
|---|---|---|---|---|
| `denyjti:{jti}` | string | 남은 refresh TTL | **fail-open**(소실 시 폐기 토큰 자연만료까지 부활) | **신규**(S1 인증) |
| `rlte:{contentId}` | string(JSON) | 1h | fail-open(미스) | 현 `spots/services/related.py` |
| `region:{lat:.3f}:{lng:.3f}` | string(JSON) | 1d(86 400s) | fail-open(미스) | 현 `map/services.py` |
| `curation:{id}:spots` | string(JSON) | **KST 자정+지터(±N분)** | fail-open(미스) | **신규**(S2 랜덤채움 일캐시) |
| `congestion:{date}` | string(JSON) | **KST 자정+지터** | fail-open(미스) | **신규**(S7-A 혼잡도 일맵, *선택*) |
| `regions:tree` | string(JSON) | 24h | fail-open(미스) | **신규**(S5·S7 centroid 런타임 AVG) |

- **모든 키가 TTL 보유** → 자연 소멸. 모든 캐시는 "죽은 캐시 = 미스"로 강등(현 패턴 유지,
  Redis 장애가 502를 만들면 안 됨).
- `curation:{id}:spots` TTL = **다음 KST 자정까지의 초**(전 사용자 동일 일 단위 픽 보장;
  현 `recommendations`가 쓰던 `_seconds_until_kst_midnight` 패턴 재사용, 모듈 제거와 별개로
  헬퍼는 `app/core` 등으로 이관). 손픽(`curation_spots`)이 차면 이 캐시는 미사용 경로.
- **동시만료 herd 방지(S11 §D6, 승인됨)**: 전 큐레이션 키가 KST 자정 동시 만료 → 첫 요청 폭주가
  동시에 무거운 랜덤채움 재빌드를 치는 thundering herd. 4중 완화:
  (1) **지터** — TTL에 `±N분` 무작위 가산(키별 산포)으로 정확한 동시 만료 회피.
  (2) **stale-while-revalidate** — 만료 직후엔 직전값(stale)을 즉시 서빙하고 백그라운드로 1회만
  갱신(별도 short-TTL `stale:` 미러 또는 본키 만료 시 grace 윈도). 사용자 지연 0.
  (3) **on-publish 즉시 무효화** — 에디터가 큐레이션을 편집/발행하면(관리자 콘솔) 해당
  `curation:{id}:spots`를 즉시 `DEL`(자정 안 기다림). 손픽 변경의 반영 지연 제거.
  (4) **하드 재빌드 mutex** — 백그라운드 재빌드는 per-key `SET <lock> NX PX <ms>`로 단일화
  (락 미획득 워커는 stale 서빙). 재계산 중복 방지.
- `regions:tree` = 17 시도→시군구 목록 + centroid 전체를 **한 키**로 캐시. centroid는 시군구
  스팟 `mapx/mapy` **런타임 AVG**(S7: 무컬럼·무스크립트), 빈 시군구는 시도 평균 폴백. 데이터는
  KTO 동기화 시에만 바뀌므로 24h면 충분(저비용 재계산).
- `congestion:{date}`(*선택*, S11 §D1 승인됨) = §7-A 혼잡도 일 맵을 한 키로 캐시(자정+지터,
  위 herd 완화 동일 적용). 또는 캐시 없이 `spot_concentration` 테이블 **직조인**(저비용) — 둘 다
  **신규 인프라/테이블 없음**. 구현 선택은 S10에 위임.

### 2.2 인증 = 덴리스트 단일 모델 (현 회전 모델 폐기)

**현행(폐기 대상)**: `rotate_refresh`가 `rt:active/deny/grace` + `sess:{sid}` SET +
`user:sessions:{uid}` ZSET + 5-key Lua로 **토큰 회전·재사용 탐지·패밀리 폐기**를 수행.
전부 wire되어 있고 동작하나, 이 제품엔 과설계이며 **`rt:active`가 Redis에 존재해야만 refresh가
성공** → Redis가 세션의 source of truth → **단일 홈서버에서 Redis 소실 = 전원 강제 로그아웃**
(CT112 디스크풀 배포실패 이력 환경에서 실질 리스크).

**신규(덴리스트)**:
- **발급**: access(15m) + refresh(30d, `jti` 클레임). **Redis 쓰기 0.**
- **refresh**(`POST /auth/refresh`): refresh JWT 검증(sig+exp) + `EXISTS denyjti:{jti}` →
  통과 시 **새 access**(15m) + **refresh를 슬라이딩 재민트**(S11 §D4 승인됨). 즉, 같은 `jti`·
  클레임을 유지한 채 **새 exp(now+30d)로 refresh JWT를 다시 서명**해 응답에 동봉 → 활성 사용자는
  세션 무한 연장, 30일 미사용자만 만료. **여전히 회전/패밀리 도난탐지는 없음**(jti 불변, Redis
  쓰기 0). 기존 "입력 refresh 토큰을 그대로 에코" 동작은 폐기.
- **로그아웃**(`POST /auth/logout`): `SET denyjti:{jti} 1 EX <남은 refresh TTL>`. (jti가 슬라이딩
  재민트로 유지되므로 마지막 발급 토큰의 jti 한 개만 덴리스트하면 그 세션 전체가 차단된다.)
- **탈퇴**: 현재 jti 덴리스트 + cascade 삭제(users 등) — user row 소멸로 refresh가 user 해석
  실패 → 추가 폐기 불필요(`user:sessions` ZSET 불요).
- **access 즉시차단 없음**(정직성): `get_current_user_id`는 JWT 디코드만(덴리스트 미조회).
  로그아웃 = "최대 15분 뒤 차단". 회전을 돌려도 즉시성은 안 생기므로 그 복잡도의 유일한
  순이익(refresh 도난탐지)을 이 위협모델에선 포기.
- **Redis 도달성 헬스체크/알림**(S11 §D4 승인됨): 덴리스트가 fail-open이라 Redis가 죽으면 로그아웃/
  탈퇴가 **조용한 폐기 갭**(쓰기 소실 → 차단 불가)이 된다. 이를 운영자가 인지하도록
  api `/health`에 **Redis PING**을 포함(또는 별도 probe) → 다운 시 Discord 헬스 알림(현 health 알림
  파이프 재사용). "조용한 fail-open"을 "시끄러운 알림"으로 전환.
- **탈퇴 시 Redis 다운 노출창**(명시): Redis 다운 중 탈퇴하면 `denyjti` 쓰기가 소실되어, 그 refresh
  토큰이 **최대 (Redis 다운 지속시간 + access 15분)** 동안 유효할 수 있다(user row는 cascade 삭제되어
  refresh의 user 해석은 곧 실패하므로 실효 노출은 access 잔여분에 수렴). fail-open의 의도된 트레이드오프
  이며, 위 헬스 알림으로 다운 자체를 빠르게 닫는다.
- **클라(모바일) 토큰 저장 보강**(S11 §D4 승인됨): access는 메모리 전용(현행), refresh는 SecureStore에
  `keychainAccessible: WHEN_UNLOCKED_THIS_DEVICE_ONLY`로 저장(잠금해제 시에만 접근 + 백업/타기기 동기화
  제외). **iOS 재설치 시 키체인 잔존 정리** — iOS는 앱 삭제 후에도 키체인 항목이 남으므로, 콜드 스타트
  "최초 1회" 플래그(예: `AsyncStorage`/`UserDefaults`)가 없으면 잔존 refresh를 선삭제해 유령 세션 차단.
  refresh 호출은 **single-flight**(동시 401 다발이 1회 refresh만 트리거, 결과 공유 — 현 "요청당 1회"
  규칙을 명시). 슬라이딩 재민트로 새 refresh가 돌아오므로 응답의 refresh를 항상 SecureStore에 덮어쓴다.

### 2.3 영속성 / eviction / 풀

- **영속성**: `--appendonly yes --appendfsync everysec`(최대 1초 손실) **+ RDB 스냅샷 유지**
  (`--save 60 1`). 덴리스트는 fail-open이라 치명적이진 않으나, 폐기 토큰 부활창을 1초로 좁힘.
  AOF 자동 재작성(기본 on)으로 파일 비대 방지.
- **eviction**: `--maxmemory 256mb --maxmemory-policy noeviction`. 우리 규모(스팟은 Postgres,
  Redis는 토큰+소형 캐시)에선 도달 불가. 도달 시 **조용한 토큰 손실 대신 쓰기 거부로 시끄럽게
  실패** → 인지·증설. (allkeys-lru는 인증/덴리스트 키를 evict할 수 있어 기각.)
- **풀 통합**: 현재 `redis_cache`(decode_responses=True) 싱글톤은 **오직 recommendations에서만**
  사용 → 모듈 제거 시 **고아**. 나머지(map/spots/users/related)는 전부 lifespan `_redis`
  (`RedisDep`, decode_responses=False). → **단일 풀로 통합**(`redis_cache` 제거).

---

## 3. 정적 호스팅 = Cloudflare Pages (apex `pictrip.org`)

**결정**: Cloudflare Pages. (대안 기각: FastAPI static = 공개 가용성을 홈서버 업타임·디스크에
묶고 apex 터널 라우트 추가 필요 / 앱 번들 = 스토어·OAuth가 요구하는 공개 URL 불가 / Notion =
URL 지저분·무채색 통제 불가, apex 딥링크 연결파일 호스팅 불가.)

```
pictrip.org  (Cloudflare Pages — repo의 web/ 폴더, Git 푸시 시 자동배포)
├─ /legal/terms              무채색 정적 HTML
├─ /legal/privacy
├─ /legal/location
├─ /legal/data-sources       (KTO 출처 고지 callout 포함)
├─ /.well-known/apple-app-site-association   application/json, 무확장자, 무리다이렉트
├─ /.well-known/assetlinks.json              application/json
├─ /spots/{contentId}        딥링크 타깃 = 스팟 렌더하는 웹 폴백 페이지(+스마트배너/설치버튼)
└─ /curations/{slug}         (위와 동일)
```

- **legal**: S6 D1 충족(자체도메인, 무채색, 인앱 WebView로 로드). 스토어·OAuth 정책 URL 재사용.
  **OAuth 검증 주의**: 구글은 *민감 scope* 시 정책을 소유·인증 도메인에 요구하는데, PicTrip은
  로그인 기본 scope(email·profile·openid)만 써서 해당 없음. apex 자체도메인이라 어차피 안전.
- **content-type 게이트**(S11 §D5 승인됨): AASA는 **확장자 없이** `Content-Type: application/json`
  필수 + **리다이렉트 금지**(AASA에 301/302가 끼면 OS가 검증 실패). CF Pages `_headers`로
  `/.well-known/*` MIME 강제, apex `www`→apex 301이 `/.well-known/*`를 건드리지 않도록 주의.
  **검증**: `curl -I https://pictrip.org/.well-known/apple-app-site-association` → `200` ·
  `content-type: application/json` · **no-redirect**(Location 헤더 없음) 셋을 빌드 체크리스트화.
- **웹 폴백 페이지**(S11 §D5 승인됨, 기존 "스토어 리다이렉트"에서 격상): 미설치 유저가 여는
  `pictrip.org/spots/{id}`는 단순 리다이렉트가 아니라 **스팟을 실제 렌더**(이름/대표이미지/요약)하는
  웹 폴백 페이지 — 링크가 항상 의미 있는 콘텐츠로 착지. 여기에:
  - iOS **Apple Smart App Banner** `<meta name="apple-itunes-app" content="app-id=…">`(설치 시 앱으로
    열기 / 미설치 시 App Store 안내) — UA 분기보다 OS 네이티브 동작.
  - Android **Play 설치 버튼**(intent/Play URL).
  - 이는 **deferred deep link 손실(미설치→스토어→설치→홈)** 의 최저비용 완화 — Branch 류 네이티브 SDK
    없이 "최소한 어떤 스팟이었는지"를 웹에서 보여줌. 새 네이티브 모듈 금지 규칙 준수.
  CF Pages Function 또는 정적 프리렌더로 구현(별도 인프라 아님, Pages 내장).

---

## 4. 딥링크 / 유니버설 링크

| 표면 | URL |
|---|---|
| 공유(스팟) | `https://pictrip.org/spots/{contentId}` |
| 공유(큐레이션) | `https://pictrip.org/curations/{slug}` |
| 앱 내부 스킴(라우팅용) | `pictrip://spots/{contentId}`, `pictrip://curations/{slug}` |

- **동작**: 앱 설치 시 OS가 `https://pictrip.org/{…}`를 가로채 해당 화면으로(Universal/App Links).
  미설치 시 브라우저가 URL 오픈 → §3 **웹 폴백 페이지**가 스팟을 렌더 + 스마트배너/설치버튼 노출.
- **한계(감수)**: **deferred deep link 없음** — 미설치→스토어→설치→앱은 **홈**으로(원 스팟 기억
  못 함). 그건 Branch 류 네이티브 SDK 필요인데 **새 네이티브 모듈 금지** 규칙으로 도입 안 함.
  → 웹 폴백 페이지(S11 §D5)가 "최소한 어떤 스팟이었는지는 웹에서 본다"로 이 손실을 최저비용 완화.
- **앱 설정**(네이티브 모듈 아님 — 엔타이틀먼트/매니페스트):
  - iOS: `app.json` associated domains `applinks:pictrip.org`.
  - Android: intent-filter `autoVerify=true`, host `pictrip.org`, scheme `https`.
  - 커스텀 스킴 `pictrip://`는 콜드/웜 스타트 라우팅 + 외부 진입 폴백용.
- **연결파일 입력값**: AASA = Apple Team ID + bundle id(EAS). assetlinks = 앱 서명 SHA-256
  지문(아래). 둘 다 §3 CF Pages에 정적 배치.
- **assetlinks 지문 2개 필수**(S11 §D5 승인됨 — *최대 프로덕션 버그 리스크, 체크리스트화*):
  `sha256_cert_fingerprints`에 **두 지문을 모두** 넣는다 —
  (1) **Play 앱 서명 키 SHA-256**(Play 콘솔이 재서명하는 최종 배포 인증서) +
  (2) **EAS 업로드 키 SHA-256**(EAS가 빌드 서명에 쓰는 업로드 인증서). 하나만 넣으면 특정 설치 경로에서
  App Links 자동검증이 조용히 실패해 `https://` 링크가 브라우저로 새는 대표적 프로덕션 버그.
- **AASA 패스 매칭**(S11 §D5 승인됨): **`components` 문법(iOS 17+)** 사용(레거시 `paths` 대신).
  `/spots/*`·`/curations/*`를 **둘 다 최초 빌드의 AASA에 포함** — AASA는 **설치/스토어 업데이트 때만**
  fetch되므로, 나중에 경로를 추가하려면 사용자가 앱을 업데이트해야 반영된다(빌드 후 서버에서만 고쳐도
  기존 설치에는 미적용). 따라서 가능 경로는 처음부터 다 넣는다.
- **외부 지도 딥링크는 별개**(S3 기존): 네이버/카카오 좌표 링크(`lat=mapy,lng=mapx`) +
  웹 폴백을 `Linking.openURL`로 — 우리 호스팅 무관.
- **진입 흐름**(S1): 딥링크 진입도 스플래시 hydrate 경유 후 목적지로.

---

## 5. CI/CD 정합

### 5.1 현행 유지 (실측 확인)
- **backend** `backend-deploy.yml`: main push → test(fresh `pictrip_test` + `alembic upgrade head`
  smoke + pytest) → GHCR 빌드/푸시(short-SHA + `main`) → CT112 self-hosted runner `deploy.sh`
  (`alembic upgrade head` 컨테이너 기동 시 실행, 로컬+공개 smoke, 실패 시 이전 태그 롤백).
- **mobile** `mobile-deploy.yml`: `v*` 태그/수동 → lint·typecheck·format·jest → `eas build
  --auto-submit`(Apple 자격증명은 EAS, GH엔 `EXPO_TOKEN`만).
- `backend-ci.yml`/`mobile-ci.yml` = PR 시그널, `codeql.yml`/`weekly-deep-check.yml` 유지.

### 5.2 신규 — Cloudflare Pages
- **CF 네이티브 Git 연동**(GitHub Action 불필요): repo 연결 + 프로젝트 루트 `web/`(또는 별
  디렉터리) 지정 → 푸시 시 자동 빌드/배포. 빌드 커맨드 없음(순수 정적) 또는 최소 정적 생성.
- legal HTML·`.well-known/*`·Pages Functions는 `web/`에 함께 커밋(SSOT in repo). PR 미리보기
  배포는 CF Pages 기본 제공.

### 5.3 신규 — 디스크 prune 룰화
- 현 수동 대응(디스크풀→`docker image/builder prune`)을 **CT112 주간 systemd timer**로:
  `docker image prune -af && docker builder prune -af`(주 1회). 배포 실패의 디스크풀 원인을
  사전 차단. (deploy.sh 롤백이 이전 이미지를 재pull하므로 prune은 dangling/빌더 캐시 한정 안전.)

### 5.4 시크릿 관리
- 백엔드: `.env`만(CT112 `/opt/pictrip-api/.env`, 컨테이너 read-only 마운트; deploy.sh는
  `.deploy.env`(태그 핀)만 갱신, `.env` 불가침). 코드/커밋에 시크릿 금지.
- 모바일: `EXPO_PUBLIC_*`만 노출(`EXPO_PUBLIC_API_BASE_URL=https://api.pictrip.org/v1`).
- GH Secrets: `EXPO_TOKEN`(+ `GITHUB_TOKEN` 기본). Apple 자격 = EAS.
- CF Pages: 정적이라 시크릿 없음(연결파일은 공개 정보).

---

## 6. reconcile 노트 (현 토폴로지 ↔ 신규 요구)

| 항목 | 현 상태 | 신규(S8) | 작업 위치 |
|---|---|---|---|
| 인증 Redis | 회전+도난탐지(rt:active/deny/grace, sess:, user:sessions ZSET, 5-key Lua) | `denyjti:{jti}` 단일 키 모델로 **교체** | S10 구현(auth.py + 테스트 재작성) |
| `user_auth_providers.refresh_token_enc` | 컬럼 존재 | 드롭(덴리스트 전용) | **S7 이미 결정**(마이그레이션) |
| Redis 풀 | `redis_cache`(decode=True, recommendations 전용) + lifespan `_redis` | recommendations 제거 후 `redis_cache` **고아 → 단일 풀 통합** | S10 |
| Redis 영속성 | RDB `--save 60 1`만 | **+ AOF everysec**, `noeviction` + `maxmemory 256mb` | compose 변경(S10) |
| `today-inspo` 캐시 | recommendations에 존재 | 모듈 제거와 함께 **소멸** | S10 prune |
| 정적/legal | 없음(현 `#14` 약관 stub) | **Cloudflare Pages** 신규 1컴포넌트 | 배포 작업(별 트랙) |
| 딥링크 | 없음 | Universal/App Links + 앱 엔타이틀먼트/매니페스트 | 모바일(S9 라우팅 계약 연계) |
| centroid | 없음 | 런타임 AVG → `regions:tree` 캐시 | S7 정합(무컬럼), S9 직렬화 |
| 디스크 prune | 수동 | 주간 systemd timer | 배포 작업 |
| CI/CD | backend/mobile 자동배포 | 현행 + CF Pages Git 연동 | 거의 무변경 |

**핵심**: 신규 *인프라 컴포넌트*는 Cloudflare Pages 하나. 나머지는 전부 현행 위 reconcile.
인증 단순화는 DB(S7) + 코드(S10)에서 수행되며 S1의 "덴리스트만" 잠긴 결정을 **확정**한다
(심층분석: 회전 모델은 단일 홈서버에서 fail-closed라 가용성 불리, 도난탐지 순이익은 미미).

## 7. 후속 위임
- 인증/refresh/logout **API 형식·에러코드** = S9. 딥링크 **앱 라우팅(스킴↔Expo Router)** = S9 연계.
- auth.py/풀/compose **구현 + 마이그↔코드제거 순서** = S10.
- legal Notion 안 — 기각됨(CF Pages 정적으로 확정).
