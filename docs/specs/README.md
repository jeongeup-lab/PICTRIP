# PicTrip 설계 스펙

플랫 디렉토리 + 안정 ID(`S00`~`S13`) 구조. **파일 정렬 순서 = 읽는 순서**이며,
코드 주석의 인용(`S07 §10`, `S09 §3.1` 등)은 이 S-ID를 가리킨다.
새 세션은 항상 [`DECISIONS.md`](DECISIONS.md)를 가장 먼저 읽는다.

## 인덱스

| ID | 문서 | 스코프 | 목업 |
|---|---|---|---|
| — | [`DECISIONS.md`](DECISIONS.md) | **잠긴 결정 · 제약 · 결정 로그** (최우선 열람) | — |
| S00 | [`S00-design-brief.md`](S00-design-brief.md) | 설계 시드 브리프 (스코프·제약·구조) | — |
| S01 | [`S01-onboarding-auth.md`](S01-onboarding-auth.md) | 스플래시 · 온보딩 · 로그인 · 권한 | 01–04 |
| S02 | [`S02-home-curation.md`](S02-home-curation.md) | ~~홈 피드 + 큐레이션 상세~~ — **S13으로 대체됨** | 05·06 |
| S03 | [`S03-spot-detail.md`](S03-spot-detail.md) | 스팟 상세 | 07 |
| S04 | [`S04-photo-search.md`](S04-photo-search.md) | ~~사진 검색 플로우~~ — **S13으로 대체됨(기능 제거)** | 08–10 |
| S05 | [`S05-map-region.md`](S05-map-region.md) | 지도(내 주변) + 지역 선택 | 11·12 |
| S06 | [`S06-profile-legal.md`](S06-profile-legal.md) | 저장 · 프로필 · 상태 · 약관 | 13–16 |
| S07 | [`S07-database.md`](S07-database.md) | DB 설계 (화면 data needs → 스키마) | — |
| S08 | [`S08-infrastructure.md`](S08-infrastructure.md) | 인프라 (배포 · Redis · 정적호스팅 · 딥링크 · CI/CD) | — |
| S09 | [`S09-api-contract.md`](S09-api-contract.md) | API 계약 (화면 → 엔드포인트 · 에러코드 §4-2) | — |
| S10 | [`S10-reconcile.md`](S10-reconcile.md) | Reconcile 종합 · 마이그레이션 · 구현 순서 | — |
| S11 | [`S11-external-benchmark.md`](S11-external-benchmark.md) | 외부 벤치마크 & 심층분석 개선노트 | — |
| S12 | [`S12-observability.md`](S12-observability.md) | 옵저버빌리티 (모니터링 · 로깅 · 업타임 · 알림) | — |
| S13 | [`S13-home-feed-explore-redesign.md`](S13-home-feed-explore-redesign.md) | 홈·탐색 전면 개편 (S02·S04 대체) | `redesign-2026-07-cc/` |

어드민 콘솔 스펙은 [`admin/specs/A01-admin-console.md`](../../admin/specs/A01-admin-console.md) (A-ID 체계).

## 규칙

- **S-ID는 영구 불변** — 코드·PR·문서가 `S09 §3.1` 형식으로 인용하므로 번호를 재사용·변경하지 않는다.
- 새 스펙은 다음 번호(`S13-…`)로 추가하고 이 인덱스에 등록한다.
- 화면 스펙(S01–S06)의 디자인 근거는 `docs/mockups/`(16 스크린)이 SSOT.
- 날짜·상태는 각 문서 본문 헤더에 기록한다.
