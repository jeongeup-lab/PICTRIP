# 어드민 콘솔

> 운영자용 내부 콘솔(`https://api.pictrip.org/admin`)의 화면·인증·구성 조회용.

read-only 집계 + 해외 게시물 숨김 토글만 — 회원 관리·콘텐츠 편집은 비목표.

## 구성

| 조각 | 위치 | 비고 |
|---|---|---|
| 코드 | `backend/app/modules/admin/` | `/admin` 페이지 + `/admin/api/*` JSON |
| UI | `backend/app/modules/admin/static/` | HTML/CSS/JS 유일본(SSOT) — 여기서 직접 편집 |

## 화면

| 페이지 | 내용 |
|---|---|
| `/admin` | 운영 개요 — 총 스팟·최근 수집·임베딩 커버리지(+재임베딩 트리거) |
| `/admin/history` | 수집 이력 롤업 (일 단위, 최근 N일) |
| `/admin/health` | api·db·터널·가입자 컴포넌트 상태 (DB 다운 시에도 500 대신 degrade) |
| `/admin/overseas` | 해외 게시물 목록·검색 + `is_hidden` 토글 (유일한 쓰기) |

## 인증·보안

- **DB-backed**: `admin_users` 테이블(bcrypt) — env 아님. 베이스라인 마이그레이션이
  `admin`/`admin`을 시드하므로 **배포 후 즉시 로테이션**:
  `python -m scripts.set_admin_password --username admin` (CT110 DB 쓰기만 필요).
- `/admin/login` 5회/분/IP 레이트리밋. 세션 = 서명 쿠키
  (`ADMIN_SESSION_SECRET`, 로테이션 시 전 세션 무효).
- `/admin/assets`는 비인증 공개 마운트 — 민감 정보 절대 금지.

## 보류

- 수집 즉시 실행 버튼(Phase 2/A7) — `pipeline-sync.yml` 미배선.
  조건·근거는 [crons-and-workflows](crons-and-workflows.md) 참조.

---

관련: [crons-and-workflows](crons-and-workflows.md) · [api](api.md)
