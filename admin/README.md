# PicTrip Admin (어드민 콘솔)

Owner 염준선 · 설계 SSOT [`admin/specs/A01-admin-console.md`](specs/A01-admin-console.md).

## 구성

| 조각 | 위치 | 비고 |
|---|---|---|
| 코드 | `backend/app/modules/admin/` | FastAPI 모듈 (`/admin` + `/admin/api/*`) |
| 명세 | `admin/specs/A01-admin-console.md` | 설계 SSOT |
| 목업 (UI SSOT) | `admin/mockups/` | served copy = `backend/app/modules/admin/static/` (byte-identical, drift-checked) |

## 진행 상황 (ADM-001~018)

| 단계 | 범위 | 상태 |
|---|---|---|
| Phase 1 운영콘솔 | ADM-001~008 | ✅ 완료 (PR #21) |
| Phase 4 큐레이션 편집기 | ADM-012~018 | ✅ 완료 (PR #21) |
| 큐레이션 하드닝 (A11) | 발행 토글 제거(편성=시드 고정 6+3) · 보드 DnD 재정렬(`PUT /admin/api/curations/positions`) · `…/preview` 정식화 · 피커 필터(시군구·카테고리·페이지네이션) · `/admin/login` 레이트리밋 | ✅ 완료 (2026-07-08) |
| Phase 2 수집 트리거 | ADM-009·010 | ⏸ 보류 — 파이프라인 트리거 메커니즘 = `workflow_dispatch` on self-hosted runner; secrets + 토큰 세팅 필요 |
| ADM-011 어드민 배포 | — | ⬜ 머지 후 배포 — `admin_users` 비번 로테이션(DB), CF Access |

## 노출 전 운영 주의

- 인증은 DB-backed `admin_users`(마이그레이션 0016이 `admin`/`admin` 시드) — 강한 비번으로
  로테이션(`backend/scripts/set_admin_password.py`) + Cloudflare Access (Phase 3).
- `/admin/login`은 5회/분/IP 레이트리밋(브루트포스 방어) 적용됨.
- prod `CORS` / `TRUSTED_HOSTS` 명시.
