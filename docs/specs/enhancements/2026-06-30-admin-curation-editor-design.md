# Admin 홈 큐레이션 편집기 — 프로덕션급 완성 설계

- **일자**: 2026-06-30
- **브랜치**: `feat/admin-curation-editor-polish` (off `main`)
- **대상**: `admin/mockups/{curation.html, assets/curation.css, assets/curation.js}` +
  바이트 동일 복사본 `backend/app/modules/admin/static/...`, 백엔드
  `app/modules/admin/{routes,services,repositories,schemas}.py`
- **연관 스펙**: `admin/specs/A01-admin-console.md` §7 (ADM-012~016)

## 목표

운영자가 프로덕션에서 홈 큐레이션을 **실제로 편집·발행하는 도구**로서의 완성도.
더미/가짜 표시 없는 진실된 미리보기, 매끄러운 검색·이미지, 명확한 발행 흐름.

## 불변 제약 (반드시 준수)

- admin `static/`는 `admin/mockups/`의 **바이트 동일 복사본**. CI drift 체크
  (`.github/scripts/check-admin-mockup-drift.sh`)가 게이트. 두 곳 항상 동일.
- 모든 응답 JSend `{data,error,meta}`, 에러는 `AppError` 서브클래스. JS는 `err.code`로 분기.
- 신규 UI CSS는 전부 `.wz` 스코프 + 충돌 클래스 리네임(이미 적용된
  `pcard/pthumb/wcol/sdot/pseg` 패턴 유지). 다른 어드민 페이지를 깨지 말 것.
- HTML CSP `img-src https:`만 허용 → KTO 이미지는 URL 참조만, http→https 승격
  validator(`https_kto_image`) 모든 이미지 필드에 적용.
- 백엔드 레이어링: `routes`=I/O만, `services`=로직, `repositories`=쿼리.
  크로스모듈 읽기는 대상 모듈의 `services` 경유.
- KTO 이미지 다운로드/저장 금지.

## 결함별 설계

### ① 발행 흐름 통합 (현재 진입점 4개 → 명확한 3액션)

**현재**: 상단 "이 큐레이션 발행" + 우하단 "저장 후 발행"(동일 동작) + "초안으로"
+ 인스펙터 내부 발행 토글 스위치 = 4중 혼란.

**변경**:
- 인스펙터 푸터 액션을 **3개로 명확화**:
  - `[임시저장]` — 현재 발행상태를 **유지**한 채 copy/cover/picks/position 저장
    (`saveCuration(publishOverride=null)` → 현재 `it.isPublished` 그대로 PUT).
  - `[발행]` — 저장 + `isPublished=true` (미발행/초안 상태일 때 표시).
  - `[발행 취소]` — 저장 + `isPublished=false` (발행 상태일 때 표시).
  - 즉, 발행/발행취소는 **현재 상태에 따라 하나만** 노출(토글 액션).
- 인스펙터 내부 발행 **토글 스위치 제거**. 발행 상태는 읽기전용 배지(`발행됨`/`초안`)로만 표기.
- 상단 툴바의 중복 "이 큐레이션 발행" 버튼 **제거**. 상단은 `되돌리기` + 저장상태 표시만.
- 상태 표시 일원화: `편집 중`(dirty) / `저장됨` / 슬롯별 배지 `발행됨`·`초안`.
- 좌측 리스트 `.sdot`/배지, 폰 미리보기 미발행 처리(`is-draft`)는 발행상태와 일관 동기화.
- 저장 중 모든 액션 버튼 비활성(`setBusy`), 422/404/네트워크 에러 토스트·필드에러 일관 처리,
  실패 시 로컬상태 롤백(되돌리기로 서버상태 복구 가능).

계약 변경 없음 — 기존 `PUT /curations/{id}` (`isPublished`,`position`) 그대로 사용.

### ② 진실된 자동충전 미리보기 (신규 읽기전용 엔드포인트)

**현재**: `autoCardsHtml()`가 이미지 없는 회색 더미 카드 3장. 거짓.

**변경**: 신규 `GET /admin/api/curations/{id}/preview`.
- admin `services.preview_curation()`가 spots `curations.py`의 resolve 로직을
  **services 경유로 재사용**: `load_curation` → `resolve_curation_spots`
  (핸드픽 있으면 그대로, 비면 품질게이트 풀의 결정론적 8개). 이미지 포함.
- **캐시 우회·발행필터 무시**: 운영자는 미발행/초안도 "발행 시 나갈 모습"을 봐야 함.
  `resolve_curation_spots`는 Redis 캐시를 쓰므로, admin 프리뷰는 캐시를 우회하는
  경로가 필요. → spots `curations.py`에 `resolve_curation_spots_fresh(...)`
  (캐시 read/write 생략, 동일 resolve+hydrate) 추가하거나 기존 함수에
  `use_cache: bool = True` 파라미터 추가. **후자 채택**(중복 최소화, 기본동작 불변).
- 응답 스키마 `CurationPreview { curationId, source: "handpicked"|"auto", spots: [PreviewSpot] }`
  where `PreviewSpot { contentId, name, category, imageUrl }`, `imageUrl`은 https 승격.
- JS: 각 큐레이션 미리보기 렌더 시 — 로컬 편집 핸드픽이 있으면 그걸 그림(이미 동작),
  핸드픽이 **비어 있을 때만** 이 엔드포인트로 실제 풀 스팟을 가져와 "자동 편성됨"
  라벨과 함께 진짜 카드로 렌더. 결과는 큐레이션 id별로 JS에서 메모이즈.
- 회색 더미(`autoCardsHtml`)·상세 빈그리드 문구("품질 랭킹으로 자동 편성") 제거,
  실제 스팟 카드 + 정직한 "자동 편성됨" 마이크로카피로 대체.

레이어링: admin `services`가 `spots.services.curations`를 import(크로스모듈 읽기 = services 경유, 허용).
admin은 읽기전용이므로 `repositories` 신규 불필요.

### ③ 이미지 누락 처리

- 신규 `PreviewSpot.imageUrl` / 기존 모든 이미지 필드에 `https_kto_image` validator 확인.
- `first_image_url == null` 스팟 → 깨진 아이콘 금지, inset 플레이스홀더(이미 `.pthumb`
  등이 `var(--p-inset)` 배경). 검색결과 썸네일(`.thumb`)도 동일 처리 보강.
- 로딩 중 자리 확보(고정 aspect-ratio 박스)로 레이아웃 흔들림 방지. 자동충전 프리뷰
  로딩 동안 스켈레톤/플레이스홀더 슬롯 노출.

### ④ 스팟 추가(검색) 모달 재설계

- **신규** `GET /admin/api/regions` — 17 시도 평면 리스트
  `{regions: [{code, name}]}` (`regions` 테이블 `ldong_regn_cd`/`ldong_regn_nm`,
  17개만; 광역시도 레벨). admin `repositories.list_regions()` (읽기전용 raw SQL).
- 필터 칩을 이 엔드포인트로 동적 생성, **코드를 `region` 파라미터로 전송**(현재 한글
  라벨 전송 버그 수정). "전체" 칩 = region 생략. 카테고리 필터는 백엔드 미지원이라
  이번 범위 제외(정직).
- 디바운스(유지), 명시적 상태: **로딩**(스피너/문구) / **빈**(검색어 없음·결과 없음 구분)
  / **에러**(재시도 가능). 이미 추가됨 표시(유지·보강), 이미지 플레이스홀더.
- 키보드 접근성: 모달 포커스 트랩, `Esc` 닫기(유지), 검색 input 자동포커스(유지),
  결과 카드 `role`/`tabindex`/엔터로 추가, 칩 키보드 조작.
- 표지 선택 모드 / 손픽 추가 모드 둘 다 매끄럽게(모드별 헤더·동작 분기 유지·정리).
- `.rspot` 바둑판 마크업/스타일 정합 유지.

### ⑤ 좌측 리스트 드래그 재정렬 (신규 포함)

- 좌측 편성 리스트 슬롯(`.slot`)을 **같은 그룹(hero/rail/editorial) 내에서** 드래그로
  재정렬. 드롭 시 그룹 내 `position`을 0..n-1로 **재계산**, 변경된 슬롯들을 dirty 표시.
- 저장: 재정렬은 위치 변경이므로 각 변경 슬롯에 대해 `PUT /curations/{id}`로
  `position` 반영. **저장 액션 시 일괄 반영**(드래그 즉시 N번 PUT 금지) — 로컬에서
  position 갱신 → 미리보기/리스트 즉시 반영 → 저장 시 변경분만 PUT.
- 그룹 간(hero↔rail) 이동 금지(type 불변, `ck_curation_scope`). 같은 그룹 내만 허용.
- 핸드픽 카드 드래그(`wirePickDrag`)는 이미 동작 — 패턴 재사용.
- 접근성: 키보드 대체수단으로 기존 +/- position 필드 **유지**(드래그 못 쓰는 환경 대비).

### ⑥ 전반 프로덕션 폴리시

- 반응형: 노트북 폭(≤1240/≤1100)에서 3열 레이아웃 안 잘리게 점검·보강.
- 접근성: 포커스 링, `aria-*`, 키보드 내비. 토스트 `aria-live`.
- 저장 중 버튼 비활성·스피너. 낙관적 업데이트 + 실패 롤백 일관.
- 카피 톤 통일(존댓말, 간결). 폰 미리보기 ↔ 실제 앱(무채색 에디토리얼) 픽셀 정합 점검.

## 백엔드 변경 요약

| 파일 | 변경 |
|---|---|
| `admin/routes.py` | `GET /api/curations/{id}/preview`, `GET /api/regions` 라우트 추가 |
| `admin/services.py` | `preview_curation()`, `list_regions()` 추가 (cross-module read via `spots.services.curations`) |
| `admin/repositories.py` | `list_regions()` raw SQL (17 시도) 추가 |
| `admin/schemas.py` | `CurationPreview`, `PreviewSpot`, `RegionList`, `RegionItem` (+https validator) |
| `spots/services/curations.py` | `resolve_curation_spots(..., use_cache=True)` 파라미터 추가(기본동작 불변) |

신규 마이그레이션 없음. `curations`/`curation_spots`/`spots`/`regions` 스키마 변경 없음.

## 검증 계획

- 백엔드 4종: `POSTGRES_DB=pictrip_test uv run ruff check . && ruff format --check . && mypy app && pytest`
  (신규 엔드포인트·use_cache 경로 테스트 추가).
- `node --check`로 `curation.js` 문법.
- `bash .github/scripts/check-admin-mockup-drift.sh`로 SSOT 바이트 동일성.
- 로컬 기동 후 브라우저로 `http://127.0.0.1:8000/admin/curation` (admin/admin) 실제 클릭 검증:
  발행/임시저장/발행취소, 자동충전 프리뷰 실제 이미지, 검색 지역필터, 드래그 재정렬,
  이미지 플레이스홀더, 반응형. `superpowers:verification-before-completion` 준수.

## 범위 외 (이번 작업 제외)

- 그룹 간 큐레이션 이동, 큐레이션 생성/삭제(type/slug/scope 불변 유지).
- 카테고리 기반 검색 필터(백엔드 미지원).
- 새 DB 테이블/마이그레이션.
