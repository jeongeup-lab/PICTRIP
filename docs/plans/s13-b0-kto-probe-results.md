# S13 B0 — KTO 채널 API 3종·집중률 프로브 결과

Task B0 산출물. **B1의 base URL·enum, B4의 오퍼레이션명·필드명은 이 문서가 SSOT.**
계획의 코드 예시와 다르면 이 실측을 따른다.

프로브 일시: 2026-07-13 (로컬 curl, 사용자 제공 서비스키).
키 호환: KorService2·PhotoGalleryService1 = 기존 키에 이미 등록. KorPetTourService2 =
활용신청 후 승인(전파 지연, 아래 참조).

---

## 1. Festa — `KorService2/searchFestival2` ✅ 등록·정상

- Base URL: `http://apis.data.go.kr/B551011/KorService2` (기존 KTO_BASE_URL_KOR 재사용, 신규 설정 불필요)
- resultCode `0000`.
- **확정 필드**: `contentid` · `title` · `addr1` · `addr2` · `eventstartdate`(YYYYMMDD) ·
  `eventenddate` · `firstimage` · `firstimage2` · `cpyrhtDivCd`(="Type3") · `mapx` · `mapy` ·
  `contenttypeid`(="15") · `progresstype` · `lDongRegnCd` · `lDongSignguCd`.
- `firstimage`는 `https://tong.visitkorea.or.kr/...` — 빈 문자열 케이스 존재하므로 카드 조립 시 빈값 제외.
- **진행 중/종료 임박 쿼리 형태**:
  - `eventStartDate=<과거일>` + `arrange=C`(수정일순) 로 요청하면 그 날짜 이후 시작한 축제가 반환됨.
    요청 파라미터에 `eventEndDate` 상한 필터는 **미지원**(응답에만 `eventenddate` 존재).
  - 따라서 "진행 중"은 서버에서 `eventstartdate <= today <= eventenddate` 로 후처리 필터,
    "종료 임박(dday)"은 `eventenddate - today` 로 서버 계산·정렬한다. B4는 `eventStartDate`를
    today−N(예: 30일)로 넉넉히 잡고 응답을 today 기준으로 걸러낸다.
- **B4 Festa 카드 매핑**: `dday` = `eventenddate`까지 남은 일수, `line` = 기간(`eventstartdate~eventenddate`)+장소(`addr1`), `saveable`=true(`contentid`가 KorService2 스팟과 호환 → 상세/저장 연결 가능).

## 2. Snap — `PhotoGalleryService1/galleryList1` ✅ 등록·정상

- Base URL: `http://apis.data.go.kr/B551011/PhotoGalleryService1`
- **오퍼레이션 = `galleryList1`** (keyword 불필요). 계획 예시의 `gallerySearchList1`은 `keyword`
  필수 파라미터라 목록 채널에 부적합(누락 시 resultCode `11 NO_MANDATORY_REQUEST_PARAMETERS_ERROR1`).
- resultCode `0000`. `arrange=A`(제목순) 등 정렬 지원.
- **확정 필드**: `galContentId` · `galContentTypeId`(="17") · `galTitle` · `galWebImageUrl` ·
  `galPhotographyMonth`(YYYYMM) · `galPhotographyLocation` · `galPhotographer` · `galSearchKeyword`.
- 이미지: `galWebImageUrl` = `http://tong.visitkorea.or.kr/cms2/website/..jpg` (KTO 자체 CDN).
  - HEAD는 405(서버가 HEAD 거부)지만 **GET은 206/200 정상 → 핫링크 OK**(기존 `firstimage`와 동일 호스트).
  - http → https 승격 가능(동일 호스트 https 응답).
- **저작권 필드 없음** (`cpyrhtDivCd` 상당 부재). KTO 홍보사진단 자체 촬영본. `galPhotographer` 표기로 크레딧.
- **contentId 호환성**: `galContentId`는 `contentTypeId=17`(사진갤러리 전용)로 **KorService2 스팟과 비호환**.
  → 스펙대로 Snap 카드는 `contentId=null` · `saveable=false` · `line=galPhotographyLocation`.

## 3. Pets — `KorPetTourService2/areaBasedList2` ✅ LIVE (전파 완료·재프로브 200)

- Base URL: `http://apis.data.go.kr/B551011/KorPetTourService2` (**버전 접미사 `2` 필수** — 계획 예시의
  `KorPetTourService`(무버전)는 `API not found`, `KorPetTourService1`은 `Unexpected errors`).
- 활용신청 페이지: https://www.data.go.kr/data/15135102/openapi.do
- 현재 상태: **재프로브 resultCode `0000` 확인** — 게이트웨이 전파 완료, `Forbidden` 해소. `areaBasedList2`
  (파라미터 `numOfRows`·`arrange="C"`) 정상 응답.
- 확정 오퍼레이션: `areaBasedList2`(지역기반). 반환 필드 `contentid`·`contenttypeid`(="12", 일반 관광지)·
  `title`·`addr1`·`firstimage`·`cpyrhtDivCd`. `contentid`는 KorService2 type-12 스팟과 호환 →
  `saveable=true`·`content_id` 채움.
- **주의**: `areaBasedList2`는 반려동물 전용 필드를 반환하지 않는다(`acmpyTypeCd`는 KorService2/detailPetTour2
  에만 존재하며, 우리는 이를 호출하지 않음). 따라서 Pets 카드의 `tag`는 **정적 라벨 `"반려동물 동반 가능"`**
  (필드에서 읽지 않음).
- **B4 Pets 카드 매핑**: `tag` = 정적 `"반려동물 동반 가능"`, `saveable=true`(contentid type-12 호환),
  이미지 필수 필터 후 `random.sample` 최대 10개.

## 4. 집중률 신선도 — `TatsCnctrRateService/tatsCnctrRatedList`

- Base URL: `https://apis.data.go.kr/B551011/TatsCnctrRateService` (기존 KTO_BASE_URL_CNCTR).
- **원천 API 살아있음**: 모든 호출 resultCode `0000 OK`. 파라미터 `areaCd`·`signguCd`(lDong 코드)·
  `numOfRows`·`pageNo`.
- populated row(실제 `baseYmd`)는 **로컬에서 미확인** — 유효 lDong sigungu 코드는 CT110 `sigungu`
  테이블에 있고, 붙어있는 MCP DB(`hda`·`hda_etl`)는 pictrip이 아님. 임의 코드는 `totalCount 0`.
- CT110 `spot_concentration` 테이블 신선도도 원격 확인 불가.
- **판정**: 원천 API가 응답(`0000`)하므로 STOP 조건(원천 사망 → Hot/Hidden 재검토)에 **해당 없음**.
  실제 테이블 `max(base_ymd)` 신선도는 **B6 크론 실행 시 CT110에서 확정**한다.

---

## B1·B4 반영 사항 (요약)

| 설정 | 값 |
|---|---|
| `KTO_BASE_URL_PET` | `http://apis.data.go.kr/B551011/KorPetTourService2` |
| `KTO_BASE_URL_GALLERY` | `http://apis.data.go.kr/B551011/PhotoGalleryService1` |
| `KtoService.PET` | `"KorPetTourService2"` |
| `KtoService.GALLERY` | `"PhotoGalleryService1"` |

- Festa base는 기존 `KorService2` 재사용(신규 설정 불필요).
- Snap 오퍼레이션은 `galleryList1`, Pets는 `areaBasedList2`, Festa는 `searchFestival2`.

## 미결/후속

- ~~**[블로커→B4]** KorPetTourService2 게이트웨이 전파~~ → **해소**: 재프로브 `0000` LIVE, B4 착수(§3 참조).
- **[B6]** 크론 2종 배선 완료: `concentration-sync.yml`(일일 04:30 KST, CT112 컨테이너 `sync_concentration`) + `overseas-sync.yml`(월간 1일 03:00 KST, CT111 `sync-overseas` → CT112 `embed_overseas`).
  - **후속(첫 실행 검증, dev 머지·배포 직후 필수)**: schedule 은 default 브랜치 기준으로만 동작하므로, dev 머지 뒤 `gh workflow run concentration-sync` 로 1회 수동 트리거 → CT110 `SELECT max(collected_at) FROM spot_concentration` 가 오늘 날짜인지 확인. (로컬에서는 CT110 ssh 접근이 없어 미실행.)
