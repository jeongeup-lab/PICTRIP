# PicTrip 설계 스펙 (specs)

리팩토링 설계 세션 산출물. **읽는 순서 = S01 → S12** (S 번호가 전역 순서키).
새 세션은 항상 [`_context/session-context.md`](_context/session-context.md)를 가장 먼저 읽는다.

명명 규칙: `<group>/S<nn>-<slug>.md` (nn = 제로패딩). 날짜는 각 문서 본문 헤더에 기록.

## _context/ — 메타·기반
| 파일 | 내용 |
|---|---|
| [`session-context.md`](_context/session-context.md) | 잠긴 결정 · 제약 · 세션 로드맵 · 결정 로그 (모든 세션이 가장 먼저 읽음) |
| [`design-brief.md`](_context/design-brief.md) | 리팩토링 설계 시드 브리프 (스코프·제약·구조) |

## screens/ — 화면·UX 설계 (S1~S6)
| 세션 | 파일 | 스코프 | 목업 |
|---|---|---|---|
| S1 | [`S01-onboarding-auth.md`](screens/S01-onboarding-auth.md) | 스플래시·온보딩·로그인·권한 | 01~04 |
| S2 | [`S02-home-curation.md`](screens/S02-home-curation.md) | 홈 피드 + 큐레이션 상세 | 05·06 |
| S3 | [`S03-spot-detail.md`](screens/S03-spot-detail.md) | 스팟 상세 | 07 |
| S4 | [`S04-photo-search.md`](screens/S04-photo-search.md) | 사진 검색 플로우 | 08~10 |
| S5 | [`S05-map-region.md`](screens/S05-map-region.md) | 지도(내 주변) + 지역 선택 | 11·12 |
| S6 | [`S06-profile-legal.md`](screens/S06-profile-legal.md) | 저장·프로필·상태·약관 | 13~16 |

## platform/ — 시스템 설계 (S7~S10)
| 세션 | 파일 | 스코프 |
|---|---|---|
| S7 | [`S07-db.md`](platform/S07-db.md) | DB 설계 (전 화면 data needs → 스키마) |
| S8 | [`S08-infra.md`](platform/S08-infra.md) | 인프라 (배포·Redis·정적호스팅·딥링크·CI/CD) |
| S9 | [`S09-api-contract.md`](platform/S09-api-contract.md) | API 계약 (화면 → 엔드포인트) |
| S10 | [`S10-reconcile.md`](platform/S10-reconcile.md) | Reconcile 종합 · 마이그레이션 · 구현 순서 (마스터 플랜) |

## enhancements/ — 로드맵 외 보강 패스 (S11~S12)
| 세션 | 파일 | 스코프 |
|---|---|---|
| S11 | [`S11-external-benchmark.md`](enhancements/S11-external-benchmark.md) | 외부 벤치마크 & 심층분석 개선노트 |
| S12 | [`S12-observability.md`](enhancements/S12-observability.md) | 옵저버빌리티 (모니터링·로깅·에러트래킹·업타임·알림) |

## admin/ — 운영 어드민
| 파일 | 스코프 |
|---|---|
| [`A01-admin-console.md`](admin/A01-admin-console.md) | 관리자 콘솔 설계 (데이터 수집 운영 어드민) |
