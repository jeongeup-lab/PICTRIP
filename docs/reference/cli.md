# CLI·스크립트 레퍼런스

> 수동 실행 가능한 명령의 조회용 표. backend 스크립트는 **라이브 api 컨테이너
> exec**가 기본이다(새 컨테이너 금지 — 이미지·`.env`·DB 라우트를 이미 가짐).

## backend scripts (`python -m scripts.<name>`)

| 명령 | 용도 | 언제 |
|---|---|---|
| `set_admin_password --username admin` | `admin_users` 암호 upsert (대화형은 히스토리 미기록, `ADMIN_NEW_PASSWORD` env 비대화형) | 시드 기본 교체·로테이션 |
| `warm_channels` | festa/pets/snap 채널 캐시 예열 (fail-soft) | 크론 + `deploy.sh` 자동 |
| `sync_concentration [--limit] [--dry-run]` | 집중률 idempotent 적재 | 일일 크론; 심사 전 수동 갱신 |
| `backfill_embeddings [--limit] [--only-failed --failure-reason source_changed] [--dry-run]` | 대표사진 CLIP 백필 (resumable) | `pipeline-daily`(신규) · `pipeline-weekly`(복구) 자동 |
| `backfill_gallery_embeddings [--limit] [--dry-run]` | 갤러리 centroid 백필 | 일일 크론 (800/일) |
| `embed_overseas [--limit]` | 해외 임베딩 백필 | `pipeline-monthly` 자동 |
| `backfill_nicknames [--dry-run]` | NULL name 계정 닉네임 백필 (일회성) | 완료됨 |

## pipeline CLI (`uv run pictrip-data <cmd>`, CT111)

| 명령 | 용도 | 언제 |
|---|---|---|
| `sync-daily` | KTO → `spots` 증분 (watermark upsert + soft-delete) | 04:00 KST 타이머 |
| `sync-full` | 필터 없는 전체 재조정 (쿼터 인지) | 수동, 주간 규모 |
| `validate-images [--dry-run] [--limit]` | `first_image_url` 생존 프로브 → 교체/NULL | 주간 크론 |
| `sync-overseas [--limit] [--country] [--dry-run]` | Wikidata+Commons → `overseas_spots` | 월간 크론 |
| `backfill-overseas-descriptions [--dry-run]` | 빈 `description_ko` ← ko.wikipedia intro | `sync-overseas` 가 자동 수행; 수동 재실행용 |
| `load-codes` | 지역·분류 마스터 로드 | 부트스트랩 |

수집 이력(`sync_runs`) 조회는 어드민 콘솔 `/admin/history`.
(:8501, tailnet 전용).

## 자주 쓰는 원격 진입

| 대상 | 명령 |
|---|---|
| pve 호스트 | `ssh root@100.83.101.1` |
| 프로드 DB (read-only) | `pct exec 110 -- docker exec -it pictrip-postgres psql -U pictrip pictrip` |
| api 컨테이너 셸 | `pct exec 112 -- docker exec -it <api-host-api-1> sh` |
| 디스크 풀 복구 | `pct exec 112 -- docker builder prune -af && docker image prune -af` |

---
관련: [operate-embeddings](../how-to/operate-embeddings.md) · [inspect-prod](../how-to/inspect-prod.md) · [crons-and-workflows](crons-and-workflows.md)
