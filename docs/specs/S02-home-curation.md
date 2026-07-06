# S2 — 홈 피드 + 큐레이션 상세 (화면 설계)

> 세션 S2. 입력: `session-context.md`(잠긴 결정·제약), `design-brief.md`,
> 목업 `docs/mockups/05-home.html`·`06-curation.html`. 설계 원칙: 화면/UX/네비/API
> 형태는 백지에서 이상적으로, DB/인프라는 후속 세션(S7~S10)에서 reconcile.
> 이 문서는 **두 화면의 완전 명세 + 큐레이션 엔티티 비공식 스케치**다. 형식 DB/API는
> S7/S9가 종합한다.

## 잠긴 전제 (재논의 금지)

- **큐레이션 = 1급 엔티티** (`curations` + `curation_spots`), region/mood/editorial 한 구조.
- **홈 = 백엔드 주도** — `/home/feed`가 히어로+레일을 서버 조립 → 앱 재배포 없이 편성 교체.
- 홈 히어로 = published **region** 큐레이션, 무드 레일 = **mood** 큐레이션.
- 표지/카피/스팟순서는 DB 적재, 표지는 spot의 KTO URL **참조**(다운로드 금지).

## 이 세션에서 확정한 결정 (9)

1. **Feed 구성 고정** — `/home/feed`는 히어로 정확히 **6**(region), 무드 레일 정확히
   **3**(mood)을 반환. 편성 교체 = 서버가 각 슬롯에 어떤 큐레이션을 넣을지 바꾸는 것;
   개수는 불변. 클라이언트는 항상 6 세그먼트 + 3 섹션을 렌더.
2. **레일/그리드 스팟 소스 = 손픽 우선, 빈 경우 테마-일치 품질게이트 랭킹** — 스키마는
   `curation_spots`(손픽·순서, 1급). 큐레이션에 손픽 스팟이 없으면 서버가 **테마 일치
   풀**에서 채움: region 큐레이션 → 해당 지역 스팟, mood 큐레이션 →
   `spot_moods` 태그 스팟. 나중에 `curation_spots`를
   채우면 자동 채움을 덮어씀(코드 변경 없이 데이터만).
   **[정정 — S11 §7-B, 사용자 승인 2026-06-21]** 순수 랜덤(`ORDER BY hash`) 폐기 →
   **품질게이트 랭킹**: `first_image_url` 보유를 **필수 게이트**, `show_flag = 1` 필수,
   `overview` 보유 + 임베딩 보유를 **가산점**으로 풀을 품질순 정렬한 뒤 **상위 버킷(top ~30)**
   안에서 **결정적 seed**(`hash(curation_id, KST date)`)로 8개 선택·회전. 결정성·**일 단위
   캐시**·일 회전을 유지해 홈 새로고침마다 스팟이 바뀌는 깜빡임을 방지(같은 날은 동일 구성).
3. **표지 = `cover_spot_id` 참조 + 자동 폴백** — 큐레이션에 `cover_spot_id`(FK) 저장 →
   read-time에 그 스팟의 대표 이미지(`firstimage`) KTO URL로 해석. null이면
   `curation_spots[0]`(또는 채움 풀 첫 스팟)의 이미지로 폴백. 이미지 바이트는 저장하지 않음.
   - **[추가 — S11 §5, 사용자 승인 2026-06-21]** 피드 **조립 시점에 표지 cover image URL이 non-null인지
     검증**하고, null이면 **폴백 표지(2순위 스팟)**의 이미지를 사용. 끝까지 해석 불가한 히어로/커버는
     방어적으로 제외(커버 없는 카드 노출 금지).
4. **편집 필드 = `{title, subtitle, lead, intro, cover_spot_id, ordered spots}`** — eyebrow
   없음(목업 미사용). `title`은 편집자 줄바꿈(`\n`)을 verbatim 저장하고 `pre-line`로 렌더.
5. **히어로 캐러셀 = 수동 스와이프 + 페이징 스냅 + 6분할 인디케이터, 자동전환 없음** —
   타이머/루프 없음. 스크롤 위치로 active 세그먼트 갱신.
6. **상세 더보기 = intro 카피 펼침** — `intro`는 기본 3줄 클램프, 셰브론 탭 → 전체 intro
   펼침(다시 탭 → 접기). 그리드는 항상 그 아래.
7. **mood 큐레이션 = 홈 레일 인라인 전용** — 자체 상세 페이지 없음. 레일 헤더 비탭(목업도
   화살표 없음). 카드 탭 → 스팟 상세(07). 상세 레이아웃(06)은 **region 큐레이션 전용**.
8. **스팟 수 = 레일 ≤8 가변 · region 상세 그리드 8** — 레일은 **최대 8**을 내리되 손픽/풀이
   얕으면 받은 만큼 렌더(목업 05는 레일당 3 노출 + 가로 스크롤; "정확히 8" 강제 아님).
   payload = 히어로 6(커버만) + 레일 3×(≤8). 빈 카드/플레이스홀더로 채우지 않음.
9. **상태 = 레이아웃 스켈레톤 패키지** — §상태 처리 참조.

---

## 큐레이션 엔티티 (비공식 스케치 — S7이 형식화)

```
curation
  id            uuid/serial
  type          enum: region | mood | editorial   ← 이 화면들은 region·mood만 사용. editorial=후속
  slug          text  (안정 식별·딥링크용)
  title         text  (줄바꿈 verbatim, pre-line)
  subtitle      text  (홈 히어로 sub / 무드 레일 subhead)
  lead          text  nullable   (상세 리드문 — region만)
  intro         text  nullable   (상세 본문 단락 — region만)
  cover_spot_id fk spots nullable (null → curation_spots[0] 폴백)
  is_published  bool
  position      int   (홈 슬롯 정렬; type별로 정렬)
  region_id     fk regions nullable (type=region일 때 랜덤 풀 스코프)
  mood_id       fk moods   nullable (type=mood일 때 랜덤 풀 스코프)
  created_at / updated_at

curation_spots                       ← 손픽·순서 (비면 서버가 랜덤 채움)
  curation_id   fk curation
  spot_id       fk spots
  position      int
  PK (curation_id, spot_id)
```

**타입별 필드 적용성**

| 필드 | region (히어로+상세) | mood (레일) |
|---|---|---|
| `title` | ✓ 히어로/상세 타이틀 | ✓ 레일 헤더 |
| `subtitle` | ✓ 히어로 sub | ✓ 레일 subhead |
| `lead` | ✓ 상세 | — (null) |
| `intro` | ✓ 상세 | — (null) |
| `cover_spot_id` | ✓ 히어로 배경·상세 커버 | — 레일은 큐레이션 커버 미렌더(스팟 썸네일만) |
| `curation_spots` | ✓ 상세 그리드 8 | ✓ 레일 카드 8 |

**자동 채움 규칙** (손픽이 비었을 때만, 결정적·일 캐시)

> **[정정 — S11 §7-B]** 아래 `ORDER BY hash` 스케치는 **순수 랜덤이 아니라 품질게이트 랭킹**으로
> 대체됨: `first_image_url` 보유 필수 게이트 + `show_flag = 1` 필수, `overview`/임베딩 보유 가산으로
> 품질 정렬 → 상위 버킷(top ~30)에서 `hash(curation_id, KST date)` seed로 8개 선택·회전.

- region: 품질순 정렬된 `WHERE region_id = :rid AND first_image_url IS NOT NULL AND show_flag = 1` 풀의
  상위 버킷에서 `hash(curation_id, KST date)`로 8개 선택
- mood:   품질순 정렬된 `JOIN spot_moods WHERE mood_id = :mid AND first_image_url IS NOT NULL AND show_flag = 1`
  풀의 상위 버킷에서 동일 seed로 8개 선택
- 손픽 < 목표수(8)면 손픽 먼저, 모자란 만큼만 같은 풀에서 채울지(보충)는 v1 미사용 —
  손픽이 있으면 손픽만, 없으면 전량 품질게이트 랭킹(단순 규칙). 보충은 후속에 열어둠.
- 결과를 Redis에 `curation:{id}:spots` (TTL ~24h)로 캐시 가능 — S8 인프라에서 확정.

---

## 히어로 6 카피 레지스트리 (목업 05 verbatim — 시드 SSOT)

`\n` = 줄바꿈(`&#10;`, pre-line 렌더). region 큐레이션 시드 스크립트의 `title`/`subtitle` 원본.

| # | region | `title` | `subtitle` |
|---|---|---|---|
| 1 | 제주 | `제주, 매일 가도\n새로운 섬` | 제주에서 가장 사진 잘 받는 곳 → |
| 2 | 부산 | `바다 끝에서\n부산` | 해안선부터 야경까지, 부산 한 바퀴 → |
| 3 | 강릉 | `동해 보러\n강릉` | 파도 소리 들리는 동해 스폿 → |
| 4 | 전주 | `느리게 걷는\n전주` | 한옥 골목을 천천히 걷기 → |
| 5 | 경주 | `천년을 걷는\n경주` | 시간이 멈춘 듯한 신라의 도시 → |
| 6 | 여수 | `밤바다의\n여수` | 불빛 가득한 남해 항구 → |

> `subtitle` 끝 "→"는 탭 어포던스 표식(상세 06 이동). 카피는 편성 교체 시 DB에서 바뀜.

---

## 화면 05 — 홈 (큐레이션 피드)

탭바 4탭(홈·지도·사진·마이) 중 **홈 탭**. 앱의 앵커 화면.

### 목적
사용자가 들어오면 곧장 "어디로 사진 찍으러 갈까"를 보여주는 에디토리얼 피드. 지역
큐레이션(히어로)으로 영감을 주고, 무드 레일로 테마별 스팟을 빠르게 탐색하게 한다.
서버가 편성을 주도하므로 앱 업데이트 없이 큐레이션을 교체한다.

### 구성요소 (위→아래)
1. **상태바** — 시스템.
2. **워드마크 토픽바**(sticky) — "PicTrip" 워드마크. 비인터랙티브, 스크롤 시 상단 고정.
3. **히어로 캐러셀** — 6개 region 큐레이션. 각 카드 = 풀폭 이미지(≈402×314, landscape
   crop) + 하단 스크림 그라데이션 + `title`(2줄, pre-line, 흰색) + `subtitle`("… →").
   가로 스냅 스와이프.
4. **6분할 인디케이터** — 이미지 바로 밑, 풀폭, 4px gap. active=잉크, 나머지=line. 현재
   히어로 인덱스 반영.
5. **무드 레일 × 3** — 각 섹션 = divider + `title`(sec-title) + `subtitle`(sec-sub) +
   가로 레일(185px 정사각 카드 **최대 8개**, 목업 노출 3 + 가로 스크롤). 카드 = thumb + 스팟명(`title`) + 세분 카테고리(`category`).
6. **푸터** — inset 배경 + 링크(이용약관·개인정보). (히어로/레일 아래, 탭바 위.) 둘 다 법적고지(16)로. **"문의" 링크는 제거**(목적지 없는 고아 — 고객센터/문의 화면이 비목표라 착지점이 없음).
7. **하단 탭바** — 홈(active)·지도·사진·마이.

### 데이터 needs (비공식)
- `GET /home/feed` →
  - `heroes[6]`: `{ id, slug, title, subtitle, coverUrl }`  (스팟 목록 없음 — 가벼움)
  - `rails[3]`:  `{ id, title, subtitle, spots[≤8 가변]: <스팟 카드> }`
- **스팟 카드(canonical)** = `{ contentId, title, category, firstImageUrl }` — 백엔드/모바일/S3와
  동일 작명(KTO명+camelCase). ~~`{spot_id,name,image_url}`~~ 폐기.
  - **[추가 — S11 §7-A 혼잡도 재융합, 사용자 승인 2026-06-21]** canonical 카드에 **선택 확장 필드**
    `congestion: "low"|"medium"|"high"|null` 추가. `spot_concentration`(KTO 15128555 집중률 예측,
    향후 30일 상대집중률 0~100, 100=가장 붐빔)에서 오늘값 `v`를 버킷팅: `v<34`→`low`(한산) /
    `34≤v≤66`→`medium`(보통) / `v>66`→`high`(붐빔), 데이터 없으면 `null`(배지 숨김). 트렌딩
    화면/엔드포인트는 계속 제거 — 데이터는 카드 enrichment로만 노출. canonical 카드를 쓰는 모든
    곳(홈 레일·상세 그리드 등)에 동일 적용. UI = 무채색 텍스트 칩/톤("한산/보통/붐빔"), `null`이면
    숨김(honest-minimal). **필드 권위 정의는 S9, DB 조인은 S7.**
- 모든 이미지 = KTO URL(다운로드 X). `category` = **세분 카테고리 라벨**(해변/카페/자연… =
  `lcls_systm3_nm`); 무드 큐레이션의 테마 분류와는 별개.

### 상태
- **loading**: 레이아웃 스켈레톤 — 히어로 자리 314px `--skeleton` 블록 + 인디케이터 자리 +
  3개 레일 섹션의 제목 바·정사각 썸네일 플레이스홀더. 스피너 없음.
- **normal**: 위 구성.
- **per-image**: 각 KTO 이미지 lazy-load, 로드 전 `--inset` 배경; 이미지 4xx/실패 →
  inset-gray 유지(깨진 아이콘 없음).
- **partial**: 어떤 레일의 (손픽+품질채움) 스팟이 8 미만이면 가진 만큼만 렌더. 스팟이 0개로
  떨어지는 레일/커버 해석 불가한 히어로는 방어적으로 제외(서버는 항상 채워 6/3을 보내는 게 목표).
  - **[추가 — S11 §6, 사용자 승인 2026-06-21]** (손픽+품질채움) 스팟이 **3개 미만**이면 해당 레일을
    **생략**(빈약한 레일 노출 금지, 밀도 안정). 즉 레일은 ≥3 스팟일 때만 렌더.
- **empty**: `/home/feed`가 히어로·레일 모두 0(정상 운영에선 발생 X) → 소프트
  플레이스홀더("곧 새로운 큐레이션을 준비할게요"). 빈 화면 노출 금지.
- **error**: feed fetch 실패(네트워크/5xx) → 풀화면 에러 + 재시도 버튼(무채색, 라인 아이콘,
  이모지 없음). **pull-to-refresh로 재요청** 가능.

### 진입/이탈 네비
- 진입: 탭바 홈 탭(앱 기본 진입), 다른 화면에서 홈 탭 복귀.
- 이탈:
  - **히어로 탭** → 큐레이션 상세(06), 해당 region 큐레이션. (sub의 "→"가 탭 어포던스.)
  - **무드 레일 카드 탭** → 스팟 상세(07).
  - **무드 레일 헤더**: 비탭(이동 없음).
  - **탭바**: 지도(11)·사진(08)·마이(14).
  - **푸터 링크**: 약관/법적고지(16).

### 인터랙션
- 히어로: 가로 스와이프(페이징 스냅), 손가락 떼면 가장 가까운 히어로에 정착, 인디케이터
  active 갱신. 자동전환 없음. 탭 = 상세 이동.
- 레일: 독립 가로 스크롤(스냅 없음, 자유 스크롤로 다음 카드 peek). 세로 스크롤로 섹션 이동.
- pull-to-refresh: 전체 feed 재요청(랜덤은 일 캐시라 같은 날엔 동일 구성 유지).
- 탭바/푸터: 표준 네비.

---

## 화면 06 — 큐레이션 상세 (region 전용)

히어로에서 진입. 한 지역 큐레이션의 카피 + 8스팟 그리드.

### 목적
선택한 region 큐레이션을 에디토리얼하게 펼친다: 큰 타이틀·세로 커버·리드문·본문으로
분위기를 전하고, 대표 스팟 8개를 그리드로 보여 스팟 상세로 보낸다.

### 구성요소 (위→아래)
1. **상태바** — 시스템.
2. **네비 바** — 좌: 뒤로(원형 fill 버튼), 우: 공유(원형 fill 버튼). 타이틀 없음.
3. **타이틀** — 가운데 정렬, `title`(pre-line 줄바꿈), 큰 굵은 잉크.
4. **커버** — 세로 4:5, 라운드 16, `cover_spot_id` 해석 이미지(또는 폴백).
5. **리드문** — 가운데, `lead`(굵은 한 줄).
6. **본문(intro)** — 가운데, 기본 **3줄 클램프**. 길면 잘림.
7. **더보기 셰브론** — 가운데 아래 화살표. 탭 → intro 전체 펼침(재탭 → 접기). intro가 3줄
   이하면 셰브론 숨김.
8. **스팟 그리드** — 2열, 8개(`curation_spots` 순서; 비면 랜덤 8). 각 카드 = 정사각 이미지 +
   스팟명(`nm`) + 카테고리(`cat`).

### 데이터 needs (비공식)
- `GET /curations/{id}`(또는 `/{slug}`) →
  `{ id, type, title, lead, intro, coverUrl, spots[≤8]: <스팟 카드> }` (스팟 카드 = 위 canonical).
  - **`subtitle`은 상세(06) 응답에서 생략** — 목업 06엔 subtitle 요소가 없음(히어로/레일 전용 필드).
- `coverUrl` = `cover_spot_id`의 `firstImageUrl`(없으면 `spots[0].firstImageUrl`).
- 모든 이미지 KTO URL.

### 상태
- **loading**: 스켈레톤 — 타이틀 바, 4:5 커버 블록, 리드/본문 라인, 8개 정사각 그리드
  플레이스홀더(`--skeleton`). 뒤로 버튼은 즉시 동작.
- **normal**: 위 구성.
- **per-image**: 커버·그리드 각 이미지 lazy-load + inset-gray 폴백.
- **empty**: 스팟 0개(정상 운영에선 발생 X — 랜덤 채움) → 그리드 자리에 소프트 안내.
- **error**: fetch 실패 → 본문 영역 에러 + 재시도(뒤로 버튼 유지).
  **404**(미published/삭제) → "큐레이션을 찾을 수 없어요" + 뒤로.

### 진입/이탈 네비
- 진입: 홈 히어로 탭. (딥링크 `slug`도 같은 화면을 열 수 있게 설계 — 인프라는 S8.)
- 이탈:
  - **뒤로** → 홈(05).
  - **공유** → OS 공유 시트(큐레이션 `title` + 딥링크 URL). KTO: URL 공유는 허용. 딥링크
    스킴/웹 URL 형식은 S8에서 확정.
  - **그리드 카드 탭** → 스팟 상세(07).

### 인터랙션
- 세로 스크롤. 더보기 셰브론 = intro 펼침/접기(인라인, 화면 이동 없음).
- 공유 버튼 = 공유 시트.
- 카드 탭 = 스팟 상세.

---

## API 형태 (비공식 — S9가 형식화)

JSend 엔벨로프 `{ data, error, meta }`(`ok()`/`err()`), `AppError` 코드 분기 전제.

- `GET /home/feed` → `{ heroes: [6], rails: [3] }` (위 데이터 needs).
  - **[선택 — S11 §5, 사용자 승인 2026-06-21]** 향후 슬롯 개수/순서 변경에 대비해 피드 페이로드를
    **순서 있는 타입드 블록 배열**(예: `blocks: [{type:"hero", ...}, {type:"rail", ...}]`)로 표현하는
    안을 보험으로 열어둠. **v1 강제 아님** — v1은 위 고정 `{heroes,rails}` 형태 유지.
- `GET /curations/{id|slug}` → 단일 큐레이션 + 스팟. 404 = `AppError`(NotFound).
- 둘 다 위 **canonical 스팟 카드**(`{ contentId, title, category, firstImageUrl }`)를 공유 —
  스팟 상세(07, S3)·지도(S5)·저장(S6)과 동일 형태(백엔드 실제 직렬화와 일치).

## 비목표 / 경계 (이 화면 한정)

- editorial 타입 큐레이션은 스키마에 존재하나 이 두 화면은 미사용(후속 편성에서 슬롯 확장 시).
- 무드 큐레이션 상세 페이지 없음. "더보기 → 무드 전체보기" 진입점 없음.
- 텍스트 검색·트렌딩·코스·today-inspo·알림 진입점 없음(비목표 확정).
- 손픽 부족분 보충(랜덤 보충) 규칙 v1 미사용 — 손픽 전량 또는 랜덤 전량.

## Reconcile 메모 (이상 설계 ↔ 현 자산 — S10이 종합)

- **신규 테이블**: `curations`, `curation_spots`. 기존 자산 위에 얹음(폐기 없음).
- **재사용 자산**: `spots`(~68k)·`spot_images`(`firstimage`→커버/카드 이미지)·
  `spot_moods`(mood 랜덤 풀)·`regions`/`sigungus`(region 랜덤 풀·스코프). `spot_embeddings`는
  이 화면 불사용(사진검색/유사도는 S4).
- **KTO 컴플라이언스**: 이미지 URL만 저장/참조, `overview` 등 텍스트 verbatim, 다운로드 금지.
- **마이그레이션 방향**: `curations`/`curation_spots` 추가 Alembic revision + region/mood
  큐레이션 시드 스크립트(카피·`cover_spot_id`·손픽 스팟). 초기엔 손픽 비우고 랜덤으로
  운영 → 이후 손픽 적재. 인덱스: `curations(type, is_published, position)`,
  `curation_spots(curation_id, position)`. (정확한 DDL은 S7.)
- **제거되는 것**: 기존 홈 하드코딩 무드 그리드/레지스트리(`features/home` 하드코딩) →
  `/home/feed` fetch로 전환. `/spots/by-region`은 큐레이션이 대체(비목표).
