# 이미지 화질 개선 — KTO 원본(`_image1_1`) 업그레이드

작성일 2026-07-14 · 대상: `backend/` (core·feed·spots) + `mobile/` (RemoteImage)

## 문제

홈 채널·게시글에 뜨는 KTO 시설 이미지가 큰 표면(풀카드/전체화면)에서 흐릿하다.

## 검증 (실측)

프로덕션 채널 API에서 KTO `firstimage` 40장을 표본 측정:

- 현재 사용하는 `firstimage` = URL 접미사 `_image2_1.jpg` = **940px 폭**.
- 같은 리소스에 **더 큰 원본 변형 `_image1_1.jpg` 존재** — 폭 **중앙값 1620px** (≈1.7배).
- `_image1_1` 존재율 **32/40 (80%)**. 나머지 **20%는 404** (오래된 이미지) → 폴백 필수.
- 원본이 있는 것 중 63%가 940px보다 크다(나머지는 소스 자체가 작음 → 효과 미미하나 손해 없음).
- `_image3_1.jpg` = 300px (썸네일, `firstimage2`).

**결론**: KTO 이미지 상한은 940이 아니라 대부분 1620px. `firstimage` 필드가 중간 크기를 가리킬 뿐. URL의 `_image2_1`→`_image1_1` 치환으로 절반이 선명해진다.

## 정책 확인

`_image2_1`→`_image1_1`은 같은 리소스의 다른 크기 URL을 가리키는 **transport-only 변환**으로, 기존 `https_kto_image`(http→https)와 동일 성격. **다운로드·저장 없이 URL만 사용** 규칙을 그대로 지킨다.

## 설계

### 원칙 — 맥락별 해상도 (blanket 아님)

1620px는 940px 대비 바이트 ~2.7배(193KB→527KB). 큰 표면에만 적용하고 작은 타일은 940px 유지.

| 분류 | 대상 필드 | 처리 |
|---|---|---|
| 큰 표면 (풀카드/전체화면) | `MatchCard.imageUrl`, `ChannelCard.imageUrl`(스토리), 스팟 상세 hero | `_image1_1` 원본 |
| 작은 타일 | `ChannelMeta.thumbnailUrl`(타일 썸네일), 리스트 썸네일 | 940px 유지 |

게시글 hero(해외/Commons)는 KTO가 아니며 현재 1200px로 카드(≈1074px 필요)에 충분 → **이번 범위 제외**.

### 백엔드

- `app/core/kto_images.py`에 `hires_kto_image(url) -> str | None` 추가.
  - KTO 호스트(`tong.visitkorea.or.kr`)의 URL에서 `_image2_1` 세그먼트를 `_image1_1`로 치환.
  - http→https도 함께 보장(기존 `https_kto_image`와 합성 또는 내부 재사용).
  - 그 외 URL·None은 그대로 반환. 확장자 대소문자(`.jpg`/`.JPG`) 무관하게 접미사만 치환.
- 큰 표면 필드 직렬화 지점에 적용(기존 `https_kto_image` 적용 패턴과 동일 위치). 정확한 필드 목록은 구현 시 코드로 확정하되, 위 표의 "큰 표면"에 한정.

### 모바일 — 폴백 (필수)

- `RemoteImage`의 기존 `onError` 재시도 인프라에 **"KTO `_image1_1` 로드 실패 시 `_image2_1`로 1회 강등 후 재시도"** 추가.
- 원본 없는 20%를 런타임 404 없이 흡수. festa/pets/snap은 라이브 KTO라 파이프라인 프로브가 못 미치므로, 이 클라이언트 폴백이 전 소스를 커버하는 유일한 지점.
- 강등은 uri당 1회로 제한하고, 강등 후에도 실패하면 기존 회색 플레이스홀더 경로로 진입.

## 범위 밖 (YAGNI)

- 파이프라인이 KTO 이미지 크기를 프로브해 저해상을 숨기는 품질 게이트.
- 해외 Commons width 상향(현재 1200px로 충분).
- snap 갤러리(이미 상한).

## 검증 방법

- 백엔드: `hires_kto_image` 단위 테스트(치환/비-KTO 무변경/None/대소문자 확장자/이미 https).
- 모바일: `RemoteImage` 폴백 테스트(`_image1_1` onError → `_image2_1` 재요청, 강등 후 실패 시 플레이스홀더).
- 수동: 홈 게시글 매칭 카드·채널 스토리에서 선명도 육안 확인.
