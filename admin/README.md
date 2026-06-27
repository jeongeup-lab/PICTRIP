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
| Phase 2 수집 트리거 | ADM-009·010 | ⏸ 보류 — 파이프라인 트리거 메커니즘 = `workflow_dispatch` on self-hosted runner; secrets + 토큰 세팅 필요 |
| ADM-011 어드민 배포 | — | ⬜ 머지 후 배포 — `ADMIN_PASSWORD` → CT112 `.env`, CF Access |

## 노출 전 운영 주의

- 강한 `ADMIN_PASSWORD` + Cloudflare Access (Phase 3).
- prod `CORS` / `TRUSTED_HOSTS` 명시.
