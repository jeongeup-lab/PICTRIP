# pictrip-data (ETL pipeline)

KTO·Wikidata data collection for PicTrip. Runs on **CT111**, writes to the
shared prod DB (CT110 `pictrip`). Separate Python project from `backend/` —
no shared venv; the only coupling is the `spots` + `sync_runs` tables.

## CLI

| 명령 | 용도 | 실행 방식 |
|---|---|---|
| `sync-daily` | KTO `areaBasedSyncList2` → `spots` 증분 동기화 (watermark upsert + soft-delete) | 매일 04:00 KST 타이머 + admin 버튼(보류) |
| `sync-full` | modifiedtime 필터 없는 전체 재조정 (쿼터 인지) | 수동, 주간 규모 |
| `validate-images` | `first_image_url` 생존 프로브 — 죽은 원본 교체/NULL | 주간 크론(`image-validate.yml`) |
| `sync-overseas` | Wikidata+Commons → `overseas_spots` | 월간 크론(`overseas-sync.yml`) |
| `backfill-overseas-thumbs` | Commons 썸네일 직접 URL 재작성 | 일회성 runbook |
| `backfill-overseas-descriptions` | 빈 `description_ko`를 ko.wikipedia intro로 | 일회성 runbook |
| `load-codes` | 지역·분류 마스터 코드 로드 | 부트스트랩 일회성 |

- **`sync_runs` 감사 테이블은 이 프로젝트 소유** (`sync/audit.py`,
  `CREATE TABLE IF NOT EXISTS`). backend는 read-only raw SQL — backend
  Alembic에 절대 추가하지 않는다.
- Detail/이미지 fetch는 여기 없음 — backend가 lazy 캐시.
- Streamlit 대시보드 (`dashboard/app.py`, :8501, tailnet 전용).

## Usage

```bash
uv sync
uv run pictrip-data sync-daily
uv run streamlit run src/pictrip_data/dashboard/app.py
```

크론·시크릿 위치는 [`docs/reference/crons-and-workflows.md`](../docs/reference/crons-and-workflows.md) 참조.
