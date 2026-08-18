# 크론·워크플로 레퍼런스

> 자동화 일정·워크플로·시크릿 위치의 조회용 표. 정본은 `.github/workflows/`와
> CT112 systemd 타이머.

## 토폴로지

```
Proxmox (pve, Tailscale 100.83.101.1)
├── CT110  PostgreSQL+pgvector          ← CT112만 라우트 보유
├── CT111  pipeline · 러너 [ct111] · Uptime-Kuma(:3001, tailnet 전용)
├── CT112  api+Redis(compose) · cloudflared(호스트 프로세스) · 러너 [ct112]
└── CT113  (미생성 — Prometheus·Grafana 는 Phase 3)
Cloudflare: api.pictrip.org(터널) · pictrip.org(Pages, root=web/, main) · img.pictrip.org(Worker)
```

배포 레일: **dev 머지 = 라이브**(backend→CT112 · pipeline→CT111 · mobile→OTA),
main = 릴리스 마커(web·CodeQL), `v*` 태그 = TestFlight(→
[deploy-and-release](../how-to/deploy-and-release.md)).

## 수집 DAG (KST)

`schedule`은 **default 브랜치(dev) 기준**으로만 돈다. 수집 잡은 시각 크론으로
흩어놓지 않고 주기별 DAG 3개에 `needs:` 로 묶는다 — 워밍은 원인 잡 뒤에, 재임베딩은
데이터가 바뀐 잡 뒤에 붙어야 의미가 있다.

정각(`0 * * * *`)을 피해 `:07`·`:13`·`:23` 에 건다. 스케줄 디스패치는 GitHub 이
큐잉하고 정각은 전 세계 크론이 몰려 지연된다 — self-hosted 러너라도 트리거는 큐를 탄다.

| 잡 | 시각 | DAG |
|---|---|---|
| `pipeline-daily.yml` | 매일 04:07 | `sync-kto` → {`concentration`, `detail-prewarm`, `embed`} → `warm` → `heartbeat` |
| `pipeline-weekly.yml` | 일요일 04:23 | `sync-full` → {`image-validate` → {`embed-repair`, `gallery-repair`}, `signals`} → `heartbeat` |
| `pipeline-monthly.yml` | 매월 2일 03:13 | `overseas-etl` → {`embed`, `warm`} → `heartbeat` |

- **`embed`가 `sync-kto`에 연쇄하는 것이 핵심.** 신규 스팟은 `UPDATE OF
  first_image_url` 트리거에 안 걸려 `embedding_failures` 에도 안 쌓인다 — 이 링크가
  없으면 새 KTO 스팟이 이미지 검색·매칭에서 영영 누락된다.
- **증분은 워터마크 날짜부터 오늘까지 하루씩 훑는다.** KTO `modifiedtime` 은 하한이
  아니라 그 날짜만 고르는 필터라, 하루치만 요청하면 워터마크가 그 날에 갇힌다
  (2026-06-26 부터 54일간 실제로 그랬다 — `fetched=10 · skipped=10` 이 매일 success 로 기록).
- **`sync-full`이 유일한 soft-delete 경로.** 일일 증분은 `modifiedtime` 필터라
  "사라진 스팟"을 못 본다. 응답이 현재 노출분의 절반 미만이면 `PartialFullSync` 로
  중단한다(부분 응답이 전체를 숨기는 사고 방지).
- 임베딩 잡 3종은 `admin:embed:running` Redis 락을 공유하므로 job-level
  `concurrency: embedding-job` 으로 워크플로를 가로질러 직렬화한다.
- `heartbeat` 는 **CT111** Uptime-Kuma push 모니터를 때린다(→ [monitoring](../../deploy/monitoring/README.md)). 잡 실패뿐 아니라 **"아예
  안 돌았음"**(GitHub 장애·60일 무활동 시 스케줄 자동 비활성)까지 Kuma 타임아웃으로
  잡힌다. 푸시 URL 시크릿이 없으면 조용히 건너뛴다.

### 그 밖의 타이머 (CT112 systemd)

| 시각 | 잡 | 목적 |
|---|---|---|
| 매일 04:00 | `warm-channels.timer` | 채널 캐시 예열 (배포 직후에도 `deploy.sh`가 호출) |
| 월 05:00 | `docker-prune.timer` | 디스크 풀 배포 실패 재발 방지 |
| 월 12:00 / 13:00 | `codeql` / `weekly-deep-check` | main 스윕 / 의존성 감사(advisory) |

> CT111 의 `pictrip-sync-v2.timer` 는 **은퇴** — 일일 수집은 `pipeline-daily.yml`
> 이 쥔다. 이관 시 CT111 에서 `systemctl disable --now pictrip-sync-v2.timer`.

## 워크플로

| 파일 | 트리거 | 요지 | 러너 |
|---|---|---|---|
| `pipeline-daily` / `-weekly` / `-monthly` | schedule + dispatch | 수집 DAG (위 표) | ct111+ct112 |
| `img-cache-warm` | `workflow_call` + dispatch | 엣지 워밍 — **ct111 러너 필수**(CF 캐시는 콜로 단위, 국내망이어야 KR 콜로가 데워짐). 자체 스케줄 없음 | ct111 |
| `backend-ci` / `mobile-ci` / `pipeline-ci` / `web-ci` | PR (경로) | 유닛별 게이트. web-ci=`.well-known` JSON 유효성(무효 JSON은 딥링크를 조용히 깨뜨림) | ubuntu |
| `pr-check` | PR 본문 | 템플릿 섹션·체크박스 (required) | ubuntu |
| `backend-deploy` | push dev | test → GHCR → CT112 `deploy.sh` | ubuntu+ct112 |
| `pipeline-deploy` | push dev | rsync(`.env`·`.venv` 보존) — 다음 DAG 실행이 새 코드를 쓴다 | ct111 |
| `mobile-ota` | push dev | EAS Update — `EXPO_PUBLIC_*` 주입 스텝 필수(빠지면 로그인 전멸 OTA) | ubuntu |
| `mobile-deploy` | tag `v*` | EAS iOS 빌드 + TestFlight 제출 | ubuntu |
| `backend-backfill-embeddings` / `-nicknames` | manual | 라이브 컨테이너 exec 백필 (기본 dry-run) | ct112 |
| `backend-logs` / `backend-oidc-logs` | manual | 원격 로그 grep / OIDC 거부 사유 | ct112 |
| `agent-detail-coverage` | manual | `spot_details` 커버리지 실측 (읽기 전용, KTO 콜 0) | ct112 |

### 공통 액션

| 액션 | 용도 |
|---|---|
| `.github/actions/api-exec` | `:8000` 서빙 중인 라이브 api 컨테이너에서 `python -m <module>` 실행 (CT110 경로·`.env`·CLIP 이미지를 가진 유일한 곳) |
| `.github/actions/heartbeat` | Uptime-Kuma push 보고. URL 시크릿 없으면 no-op |

## 시크릿 위치 (값 커밋 금지)

| 위치 | 내용 |
|---|---|
| CT112 `/opt/pictrip-api/.env` (:ro 마운트) | 백엔드 전체 — 수정 후 `docker restart` |
| CT111 `.../pipeline/.env` | `DATABASE_URL` · `KTO_API_KEY` |
| GitHub Actions | `EXPO_TOKEN`; `KUMA_PUSH_PIPELINE_{DAILY,WEEKLY}`(미주입 시 heartbeat no-op) |
| Wrangler | `T1_SECRET` (백엔드 .env와 미러) |
| EAS `eas.json` | `EXPO_PUBLIC_*` (Kakao·Google 키) |

admin 콘솔 인증은 env가 아니라 `admin_users` 테이블(→
[inspect-prod](../how-to/inspect-prod.md)).

---
관련: [deploy-and-release](../how-to/deploy-and-release.md) · [operate-embeddings](../how-to/operate-embeddings.md) · [cli](cli.md)
