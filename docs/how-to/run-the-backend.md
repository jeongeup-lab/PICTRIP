# 백엔드 실행

> 목표: 로컬에서 API 서버를 띄우고, 푸시 전 검증 스위트를 전부 그린으로 만든다.

## 전제
- `backend/.env` — 로컬 Postgres/Redis 접속값. 로컬 도커 `pictrip-postgres`에는
  `pictrip`(dev 데이터) + `pictrip_test`(마이그레이션만) 두 DB가 있다.
  `.env`의 `POSTGRES_HOST`가 원격이면 `POSTGRES_HOST=localhost`로 덮는다.
- `uv sync` 완료.

## 단계

1. **서버 실행**
   ```bash
   cd backend
   uv run uvicorn app.main:app --reload
   # http://localhost:8000/health · /v1/docs
   ```

2. **푸시 전 검증 (전부 통과 필수)**
   ```bash
   uv run ruff check . && uv run ruff format --check . \
     && uv run mypy app && uv run lint-imports \
     && POSTGRES_HOST=localhost POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest
   ```

3. **새 마이그레이션**
   ```bash
   uv run alembic revision --autogenerate -m "..."
   # SQL을 반드시 눈으로 리뷰 — autogenerate는 부분 인덱스·CHECK·드롭 downgrade를 놓친다
   POSTGRES_HOST=localhost POSTGRES_DB=pictrip_test uv run alembic upgrade head
   ```
   파괴적 변경은 expand→contract 순서를 지킨다(→ [ADR-0002](../adr/0002-expand-contract-migrations.md)).

## 검증
- pytest 전 케이스 green + `Contracts: 6 kept, 0 broken`(lint-imports).
- `curl localhost:8000/health` → `{"data":{"status":"ok"},…}`.

## 자주 나는 문제
| 증상 | 원인 | 해결 |
|---|---|---|
| 전역 카운트 assert 실패 | dev DB(`pictrip`)로 테스트 실행 | `POSTGRES_DB=pictrip_test` |
| admin 로그 assert에 ANSI 코드 | 상속된 `FORCE_COLOR` | `NO_COLOR=1` |
| DB 접속 실패 | `.env`가 원격 호스트 | `POSTGRES_HOST=localhost` 덮기 |
| `alembic check` 트리거 인덱스 경고 | trgm 인덱스가 raw-SQL(0008) | 기존 노이즈 — CI는 `upgrade head`로 게이트 |

---
관련: [deploy-and-release](deploy-and-release.md) · [database-schema](../reference/database-schema.md) · [architecture](../explanation/architecture.md)
