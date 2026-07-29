# 크론·워크플로 레퍼런스

> 자동화 일정·워크플로·시크릿 위치의 조회용 표. 정본은 `.github/workflows/`와
> CT111/CT112 systemd 타이머.

## 토폴로지

```
Proxmox (pve, Tailscale 100.83.101.1)
├── CT110  PostgreSQL+pgvector          ← CT112만 라우트 보유
├── CT111  pipeline · 러너 [ct111]
├── CT112  api+Redis(compose) · cloudflared(호스트 프로세스) · 러너 [ct112]
└── CT113  Prometheus·Grafana·Uptime-Kuma
Cloudflare: api.pictrip.org(터널) · pictrip.org(Pages, root=web/, main) · img.pictrip.org(Worker)
```

배포 레일: **dev 머지 = 라이브**(backend→CT112 · pipeline→CT111 · mobile→OTA),
main = 릴리스 마커(web·CodeQL), `v*` 태그 = TestFlight(→
[deploy-and-release](../how-to/deploy-and-release.md)).

## 크론 일정 (KST)

`schedule`은 **default 브랜치(dev) 기준**으로만 돈다.

| 시각 | 잡 | 목적 |
|---|---|---|
| 매일 04:00 | pipeline `sync-daily` (CT111 타이머) | KTO → `spots` 증분 동기화 |
| 매일 04:00 | `warm-channels.timer` (CT112) | 채널 캐시 예열 (배포 직후에도 `deploy.sh`가 호출) |
| 매일 04:30 | `concentration-sync.yml` | 집중률 적재 (Hot/Hidden 신선도) |
| 매일 05:00 | `img-cache-warm.yml` | 엣지 워밍 — **ct111 러너 필수**(CF 캐시는 콜로 단위, 국내망이어야 KR 콜로가 데워짐) |
| 매일 06:00 | `gallery-backfill.yml` | 갤러리 centroid 800스팟/일 (KTO 쿼터 ~1k 중 앱 몫 ~200콜 헤드룸 산식) |
| 일 05:00 | `image-validate.yml` | 죽은 KTO 원본 교체/NULL — rewritten>0이면 재임베딩 후속 필수(→ [operate-embeddings](../how-to/operate-embeddings.md)) |
| 월 05:00 | `docker-prune.timer` (CT112) | 디스크 풀 배포 실패 재발 방지 |
| 월 12:00 / 13:00 | `codeql` / `weekly-deep-check` | main 스윕 / 의존성 감사(advisory) |
| 매월 2일 03:00 | `overseas-sync.yml` | Wikidata ETL(ct111) → 임베딩(ct112) → 워밍 |

## 워크플로

| 파일 | 트리거 | 요지 | 러너 |
|---|---|---|---|
| `backend-ci` / `mobile-ci` / `pipeline-ci` / `web-ci` | PR (경로) | 유닛별 게이트. web-ci=`.well-known` JSON 유효성(무효 JSON은 딥링크를 조용히 깨뜨림) | ubuntu |
| `pr-check` | PR 본문 | 템플릿 섹션·체크박스 (required) | ubuntu |
| `backend-deploy` | push dev | test → GHCR → CT112 `deploy.sh` | ubuntu+ct112 |
| `pipeline-deploy` | push dev | rsync(`.env`·`.venv` 보존) + 타이머가 다음 발화 때 픽업 | ct111 |
| `mobile-ota` | push dev | EAS Update — `EXPO_PUBLIC_*` 주입 스텝 필수(빠지면 로그인 전멸 OTA) | ubuntu |
| `mobile-deploy` | tag `v*` | EAS iOS 빌드 + TestFlight 제출 | ubuntu |
| `backend-backfill-embeddings` / `-nicknames` | manual | 라이브 컨테이너 exec 백필 (기본 dry-run) | ct112 |
| `backend-logs` / `backend-oidc-logs` | manual | 원격 로그 grep / OIDC 거부 사유 | ct112 |
| `agent-intent-eval` | manual | 골든셋 61건으로 의도 추출 채점 (모델 비교용, 읽기 전용) — 키가 CT112에만 있어 로컬 실행 불가 | ct112 |
| `overseas-backfill-thumbs` | manual | Commons 썸네일 직접 URL 재작성 | ct111 |
| `pipeline-sync` ⚠️ | manual only | admin 수집 버튼 타깃 — **미배선(A7 보류)**: 시크릿 2종 + `GITHUB_DISPATCH_TOKEN` 필요 | ct112 |

## 시크릿 위치 (값 커밋 금지)

| 위치 | 내용 |
|---|---|
| CT112 `/opt/pictrip-api/.env` (:ro 마운트) | 백엔드 전체 — 수정 후 `docker restart`. `CEREBRAS_API_KEY`가 없으면 LLM 폴백은 꺼진 채로 Gemini 단독 동작 |
| CT111 `.../pipeline/.env` | `DATABASE_URL` · `KTO_API_KEY` |
| GitHub Actions | `EXPO_TOKEN`; `pipeline-sync`용 2종은 미주입 |
| Wrangler | `T1_SECRET` (백엔드 .env와 미러) |
| EAS `eas.json` | `EXPO_PUBLIC_*` (Kakao·Google 키) |

admin 콘솔 인증은 env가 아니라 `admin_users` 테이블(→
[inspect-prod](../how-to/inspect-prod.md)).

---
관련: [deploy-and-release](../how-to/deploy-and-release.md) · [operate-embeddings](../how-to/operate-embeddings.md) · [cli](cli.md)
