# pictrip-data (ETL pipeline)

KTO·Wikidata data collection for PicTrip. Runs on **CT111**, writes to the
shared prod DB (CT110 `pictrip`). Separate Python project from `backend/` —
no shared venv; the only coupling is the `spots` + `sync_runs` tables.

## CLI

| 명령 | 용도 | 실행 방식 |
|---|---|---|
| `sync-daily` | KTO `areaBasedSyncList2` → `spots` 증분 동기화 (watermark upsert) | `pipeline-daily.yml` + admin 버튼 |
| `sync-full` | 전체 재조정 + **soft-delete**(사라진 스팟 `show_flag=0`) | `pipeline-weekly.yml` |
| `validate-images` | `first_image_url` 생존 프로브 — 죽은 원본 교체/NULL | `pipeline-weekly.yml` |
| `sync-overseas` | Wikidata+Commons+ko.wikipedia → `overseas_spots` | `pipeline-monthly.yml` |
| `backfill-overseas-descriptions` | 빈 `description_ko`를 ko.wikipedia intro로 | 일회성 runbook |
| `load-codes` | 지역·분류 마스터 코드 로드 | 부트스트랩 일회성 |

- **`sync_runs` 감사 테이블은 이 프로젝트 소유** (`sync/audit.py`,
  `CREATE TABLE IF NOT EXISTS`). backend는 read-only raw SQL — backend
  Alembic에 절대 추가하지 않는다.
- Detail/이미지 fetch는 여기 없음 — backend가 lazy 캐시.
- 수집 이력(`sync_runs`) 조회는 어드민 콘솔 `/admin/history`.

## Usage

```bash
uv sync
uv run pictrip-data sync-daily
```

크론·시크릿 위치는 [`docs/reference/crons-and-workflows.md`](../docs/reference/crons-and-workflows.md) 참조.
