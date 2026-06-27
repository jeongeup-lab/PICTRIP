# A1 — 관리자 콘솔 설계 (데이터 수집 운영 어드민)

> 입력 SSOT: 목업 `admin/mockups/`(3페이지 + `assets/`), 루트 `CLAUDE.md`
> (Conventions·Prohibitions·DB facts), **현 백엔드 코드 + 홈서버 인프라(실측)** —
> `backend/app/modules/*`, `app/core/{schemas,exceptions,db,redis}.py`,
> juns `pictrip-data`(CT111: `sync/audit.py`·`sync/daily.py`·`dashboard/`).
> 설계 철학: 신규 백지 아님. **공용 prod DB(CT110)를 그대로 읽는 조회 전용 어드민**을
> 먼저 세우고, 외부 의존(트리거)만 뒤에 붙인다. 목업이 UI SSOT.

이 세션에서 crosscheck로 확정한 사실(코드/인프라 권위):

- **juns 파이프라인은 백엔드와 같은 DB에 쓴다.** juns `.env` `DATABASE_URL=…@100.123.189.120:5432/pictrip`
  = CT110의 그 `pictrip` DB. → `spots`·`sync_runs` 둘 다 **백엔드가 이미 붙는 DB에 존재**, 그냥 읽으면 됨.
- **`sync_runs` 스키마(실측, `sync/audit.py`):** `id · started_at · finished_at ·
  status(running|success|error) · mode · watermark_from · watermark_to · api_calls ·
  fetched · inserted · updated · soft_deleted · skipped · duration_sec · error(text)`.
  인덱스 `idx_sync_runs_recent (id DESC)`.
- **전체 stdout 로그 컬럼은 없다.** 영속되는 상세는 `error` 텍스트 + 집계 컬럼뿐.
- **수집 본체는 juns CLI**(`pictrip-data sync-daily` 등)로 존재하고, juns는 이미 CT111에
  Streamlit 대시보드(:8501, tailnet)를 운영 중. 본 어드민은 그와 **역할 분리**: juns=파이프라인
  내부 도구, 본 어드민=서비스 측 운영 + spots 수집 표면(앱 헬스는 juns가 안 봄).

백엔드 코드 측 crosscheck(실측):

- **설정 모듈 = `app/config.py`** (`Settings(BaseSettings)`, `env_file=".env"`) — `app/core/`가 아님.
  → `ADMIN_PASSWORD`는 여기 추가. KTO/Kakao 키도 전부 여기 패턴.
- **JSend** `ok()`/`err()`·`Envelope`·`ResponseMeta`·`ErrorPayload` = `app/core/schemas.py` 실재. ✓
- **`AppError`**(`app/core/exceptions.py`) = 베이스에 `code:str`·`http_status:int`, 서브클래스가 둘을 지정.
  → 어드민 전용 코드(§3)는 동일 패턴으로 서브클래싱. ✓
- **루트 `/health`**(`@app.get("/health", include_in_schema=False)`, "outside /v1 — used by ALB") 실재.
  → 어드민 헬스 `/admin/api/health`와 별개. ✓
- **`StaticFiles` 현재 미사용**(어떤 mount도 없음) → `/admin` 정적 서빙은 신규 와이어링.
- **alembic `env.py`에 `include_object` 필터 없음**(`target_metadata=Base.metadata`, `compare_type=True`)
  → A5대로 `sync_runs`는 **Base 밖**(raw SQL/비등록 Table)으로 두는 게 env.py 무수정으로 가장 안전.
- **DB 풀**(`app/core/db.py`) `pool_size=20`·`pool_pre_ping`·asyncpg `server_settings hnsw.ef_search=80`
  → 헬스 `db.poolSize=20`, `poolInUse=engine.pool.checkedout()`로 산출.
- **카카오 수** = `user_auth_providers.provider='kakao'`(CHECK `IN ('kakao','google','apple','email')`).
  활성=`users.deleted_at IS NULL`, 신규=`created_at`, 탈퇴=`deleted_at`. ✓
- **`/meta/version`** = `{apiVersion,environment,ktoApiStatus}` 반환(uptime·p95 없음) → 헬스의 uptime/p95는 신규.
- ⚠️ main.py에 `recommendations`·`courses` 라우터 **아직 포함**(CLAUDE.md 제거 대상이나 미제거) — 어드민과 무관, FYI.

---

## 0. 요약 (확정 결정)

| # | 결정 | 근거 |
|---|---|---|
| A1 | **스코프 = KTO 수집 ①(spots, `areaBasedSyncList2`) 1개만** | KTO 수집 대상은 4개(spots·상세·이미지·마스터)지만 매일 도는 건 spots뿐. 상세·이미지는 백엔드 lazy 캐시, 마스터는 1회성 → 어드민 관리 대상 아님 |
| A2 | **3페이지** = 수집 현황(+트리거) · 수집 이력 · 서비스 헬스 | 목업 SSOT. 트리거(B)는 버튼 1개라 현황 페이지의 주 액션으로 통합 |
| A3 | **서빙 = FastAPI 내장.** `/admin`에 정적 HTML 3장 + `/admin/api/*` JSON | 별도 빌드·배포 0. React 미사용(단일 HTML+fetch). 모바일 `/v1`과 분리된 내부 표면 |
| A4 | **인증 = `ADMIN_PASSWORD`(env) + HTTP Basic**, `/admin/*` 전체 | role/권한 테이블 신설 과함(솔로 운영). CF로 공개되므로 Basic 필수 |
| A5 | **`sync_runs`는 read-only foreign 테이블로만 접근** | juns 소유(`CREATE TABLE IF NOT EXISTS`, 백엔드 alembic 밖). 백엔드 모델/마이그레이션에 넣지 않음 → 스키마 소유권 충돌 방지 |
| A6 | **상세 로그 = run 요약 + `error`** (raw stdout 아님) | DB에 로그 컬럼 없음. 전체 로그가 필요해지면 juns가 적재 추가(차기) |
| A7 | **트리거 메커니즘 미정 → 어댑터로 격리** | `workflow_dispatch` vs CT111 Tailscale HTTP는 juns 협의. 인터페이스 `trigger(job)->run_id`만 고정, 구현체 교체 가능 |
| A8 | **단계화: Phase 1(조회 전용) 단독 선출시** | 현황·이력·헬스는 공용 DB 읽기 + 백엔드 내부값 = 0 외부의존. 트리거만 Phase 2 |
| A9 | **홈 큐레이션 편집기 채택 — read-write 확장** (2026-06-21, 사용자 승인) | A01 본래 "콘텐츠 큐레이션=비목표"·어드민 read-only 결정을 뒤집음. 홈 편성(히어로6+무드레일3)을 앱 재배포 없이 편집/발행. `curations`/`curation_spots`에 한정한 **스코프된 쓰기**(그 외 표면은 read-only 유지). Phase 4. → §7, 목업 `admin/mockups/curation.html`(B안), 요구사항 ADM-012~018 |

**미정(blocking은 트리거뿐):** A7 트리거 메커니즘.
**제외(스코프 밖):** 데이터 품질/커버리지 패널, Redis ping·`rlte:*` 카운트, 취향벡터 보유,
다른 KTO 수집/가공(상세·이미지·마스터·임베딩·무드) 트리거, 회원 관리.
(콘텐츠 큐레이션은 2026-06-21 채택으로 스코프에 편입 → A9·§7.)

---

## 1. 아키텍처

### 1.1 모듈 배치

현 모듈 레이아웃(`routes`/`services`/`schemas`, repo는 spots만)을 따른다. 어드민은
여러 모듈을 가로질러 **읽기만** 하므로, cross-module read의 예외로 **read-only 집계
repo**를 어드민 모듈 안에 둔다(쓰기 없음, 다른 모듈 `models` 직접 import 금지 원칙은
유지하되 집계 쿼리는 raw SQL/read 모델로).

**예외 — Phase 4 큐레이션 편집기(A9·§7):** `curations`/`curation_spots`에 한정한
**쓰기**를 도입한다(트랜잭션 경계는 `admin/services.py`). 이 두 테이블은 어드민이
소유 도메인으로 직접 다루며, 그 외 표면(spots·sync_runs·users 집계 등)은 read-only 유지.

```
app/modules/admin/
├── routes.py        HTTP I/O — /admin (HTML) + /admin/api/* (JSON). 비즈로직 없음
├── services.py      집계·헬스 프로브·트리거 오케스트레이션
├── repositories.py  read-only 집계 쿼리 (spots·sync_runs·users). SQLAlchemy/raw SQL
├── schemas.py       Pydantic DTO (JSend data 페이로드)
├── security.py      ADMIN_PASSWORD HTTP Basic 의존성
├── triggers.py      트리거 어댑터 인터페이스 + 구현체(Phase 2)
└── static/          목업 HTML 3장 + assets/ (UI SSOT 복사본 또는 심볼릭 소스)
```

### 1.2 라우팅 / 서빙

- `GET /admin` → `index.html`(수집 현황). `/admin/history`·`/admin/health`는 정적 파일 또는
  `FileResponse`. 정적 자산은 `StaticFiles`로 `/admin/assets/*`.
- API는 `/admin/api/*` — **`/v1` 프리픽스 밖**(내부 도구, 모바일 계약과 분리; A3).
- 루트 `/health`(ALB/liveness, `include_in_schema=False`)와 **혼동 금지**: 어드민 헬스는
  `/admin/api/health`(인증 필요, 풍부한 컴포넌트 상태).

### 1.3 인증 (A4)

> **🔄 2026-06-27 변경(사용자·친구 합의): 인증을 env(`ADMIN_PASSWORD`)에서 DB 테이블로 이관.**
> 근거: 자격증명이 CT112 `.env`에 살면 설정/로테이션에 CT112 셸 접근이 필요한데
> 그 경로가 막힘(CT112 비-tailnet + lss:22 ACL 차단). 자격증명을 **공용 CT110 DB**의
> `admin_users` 테이블에 두면 로컬·프로덕션이 같은 DB를 읽어 **CT112 무접근으로 프로비저닝**.
> 배포는 normal push-to-main(컨테이너 기동 시 `alembic upgrade head`가 시드)로 완료.
> 아래 env 기반 서술은 마이그레이션 0016 이전 설계로 **superseded**.

- **현행:** `admin_users(username PK, password_hash, created_at, updated_at)` 테이블.
  `app/modules/admin/security.py`가 username 조회 + bcrypt `verify_password`로 검증.
  마이그레이션 0016이 `admin`/`admin` 시드(약한 기본값 — `scripts/set_admin_password.py`로 로테이션).
  자격증명 없음/오류 → `401 WWW-Authenticate: Basic`(503 잠금 개념 폐지).
- HTTP Basic 의존성을 `/admin` HTML + `/admin/api/*` 전 라우트에 적용(공개 경로라 Basic 필수).
- ⚠️ 보안: `/admin`은 CF 터널로 공개되고 홈 큐레이션 **쓰기** 권한이 있음. `admin`/`admin`은
  데모용 약한 기본값 — 실사용 전 강한 비번 로테이션 또는 A9 CF Access 게이트 권장.
- ~~(superseded) env `ADMIN_PASSWORD` 미설정 시 503, username 고정 `admin`, `secrets.compare_digest`.~~

### 1.4 응답 규약

- `/admin/api/*`도 모바일과 동일하게 **JSend 엔벨로프**(`ok()`/`err()`, `app/core/schemas.py`)
  사용 — 프론트 fetch가 `data`만 읽도록. 오류는 `AppError` 분류(어드민 전용 코드는 §4).

---

## 2. 페이지 ↔ 데이터 매핑

### 2.1 수집 현황 (`index.html`)

데이터 소스 가로줄(현재 1행 = 국문 관광정보 서비스) + "다시 업데이트" 트리거.

| 화면 필드 | 출처 |
|---|---|
| 데이터 소스명 / 엔드포인트 | 정적 라벨 `국문 관광정보 서비스` · `areaBasedSyncList2 → spots` |
| 실행 시간 (절대 + 상대) | `sync_runs` 최신 `finished_at`(없으면 `started_at`) |
| API 호출 | 최신 run `api_calls` |
| 추가 / 수정 / 숨김 | 최신 run `inserted` / `updated` / `soft_deleted` |
| 소요 | 최신 run `duration_sec` |
| 상태 아이콘 (완료/실패/실행중) | 최신 run `status` |
| 총 수집 건수 | `SELECT count(*) FROM spots` |
| 다음 자동 실행 | 정적("내일 04:00") 또는 차기 스케줄 메타 |

엔드포인트 **`GET /admin/api/collection`**.

### 2.2 수집 이력 (`history.html`)

날짜별 성공/실패 집계 목록 → 행 클릭 시 상세 로그 모달.

| 화면 필드 | 출처 |
|---|---|
| 날짜 (오늘/어제 라벨) | `sync_runs` `date(started_at)` 그룹 |
| 성공 N / 실패 N | `status='success'` / `status='error'` 카운트 |
| run 수 / 재시도 표시 | 그룹 내 row 수 |
| 상세 로그 (모달) | 해당 일자 run들의 요약(`mode·api_calls·ins/upd/del·duration_sec`) + `error`(A6) |

엔드포인트 **`GET /admin/api/history`**(목록) · **`GET /admin/api/history/{date}`**(상세).

### 2.3 서비스 헬스 (`health.html`)

앱/서비스 측 운영 상태(파이프라인 아님).

| 화면 필드 | 출처 |
|---|---|
| API 버전·uptime·p95 | 앱 내부(`/meta/version` 로직 + 프로세스 시작시각). p95는 차기(미들웨어 집계) — 초기엔 생략/정적 |
| PostgreSQL 연결·pool·spots 수 | `SELECT 1` ping + 풀 stats + `count(spots)` |
| Cloudflare 터널 | 터널 헬스 체크(차기) — 초기엔 정적/생략 가능 |
| 가입자: 총/활성/신규(7d)/탈퇴(30d)/카카오 | `users` 집계(`deleted_at`·`created_at`·auth provider) |
| API 응답시간 24h 차트 | 차기(미들웨어 메트릭) — 초기엔 생략 |

엔드포인트 **`GET /admin/api/health`**. **제외:** Redis ping·`rlte:*`·취향벡터 보유(§0 요약).

---

## 3. API 계약 (JSend `data` 페이로드)

> 전부 `/admin/api/*`, Basic 인증 필요, `{ data, error, meta }` 엔벨로프. 아래는 `data`만.

```
GET /admin/api/collection
CollectionStatus {
  totalSpots: int,
  source: {
    name: "국문 관광정보 서비스",
    endpoint: "areaBasedSyncList2",
    lastRun: {
      status: "success"|"error"|"running"|null,
      finishedAt: datetime|null, ranAt: datetime,
      apiCalls: int, inserted: int, updated: int, softDeleted: int,
      durationSec: float|null
    } | null
  },
  nextScheduledAt: datetime|null
}

GET /admin/api/history?days=7
HistoryList { days: [ {
  date: "2026-06-18", success: int, error: int, running: int, runs: int
} ] }

GET /admin/api/history/{date}        # date = YYYY-MM-DD
HistoryDetail { date: str, runs: [ {
  id: int, status: str, mode: str,
  startedAt: datetime, finishedAt: datetime|null,
  apiCalls: int, inserted: int, updated: int, softDeleted: int,
  durationSec: float|null, error: str|null
} ] }

GET /admin/api/health
Health {
  api:   { version: str, uptimeSec: int, p95Ms: float|null },
  db:    { ok: bool, poolInUse: int, poolSize: int, spots: int },
  tunnel:{ ok: bool|null, detail: str|null },        # 차기, 초기 null
  users: { total: int, active: int, new7d: int, deleted30d: int, kakao: int }
}

POST /admin/api/collection/trigger   # Phase 2
TriggerResult { job: "sync-daily", runId: str|null, accepted: bool }
```

오류 코드(어드민 전용, `AppError` 확장): `ADMIN_UNAUTHORIZED(401)` ·
`ADMIN_TRIGGER_FAILED(502)`(Phase 2) · `ADMIN_HISTORY_NOT_FOUND(404)`.

---

## 4. `sync_runs` read-only 접근 (A5)

- juns가 `CREATE TABLE IF NOT EXISTS`로 만든 테이블 → 백엔드 alembic이 관리하지 않음.
  autogenerate가 이 테이블을 "drop 대상"으로 보지 않도록 **alembic `include_object`에서
  `sync_runs` 제외** 또는 read 모델을 `__table_args__={"info":{"skip_autogen":True}}` 처리.
- 접근은 raw SQL(`text()`) 또는 `Base` 밖의 read-only 매핑. 컬럼명은 위 실측 그대로.
- 컬럼 계약은 juns와 공유(이름 변경 시 양쪽 깨짐) — PR 설명에 의존성 명시.

---

## 5. 단계화

### Phase 1 — 조회 전용 어드민 (단독, 외부의존 0)
1. `admin` 모듈 + `ADMIN_PASSWORD` Basic 인증 + 정적 3페이지 서빙
2. `GET /admin/api/collection` · `/history` · `/history/{date}` · `/health`
3. `sync_runs` read-only 접근(§4) + `spots`/`users` 집계
4. 목업 하드코딩 → fetch 교체, 로딩/에러/자동새로고침
5. 트리거 버튼 = "준비 중" stub(honest-minimal)
6. pytest(`POSTGRES_DB=pictrip_test`) — 인증 게이트·집계·날짜그룹·헬스

### Phase 2 — 트리거 (juns 협의 후)
7. A7 메커니즘 확정 → `triggers.py` 구현체(workflow_dispatch: PAT+pipeline 워크플로 /
   Tailscale HTTP: CT111 얇은 리스너)
8. `POST /admin/api/collection/trigger` + 버튼 활성 + 폴링으로 running→완료 반영

### Phase 3 — 배포
9. `ADMIN_PASSWORD` → CT112 `.env`. `/admin`이 CF 터널로 공개 → Basic 필수(또는 CF Access
   추가). 기존 push-to-main 자동배포에 포함.

### Phase 4 — 홈 큐레이션 편집기 (read-write 확장, A9 / §7)
10. 어드민 write 도입: 큐레이션 목록·상세·편집(PUT)·손픽 스팟·어드민 스팟 검색 API
    (ADM-012~015) + 발행 시 BE-HOME-003 캐시 무효화 재사용 + 변경 audit(ADM-016).
11. 편집 화면 = 목업 `curation.html`(B안: 편성 미리보기 + 편집) fetch 연결(ADM-017).
12. pytest(`POSTGRES_DB=pictrip_test`) — 편집·손픽·검색·발행 무효화·권한(ADM-018).

---

## 6. reconcile 메모 / 리스크

- **중복 우려:** juns Streamlit이 수집 현황·이력을 이미 봄. 본 어드민은 *서비스 측 헬스 +
  spots 수집 표면*으로 차별. 수집 모니터링이 완전히 겹치면 Phase 1에서 현황/이력을 juns
  대시보드 링크로 대체하는 선택지도 가능(미결, 운영하며 판단).
- **p95·터널·24h 차트**는 현재 백엔드가 메트릭을 집계하지 않음 → 초기엔 정적/생략, 차기
  미들웨어로 보강(스코프 크리프 방지).
- **로그 한계(A6):** 실패 원인 추적이 `error` 텍스트로 제한. 부족하면 juns가 run 로그를
  `sync_runs`에 적재(또는 별 테이블)하도록 협의.

---

## 7. 홈 큐레이션 편집기 (Phase 4 — read-write 확장, 2026-06-21 채택)

> A01 본래 결정(콘텐츠 큐레이션=비목표 · 어드민 read-only)을 **사용자 승인으로 뒤집은**
> 확장. 근거: 홈은 백엔드 주도 설계(잠긴 결정 2)라 *편성 교체에 앱 재배포가 필요 없도록*
> 의도됨 — 현재는 시드 스크립트 수정(개발자 작업)이 유일 경로이고, 편집기가 그 마지막 조각.
> UI SSOT = `admin/mockups/curation.html`(B안: 편성 미리보기 우선).
> 작업 분해 = `docs/requirements/dev-requirements.md`(ADM-012~018).

- **스코프된 쓰기:** `curations`·`curation_spots`에 한정. 그 외 어드민 표면(spots·sync_runs·
  users 집계)은 read-only 유지. 쓰기 트랜잭션 경계는 `admin/services.py`. 큐레이션은 어드민이
  소유 도메인으로 직접 다룬다(taste/spots 등 타 모듈은 계속 read 전용 집계).
- **편집 대상:** 히어로 6(region) + 무드 레일 3(mood). 카피(제목 `\n` 원문 유지·부제·리드·
  소개), 표지 스팟(**KTO URL 참조만 — 다운로드·저장 금지**), 발행 여부, 노출 순서, 손픽
  스팟(≤8, 순서). 손픽을 비우면 BE-HOME-003 품질게이트 랭킹으로 자동 채움(덮어쓰기 아님).
- **API(신규, `/admin/api/`):**
  - `GET  /admin/api/curations` — 히어로6 + 레일3 목록(발행 상태 포함)
  - `GET  /admin/api/curations/{id}` — 카피·표지·손픽 스팟 상세
  - `PUT  /admin/api/curations/{id}` — 카피·표지·발행·순서 수정(타입↔스코프 CHECK 검증)
  - `PUT  /admin/api/curations/{id}/spots` — 손픽 스팟 순서 set(`curation_spots` 교체)
  - `GET  /admin/api/spots/search?q=&region=` — 어드민 전용 스팟 피커(공개 `/spots/search`
    비목표와 별개의 내부 검색; 응답=content_id·이름·대표이미지·지역 최소 필드)
- **발행 일관성:** 저장/발행 시 BE-HOME-003 `on-publish 즉시 DEL` 무효화를 재사용 → 앱 홈에
  즉시 반영. 모든 쓰기에 변경 audit 1줄(누가·언제·무엇·발행 여부, ADM-010 패턴).
- **인증:** 기존 A4(Basic) + A9 배포의 CF Access 게이트로 보호. write도 동일 게이트.
- **여전히 비목표:** 회원 관리, 큐레이션 신규 타입/스키마 변경, editorial 큐레이션 자동 생성.
