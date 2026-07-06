# S3 — 스팟 상세 화면 설계

> 세션: S3 · 목업: `docs/mockups/07-spot.html` · 작성일 2026-06-20
> 입력 SSOT: 목업(무채색) · `CLAUDE.md`(제약) · `design-brief.md`
> 설계 원칙: 화면/UX/네비/API 형태는 백지에서 이상적으로, DB·인프라는 reconcile.

스팟 상세는 **세로 스크롤 1화면**이다. 비로그인(게스트)도 전체 열람 가능하며,
저장만 인증을 요구한다. KTO 부가정보(overview·갤러리·intro)는 **지연 fetch(7일
캐시)**라 화면은 2계층 로딩 모델을 갖는다.

---

## 1. 목적

- 한 스팟의 사진·소개·위치·연락 정보를 한 화면에서 보여주고, **저장·공유·
  지도 연결·주변 탐색**으로 이어지는 행동을 유도한다.
- KTO 데이터를 **verbatim**(특히 `overview`)으로 존중하면서, 데이터가 없는 부분은
  honest-minimal하게 **조용히 생략**한다(가짜/죽은 콘텐츠 금지).

## 2. 진입 / 이탈 네비게이션

**진입점**
- 홈 큐레이션 피드(05) · 큐레이션 상세(06) · 지도 내 주변(11) · 저장(13) ·
  사진 검색 결과(10) · 본 화면의 "주변 둘러보기" 레일(자기참조).
- 딥링크(`pictrip://spots/{contentId}` 류) — 진입 카드 데이터 없음.

**이탈**
- 뒤로(스티키 헤더 또는 스와이프) → 이전 화면.
- 주변 레일 카드 탭 → 다른 스팟 상세(스택 push).
- 지도 미리보기/외부 버튼 탭 → 카카오·네이버 지도 외부 앱/웹.
- 게스트 저장 탭 → 03-login 모달(성공 시 복귀).

## 3. 레이아웃 (위→아래)

```
[히어로]  풀블리드 이미지 + 위→아래 스크림
  · 좌상단 뒤로(‹)  우상단 저장(북마크)  ← 둥근 glass 컨트롤
  · 제목 (큰 굵게, 2줄 max)
  · 서브라인  "카테고리 · 지역명 시군구명"
  · 갤러리 스트립 (가로 스크롤, 첫 타일 와이드)
  · "전체 사진 {n}" glass 버튼  (n = images.length; images 없으면 스트립·버튼 숨김)
[소개]        overview verbatim · 4줄 클램프 + 더보기/접기
[대표 메뉴]   음식점일 때만 (firstmenu 칩 + treatmenu 텍스트)
[위치]        KakaoWebMap 정적 미리보기 + 네이버/카카오 버튼 + 정보행 4개
[방문 예정?]  inset CTA — 공유 + 스크랩 카드
[주변 둘러보기] /map/nearby 사진 레일 (가로 스크롤)
[스티키 헤더]  스크롤 시 페이드인 — 뒤로 + 제목 + 저장 (오버레이)
```

---

## 4. 구성요소별 명세

### 4.1 히어로 & 스크롤 (결정 1·2·3)

- 히어로 = `firstImageUrl` 풀블리드 배경 + 위→아래 스크림(텍스트 가독성). 그 위:
  - **뒤로(‹)** 좌상단, **저장(북마크)** 우상단 — 둥근 반투명 glass 컨트롤.
  - **제목** = `title` (2줄 max).
  - **서브라인** = `category · regionName sigunguName` (스팟 기본 행에서 즉시 표시).
  - **혼잡도 배지(congestion)** — 서브라인 근처에 무채색 텍스트 칩 한 줄로 노출
    (low=한산 / medium=보통 / high=붐빔). `congestion`이 null이면 칩 자체를 숨김
    (honest-minimal). 데이터 = `spot_concentration`(KTO 향후30일 상대집중률) 유래,
    필드 권위 정의=S9, DB 조인=S7 (S11 §7-A).
  - 한 줄 설명(teaser) 없음 — KTO가 태그라인을 주지 않고 68k 스팟에 카피가 없어,
    지어내거나 overview를 발췌하면 verbatim 정신·정직성·레이아웃 안정성에 어긋남(결정 3).
- **스크롤 전환**: 히어로 컨트롤은 이미지와 함께 스크롤되어 사라지고, **제목이
  상단을 지나는 순간** 흰색 솔리드 **스티키 헤더**가 크로스페이드.
  스티키 = `[‹  잘린 제목  ▢저장]` (잉크 색, 공유 없음). 임계점 ≈ 히어로 높이 − 100.
- **저장·공유 배치** (모두 동일 상태 동기화):
  - 저장(스크랩): 히어로 우상단 · 스티키 · '방문 예정?' 인셋 카드 — **3곳**.
  - 공유: '방문 예정?' 인셋 카드 — **1곳**(목업대로 스티키엔 없음).

### 4.2 소개 (overview) (결정 4)

- `overview`를 **verbatim** 표시(수정·요약·재배열 금지).
- 기본 **4줄 클램프** + 인라인 **더보기/접기** 토글(더보기=펼침, 접기=재클램프).
- 본문이 4줄 이하면 토글 숨김.
- `overview` 없음(unavailable) 처리 → §6 상태.

### 4.3 대표 메뉴 (음식점 전용) (결정 10)

- **조건**: `intro.firstmenu` 또는 `intro.treatmenu` 가 존재할 때만 표시.
  백엔드가 메뉴 필드를 `content_type_id=39`에만 채우므로 클라이언트는
  타입 검사 없이 **존재 여부만** 본다.
- **위치**: '소개' 바로 아래(음식점에선 메뉴가 핵심 정보).
- **렌더**:
  - `firstmenu` → "대표 메뉴", 쉼표/`<br>` 분리해 **칩** 목록.
  - `treatmenu` → "취급 메뉴", 정리한 **텍스트**.
  - KTO 메뉴 문자열은 messy(HTML 태그/`<br>`/쉼표 혼재) — `overview`와 달리
    보호 대상이 아니므로 가벼운 정리 허용(태그 strip, 구분자 분리).
- 둘 다 없으면 섹션 자체 없음.

### 4.4 위치 (지도 + 외부 링크 + 정보행) (결정 6·7)

- **지도 미리보기**: KakaoWebMap(WebView+Kakao JS SDK) **정적** — 스팟 중심 핀 1개,
  제자리 인터랙션 없음(세로 스크롤 제스처 충돌 회피). 탭 → 카카오 지도 외부.
  (`@react-native-kakao/map` 뷰 금지. 가짜 지도 플레이스홀더는 honest-minimal 위반이라 불가.)
- **외부 버튼 2개**: 네이버 지도 / 카카오 지도 — **좌표 기반 딥링크 + 웹 폴백**.
  - 카카오: `kakaomap://look?p={lat},{lng}` → 폴백 `https://map.kakao.com/link/map/{title},{lat},{lng}`
  - 네이버: `nmap://place?lat={lat}&lng={lng}&name={title}&appname=org.pictrip`
    → 폴백 `https://m.map.naver.com/...`
  - `lat = mapy`, `lng = mapx` (KTO EPSG:4326). KTO엔 네이버/카카오 place id가
    없으므로 **좌표 기반** 링크 사용. `Linking.openURL`(app scheme→web), 새 네이티브 없음.
- **정보행 4개** (목업 충실, null 행 숨김):
  | 행 | 출처 | 탭 인터랙션 |
  |---|---|---|
  | 주소 | `addr1` (스팟 기본 행, 항상 존재) | 복사 + 토스트 |
  | 이용시간 | `intro.usetime` | — |
  | 전화 | `tel` 우선, null이면 `intro.infocenter` 폴백 | 다이얼 `tel:` |
  | 홈페이지 | `homepage` (도메인만 표시, 밑줄) | 외부 브라우저로 전체 URL |
  - 휴무일(`restdate`)·주차(`parking`)는 **표시하지 않음**(목업 미포함).

### 4.5 방문 예정? (inset CTA) (결정 2)

- 배경 inset(연그레이) 블록. 헤드라인 "{제목}에 방문 예정이신가요?"
- **공유** 카드 + **스크랩** 카드 2개. 스크랩=저장 토글(§4.7과 동일 상태).

### 4.6 갤러리 & 전체 사진 뷰어 (결정 5)

- **스트립**(히어로 내): `images[].originImageUrl` 목록(히어로 배경 `firstImageUrl`은
  별도). 첫 타일 와이드(≈300px), 나머지 narrow(≈108px), 가로 스크롤. 타일 탭 = 그
  인덱스로 뷰어 오픈.
- **"전체 사진 {n}"** glass 버튼(n = `images.length`) → **심플 스와이프 페이저**(전체화면 모달):
  - 좌우 스와이프, `n / 총장` 인디케이터, 탭 또는 아래로 스와이프 닫기. **줌 없음.**
  - 새 네이티브 모듈 없이 RN `Modal` + 핀고정 gesture-handler/reanimated 가로 페이징.
- `images` 0장 → 스트립·"전체 사진" 버튼 숨김(히어로 배경만). 히어로 이미지 처리 → §6.

### 4.7 저장 (게스트 넛지) (결정 2·9)

- 저장 = `POST/DELETE /users/me/saved/{contentId}` 토글. 히어로·스티키·인셋 3개
  진입점 모두 **단일 상태**를 공유(낙관적 토글 + 실패 시 롤백 토스트). 채울 때만
  토스트("스크랩했어요"), 해제는 조용히.
- **게스트가 저장 탭 시**: 로그인 시트 → `03-login` 제시.
  - **pending intent 없음**: 로그인 성공 후 상세로 복귀해도 **자동 저장하지 않음**.
    사용자가 저장을 **다시 탭**해야 적용된다(S6 게스트 하트 패턴과 통일).
  - S1의 "보류 액션 재개"는 진입 퍼널 CTA(사진선택) 한정 — 상세 저장엔 적용 안 함.
  - 모달 취소 시 저장 미수행, 상세 그대로.

### 4.8 주변 둘러보기 레일 (결정 8)

- 데이터 = **`/map/nearby`** (스팟 좌표 `mapx`/`mapy` 기준, 거리순 최근접 N개,
  **자기 자신 제외**). 카드 = 사진 + 이름 + **세분 카테고리 라벨**.
- **혼잡도 배지(congestion)** — 카드에 데이터가 있을 때만 무채색 텍스트 칩으로 표시,
  null이면 숨김(상세 히어로와 동일 규칙). canonical 카드 확장 필드 `congestion`
  (low/medium/high|null) 사용 (S11 §7-A).
- 비어 있거나 에러면 섹션 **조용히 숨김**(보조 콘텐츠).
- 카드 탭 → 해당 스팟 상세 push.
- *reconcile 필요(§7): 현재 `/map/nearby` 카드 `category`는 coarse 버킷
  (attraction/food/cafe…)이라 목업의 세분 라벨(식물원/해변/음식점/카페)과 불일치 →
  nearby 카드에 `lcls_systm3_nm`(세분 라벨) 추가 또는 전용 rail 필드 도입.*

---

## 5. 데이터 needs (비공식 스케치)

`GET /spots/{contentId}` → `SpotDetailResponse`:
- 기본(즉시): `contentId`, `title`, `firstImageUrl`, `category`, `regionName`,
  `sigunguName`, `addr1`, `mapx`, `mapy`
- 지연 enrich: `overview`, `homepage`, `tel`, `images[]`(originImageUrl),
  `intro{usetime, restdate, parking, infocenter, firstmenu, treatmenu}`,
  `detailStatus`(`fresh|stale|unavailable`)
- (현 응답엔 `moods[]`도 있으나 본 화면 미사용)

추가 호출:
- `GET /map/nearby?lat&lng` → 주변 레일 (카드에 세분 카테고리 라벨 필요 — §7)
- `POST /users/me/saved/{id}` · `DELETE /users/me/saved/{id}` → 저장 토글
- 인증 상태(게스트 여부)는 클라이언트 auth 스토어에서.

> 형식화는 S9(API 계약) 세션에서. 여기서는 needs만 명시.

---

## 6. 상태 (loading / normal / empty / error) (결정 11·12)

### 6.1 로딩 — 프로그레시브
- **카드 진입**: 진입 카드 데이터로 **히어로(제목·이미지·서브라인) 즉시 페인트**
  (TanStack `placeholderData`로 리스트 캐시 시드). 지연 파트(소개·메뉴·갤러리·정보행·
  레일)만 **섹션 스켈레톤** 후 `/spots/{id}` 도착 시 채움.
- **딥링크(카드 없음)**: 히어로 포함 **풀 스켈레톤** → 응답 후 전체 렌더.
- 주변 레일은 별도 쿼리 — 로딩 중 카드 스켈레톤.

### 6.2 정상 — `detailStatus = fresh` 또는 `stale`
- `fresh`/`stale` 모두 캐시 콘텐츠를 **동일하게** 표시(`stale`는 조용히 제공,
  사용자 노출 인디케이터 없음).

### 6.3 빈/부분 — `detailStatus = unavailable` (KTO 실패 + 캐시 없음)
honest-minimal **숨김** 원칙, 핵심만 재시도:
- `overview` 없음 → '소개' 섹션에 **인라인 "정보를 불러오지 못했어요 · 다시 시도"**
  1개(소개는 핵심이라 예외적으로 재시도 노출).
- `intro`(메뉴) 없음 → 메뉴 섹션 없음.
- `images` 없음(+`firstImageUrl`도 null) → 히어로 = **무채색 플레이스홀더**
  (제목·서브라인 유지, 갤러리·전체사진 숨김). `firstImageUrl`만 있고
  `images` 비면 히어로 배경만 표시하고 스트립·"전체 사진" 버튼은 숨김.
- 위치는 `addr1`·좌표가 **항상 존재**하므로 지도 미리보기 + 주소행 항상 유지.
- 주변 레일 빈/에러 → 섹션 **조용히 숨김**.

### 6.4 에러 (화면 단위)
- 스팟 404(존재하지 않음) → **전체화면** "존재하지 않는 장소입니다" + 뒤로.
- 네트워크 에러(`/spots/{id}` 실패, 캐시 없음) → **전체화면** 재시도.
- 저장 토글 실패 → 낙관적 롤백 + 토스트(화면 유지).

---

## 7. Reconcile 노트 (이상 설계 → 현 자산/제약)

대부분 현 백엔드/모바일과 정합. 차이/조정 지점:

1. **주변 레일 카테고리 라벨** — 목업은 세분 라벨(식물원/해변/음식점/카페).
   현 `/map/nearby` `NearbySpotCard.category`는 coarse 버킷(attraction/food/cafe/
   leisure/shopping). → nearby 카드에 `lcls_systm3_nm` 세분 라벨 추가(또는 rail 전용
   응답 필드). DB: `spots.lcls_systm3` → `lcls_systm_codes.lcls_systm3_nm` 조인.
2. **crowd 필드 제거 → S11 §7-A로 congestion 재도입(정정)** — 과거 reconcile은
   `NearbySpotCard.crowd`(혼잡도)를 비목표로 보고 미사용·미표시로 정리했으나,
   S11 §7-A(2026-06-21 승인)에서 **혼잡도를 `congestion` 필드로 재도입**한다.
   `spot_concentration`(KTO 15128555 집중률 예측, 향후30일 상대집중률 0~100) 보존,
   트렌딩 화면은 계속 제거하고 데이터는 카드/상세 enrichment로만 사용. canonical 카드
   확장 필드 `congestion: "low"|"medium"|"high"|null`(v<34→low 한산 / 34~66→medium
   보통 / >66→high 붐빔, 없으면 null=숨김), 무채색 텍스트 칩으로 표시. 필드 권위 정의
   =S9, DB 조인=S7. → 본 화면 §4.1(히어로)·§4.8(주변 레일)에 배지 슬롯 반영.
3. **`info_data` 미사용** — `spot_details.info_data`(JSONB)는 현재 미적재.
   정보행은 `addr1`/`tel`/`homepage`(detailCommon2) + `intro`(detailIntro2)로 충분 →
   본 화면은 `info_data` 불필요.
4. **`moods[]`** — 상세 응답에 포함되나 본 화면 미사용(제거는 API 정리 세션에서 판단).
5. **`overview` verbatim** — 소개 본문만 사용하며 발췌/요약 없음(히어로 teaser 제거, 결정 3).
6. **이미지 URL only** — 히어로·갤러리·레일 모두 KTO URL 직접 렌더, 바이트 저장 없음.

---

## 8. 결정 로그 (이 세션)

| # | 결정 | 선택 |
|---|---|---|
| 1 | 스크롤 시 상단 컨트롤 | 스티키 헤더 크로스페이드(뒤로+제목+저장) |
| 2 | 저장·공유 배치 | 저장=히어로+스티키+인셋(3곳) / 공유=인셋(1곳) |
| 3 | 히어로 teaser | 제거(데이터 정직성·레이아웃 안정성·전 진입경로 일관성) |
| 4 | 소개 클램프 | 4줄 + 인라인 더보기/접기 |
| 5 | 전체 사진 뷰어 | 심플 스와이프 페이저(줌 없음) |
| 6 | 정보행 | 목업 4행(주소/시간/전화/홈페이지) + 탭 인터랙션, 전화 tel→infocenter 폴백 |
| 7 | 지도 미리보기 | KakaoWebMap 정적, 탭→외부; 외부 버튼 좌표 딥링크+웹 폴백 |
| 8 | 주변 레일 | `/map/nearby` 단일 레일 (reconcile: 세분 카테고리 라벨) |
| 9 | 게스트 저장 넛지 | 로그인 시트→03→복귀 후 수동 재탭(pending intent 없음, S6 통일) |
| 10 | 음식점 메뉴 | `firstmenu\|\|treatmenu` 존재 시, '소개' 아래, 칩+텍스트 |
| 11 | 로딩 전략 | 프로그레시브(히어로 즉시 + 섹션 스켈레톤) |
| 12 | 에러/빈 상태 | honest-minimal 숨김 + '소개'만 인라인 재시도; 404/네트워크 전체화면 |
