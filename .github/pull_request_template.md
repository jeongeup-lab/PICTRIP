## 요약
<!-- 무엇을 / 왜. 1~3줄. -->

## 관련 스펙 / 이슈
<!-- 예: docs/specs/screens/S03-spot-detail.md · A01 ADM-014 · #12 -->

## 변경 단위
<!-- 해당 항목을 [x] 로 체크 (최소 1개) -->
- [ ] backend
- [ ] mobile
- [ ] web
- [ ] pipeline
- [ ] deploy
- [ ] docs

## 핵심 결정 (load-bearing decisions)
<!-- 되돌리기 어렵거나 논쟁 여지 있는 결정을 기록 (CLAUDE.md 규칙). 없으면 "없음". -->

## 검증
<!-- 해당 단위 명령을 돌리고 체크. 안 돌린 항목은 체크하지 말 것. -->
- [ ] backend: `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest`
- [ ] mobile: `npm run lint && npm run typecheck && npm run format:check && npm test`
- [ ] pipeline: `uv run ruff check . && uv run pytest`
- [ ] DB 변경: 마이그레이션 SQL 리뷰 완료 (부분/CHECK 인덱스 수동 확인 · `sync_runs` 미포함)
- [ ] 해당 없음

## 스크린샷
<!-- mobile UI 변경 시 첨부. 아니면 생략. -->
