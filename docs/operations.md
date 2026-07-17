# 운영 (Operations)

> 갱신: 2026-07-17 · 워크플로/스크립트가 SSOT — 이 문서는 지도와 "왜"만 담는다.

## 토폴로지

```
Proxmox 홈서버 (pve, Tailscale 100.83.101.1)
├── CT110  PostgreSQL + pgvector  ← CT112만 라우트 보유
├── CT111  pipeline (pictrip-data CLI + Streamlit) · self-hosted 러너 [ct111]
├── CT112  api (FastAPI, :8000) + Redis (compose) + cloudflared 호스트 프로세스
│          · self-hosted 러너 [ct112] · 시크릿 /opt/pictrip-api/.env (:ro 마운트)
└── CT113  모니터링 (Prometheus + Grafana + Uptime-Kuma)

Cloudflare
├── api.pictrip.org   터널 → CT112:8000 (cloudflared는 compose 밖 호스트 프로세스가 SSOT)
├── pictrip.org       CF Pages 정적 (build root=web/, main 자동배포)
└── img.pictrip.org   Worker pictrip-img-proxy (KTO/Commons 프록시·캐시, /t1 서명 변환)
```

## 배포 레일

| 트리거 | 결과 |
|---|---|
| **dev push** | 즉시 라이브(스테이징 없음): backend→CT112 · pipeline→CT111 · mobile→EAS OTA(JS만, 네이티브 변경은 fingerprint 가드가 조용히 skip) |
| **main push** | 릴리스 마커. web(CF Pages) 빌드 · CodeQL |
| **`v*` 태그** (main에서 cut) | EAS iOS 프로덕션 빌드 + TestFlight 자동 제출 |

backend `deploy.sh`: 이미지 태그 pin(full SHA) → compose pull → up(entrypoint가
`alembic upgrade head`) → 로컬+퍼블릭 스모크 → 실패 시 **이미지 롤백만**
(마이그레이션은 forward-only — expand→contract, `docs/decisions.md`).
배포 상태 앵커 = CT112 `deploy/api-host/.deploy.env`.

## 크론 일정 (KST)

| 시각 | 잡 | 목적 |
|---|---|---|
| 매일 04:00 | pipeline `sync-daily` (CT111 systemd 타이머) | KTO→`spots` 일일 증분 동기화 |
| 매일 04:00 | `warm-channels.timer` (CT112 systemd) | festa/pets/snap 채널 캐시 예열 (배포 직후에도 `deploy.sh`가 호출) |
| 매일 04:30 | `concentration-sync.yml` | 집중률 적재 — Hot/Hidden 채널 신선도 |
| 매일 05:00 | `img-cache-warm.yml` | img.pictrip.org 엣지 워밍 — **ct111 러너 필수** (Cloudflare 캐시는 콜로 단위, 국내망에서 돌려야 KR 사용자 콜로가 데워짐) |
| 매일 06:00 | `gallery-backfill.yml` | 갤러리 centroid 임베딩 800스팟/일 — KTO 일일 쿼터(~1,000콜) 중 앱 lazy-fetch 몫 ~200콜 헤드룸을 남긴 산식 |
| 일 05:00 | `image-validate.yml` | 죽은 KTO 원본(~20%가 404) 교체/NULL. rewritten>0이면 임베딩이 `source_changed`로 큐잉됨 → `backend-backfill-embeddings` write=true 디스패치해야 매칭 복귀 |
| 월 05:00 | `docker-prune.timer` (CT112) | 디스크 풀로 배포 실패했던 사고 재발 방지 |
| 월 12:00 / 13:00 | `codeql` / `weekly-deep-check` | main 스윕 / 의존성 감사(advisory) |
| 매월 2일 03:00 | `overseas-sync.yml` | Wikidata ETL(ct111) → CLIP 임베딩(ct112) → 워밍. warm은 etl에만 needs(이미지 URL은 ETL 직후 확정) |

주의: `schedule` 워크플로는 **default 브랜치(dev) 기준**으로만 돈다 — dev 머지
후부터 유효.

## 수동 runbook

라이브 백엔드 스크립트는 새 컨테이너를 띄우지 말고 **:8000을 서빙 중인 compose
api 컨테이너에 exec** 한다 — 이미지·`.env`·CT110 라우트를 이미 가진 유일한 곳이다.

| 상황 | 명령 |
|---|---|
| admin 암호 로테이션 | `python -m scripts.set_admin_password --username admin` (시드 기본 admin/admin은 반드시 교체) |
| 임베딩 백필 | `backend-backfill-embeddings.yml` dispatch (기본 dry-run; 사전조건: api 1개·healthy·0019 적용) |
| 해외 임베딩 | `python -m scripts.embed_overseas` (overseas-sync가 자동 수행) |
| 프로드 로그 grep | `backend-logs.yml` dispatch (pattern은 env로만 전달 — 셸 인젝션 방지) |
| 소셜 로그인 거부 원인 | `backend-oidc-logs.yml` dispatch (토큰/PII 없음, 거부 사유만) |
| KTO 전체 재조정 | CT111에서 `pictrip-data sync-full` (쿼터 인지, 주간 규모) |
| 해외 설명 백필 | `pictrip-data backfill-overseas-descriptions` (ko.wikipedia intro) |
| 마스터 코드 재적재 | `pictrip-data load-codes` (부트스트랩 일회성) |
| 프로드 DB 읽기 | `ssh root@100.83.101.1` → `pct exec 110` → `docker exec pictrip-postgres psql` (직접 asyncpg 금지 — .env 암호는 local-only) |
| CT112 디스크 풀 | `pct exec 112 -- docker builder prune -af && docker image prune -af` 후 `gh run rerun --failed` |

## CI (PR 게이트)

| 워크플로 | 대상 | 비고 |
|---|---|---|
| `backend-ci` / `mobile-ci` / `pipeline-ci` / `web-ci` | 경로 필터 | web-ci는 `.well-known` JSON 유효성 — 무효 JSON은 유니버설 링크를 조용히 깨뜨림 |
| `pr-check` | PR 본문 | 템플릿 섹션·체크박스 필수 (required check) |
| `pr-review` | diff 리뷰 봇 | ct112의 codexproxy(127.0.0.1:8787) 경유 — fork PR은 미실행(임의 코드 실행 방지) |
| `admin-drift` | admin 경로 | `backend/.../admin/static/` ↔ `admin/mockups/` 바이트 동일성 |

## 시크릿 위치 (값은 어디에도 커밋 금지)

| 위치 | 내용 |
|---|---|
| CT112 `/opt/pictrip-api/.env` | 백엔드 전체 (KTO·Kakao·Sentry·DB·Redis·`GITHUB_DISPATCH_TOKEN`) — 수정 후 `docker restart` |
| CT111 `.../pipeline/.env` | `DATABASE_URL`·`KTO_API_KEY` (배포 rsync가 보존) |
| GitHub Actions | `EXPO_TOKEN`; `pipeline-sync`용 `KTO_SERVICE_KEY`·`DATABASE_URL`은 **미주입(A7 보류)** |
| Wrangler | `T1_SECRET` (img-proxy 서명 — 백엔드 .env와 미러) |
| EAS `eas.json` | `EXPO_PUBLIC_*` (Kakao·Google 클라이언트 키) |

admin 콘솔 인증은 env가 아니라 **`admin_users` DB 테이블** — 로테이션에 CT112
접근 불필요.

## 모바일 배포 함정 (사고 이력에서 승격)

- **OTA에 `EXPO_PUBLIC_*` 주입 필수** — `eas.json`의 env는 `eas build`에만 적용되고
  `eas update`는 러너 env로 번들한다. 주입 스텝이 빠지면 빈 키 OTA가 정상 스토어
  빌드를 덮어써 Kakao/Google 로그인이 전멸한다 (`mobile-ota.yml`에 배선됨).
- **네이티브 변경은 `v*` 태그로만 나간다** — OTA fingerprint 가드가 네이티브 지문
  불일치 빌드를 조용히 skip한다. 모듈/권한/SDK 변경 후 OTA만 하면 아무 일도 안 일어난다.
- 모바일 API 베이스는 `EXPO_PUBLIC_API_BASE_URL` 미인라인 시 env.ts 폴백을 쓴다 —
  폴백에 `/v1`이 빠지면 전 화면 404 (v0.4.1 사고).

## 미배선 / 보류

- `pipeline-sync.yml` (admin "수집 즉시 실행" 버튼 타깃) — **A7 결정 보류**. 발화
  조건: repo 시크릿 2종 주입 + 백엔드 `GITHUB_DISPATCH_TOKEN`. 그 전까지 스케줄
  경로는 CT111 04:00 타이머가 유일(이중 실행 방지).
