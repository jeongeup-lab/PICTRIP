# 여행 탭 — 조건 폐기 · 사진 진입구 · 동작하는 칩 재설계

- 날짜: 2026-07-26
- 대상: `backend/app/modules/agent`, `backend/app/modules/feed`,
  `backend/app/modules/spots`, `mobile/src/features/travel`
- 선행: [ADR 0009](../../adr/0009-travel-tab-conversational-agent.md)
- 실측 근거: `agent-axis-probe` 워크플로 run
  [30192987742](https://github.com/jeongeup-lab/PICTRIP/actions/runs/30192987742) ·
  [30193081228](https://github.com/jeongeup-lab/PICTRIP/actions/runs/30193081228)
  (2026-07-26, CT110 읽기 전용)

## 문제

여행 탭의 UI가 약속하는 축과 엔진이 실제로 거는 축이 어긋나 있다. 네 갈래로 드러난다.

1. **사진 진입구가 없다.** 앱의 이름값이자 유일한 기술 차별점(CLIP 매칭)이
   컴포저의 `+` 아이콘 뒤에 숨어 있다.
2. **조건 시트 3축 중 2축이 무동작이다.** `when`은 답변 문구에만 실리고
   (ADR 0009가 인정), `who`의 `solo`/`duo`는 빈 튜플이며 `kids`/`pets`는
   필터가 아니라 카테고리 몰래 바꿔치기다. 유일하게 진짜인 `region`은
   질문에 지역이 나오면 아무 표시 없이 무시된다.
3. **초기 칩 4개 중 2개가 거짓말이다.** `반려견과 갈 만한 곳`은 카테고리가
   비어 전국 아무거나 20곳, `제주 2박 3일`은 일정 조립기가 폐기됐는데도
   일정을 약속한다.
4. **후속 칩은 이전 턴을 잃는다.** `travel.tsx`의 `onSuggest`가
   `submit(text, null)`로 새 질문을 던지고 `AskRequest`에 대화 상태가 없다.
   `여수 바다` 결과에서 `더 한적한 곳`을 누르면 전국에서 한적한 20곳이 온다.
   문구가 비교급을 약속하는데 엔진에 비교 대상이 없다.

## 실측 — 엔진이 실제로 할 수 있는 것

### 카테고리 술어가 실내를 통째로 잘라내고 있다

`attraction_category_sql()`(`spots/services/nearby.py`, 지도 "주변 관광지"용)을
에이전트가 그대로 재사용한 결과:

| 중분류 | 스팟 | attraction 통과 |
|---|---|---|
| VE07 전시시설 (박물관 543 · 전시관 470 · 미술관/화랑 337 · 기념관 142 · 과학관 58) | 1,571 | **0** |
| VE06 공연시설 (공연장 318 · 영화관 17) | 335 | **0** |
| VE09 교육시설 (도서관 214) | 440 | 0 |
| SH06 시장 (상설 550 · 비상설 234) | 784 | 0 |

살아남은 실내는 `기타문화시설` 158곳 + `수족관/아쿠라리움` 19곳뿐이다.
그래서 `INDOOR_KEYWORDS` 6개 중 5개가 0곳이고, 유일하게 걸리는 `체험관`은
`lcls_systm1_nm ILIKE '%체험관%'`이 **`체험관광` 대분류에 substring 매칭**해
체험마을·체험농장·체험어장 1,629곳(야외)을 돌려준다.

### 집중률은 쓸 만하다

eligible 11,575곳 중 `spot_concentration` 보유 5,323곳(46.0%). 전국 무필터
기준 quiet(≤30%) 1,622곳 · popular(≥70%) 1,624곳. 제주 rated 264곳.
시도별 37~55%로 고르고, 세종 0%·광주 17.4%만 예외.

### 키워드 → 코드 매칭

동작: 해수욕장 389(rated 299) · 계곡 268(56) · 테마파크 224(123) ·
수목원 187(113) · 고택 179(26) · 전망대 175(80) · 온천 73 · 폭포 68 ·
등대 48 · 동물원 29.

불능:

- **1글자 키워드 전멸** — `find_category_codes`의 `len(cleaned) < 2` 가드가
  `섬`·`숲`을 즉시 빈 배열로 만든다. 실제로는 섬 카테고리에 219곳이 있는데
  조용히 전국 조회로 새어나간다.
- 카테고리에 아예 없음 — `산책로`(둘레길만 존재) · `야경` · `아쿠아리움`.
- `공원`은 17개 코드 2,341곳으로 너무 넓다. `WHO_KEYWORDS["pets"]`가 여기로 샌다.

### moods는 살아 있다

`spot_moods` 4,677행, 전부 `source='code'` · `confidence=1.00`(카테고리에서
결정적 파생). attraction 모수 안 커버리지:

| mood | 스팟 | rated | 제주 |
|---|---|---|---|
| mountain 산·숲 | 1,038 | 513 | 115 |
| sea 바다 | 763 | 530 | 84 |
| street 도시 골목 | 537 | 164 | 19 |
| hanok 한옥·고궁 | 355 | 102 | 6 |
| night 야경 | 304 | 85 | 7 |
| island 섬 | 219 | 157 | 10 |
| lake 호수 | 196 | 82 | 3 |

`market 시장`은 0곳 — SH06이 술어에서 잘려서다. 위 절단면 표와 교차검증된다.

mood의 가치는 카테고리 매칭이 실패하는 축을 잡는 것이다: `섬`(1글자 컷) ·
`야경`(카테고리 부재) · `한옥·고궁`(고택 179 + 고궁 72로 쪼개진 것을 355로 묶음).

### 축제는 동작한다

`searchFestival2` 최근 90일 시작분 414건 중 **오늘 진행 중 57건, 대표이미지
보유 56건**. 서울 16 · 강원 7 · 경기 7 · 제주 4로 분포도 있고 D-0~D-7이 고르다.

주의: 축제 주소가 `전남광주통합특별시`로 내려온다. `spots.addr1`은
`전라남도`/`광주광역시` 구 표기라 두 소스의 시도 문자열이 다르다.

## 결정

### D1. 에이전트 전용 카테고리 술어를 만들어 VE06·VE07을 포함한다

`spots/services/nearby.py`에 `travel_category_sql()`을 새로 두고 제외 집합을
`("VE08", "VE09", "VE10", "VE11")`로 좁힌다. `attraction_category_sql()`과
지도 탭 동작은 건드리지 않는다.

모수 11,575 → 13,481(+16%), 실내 후보 177곳 → 1,906곳. 지도 탭과 결과가
달라지지만 여행 탭이 더 넓게 답하는 쪽이 맞다. 도서관(VE09)·시장(SH06)은
관광 의도와 거리가 있어 이번에는 제외한다.

`INDOOR_KEYWORDS`는 이름 매칭을 버리고 **코드 직접 지정**으로 바꾼다
(중분류 `VE06`·`VE07`, 소분류 `VE020400` 수족관 · `VE120300` 기타문화시설).
이름 ILIKE가 `체험관` → `체험관광`으로 샌 것이 이번 사고의 직접 원인이다.

### D2. mood를 조회 축으로 승격한다

`QueryIntent.moodHints`를 추가하고 `find_candidates`에 `EXISTS` 서브쿼리로
건다. 카테고리 코드와는 AND. 새 `ToolName`은 `mood_search`.

Gemini 프롬프트에는 **DB에 실재하고 모수가 0이 아닌 7종만** 열거한다
(`바다`·`산·숲`·`호수`·`섬`·`한옥·고궁`·`야경`·`도시 골목`). `시장`은 모수 0이라
넣지 않는다.

같은 프롬프트에 `festivalOnly` 규칙도 넣는다 — 질문이 축제·행사를 지목하면
true, 아니면 false. true면 다른 조회 축은 무시하고 축제 풀만 본다.

### D3. 조건 시트를 전면 삭제한다

3축 중 2축 무동작 + 1축 침묵 무시. 지역은 버리지 않고 **말로 옮긴다** —
칩이 `제주에서 한적한 곳`처럼 질문 문자열에 지역을 실어 보내면
기존 `regionHints` 경로가 그대로 처리한다.

배포 순서는 안전하다. 백엔드가 먼저 나가도 Pydantic 기본이 extra-ignore라
구 앱이 보내는 `region`/`when`/`who`는 조용히 무시된다.

### D4. 후속 칩은 intent 왕복으로 refine 한다

서버가 응답에 **적용된 `intent`**를 싣고, 후속 요청은 그 intent + patch만
보낸다. `intent`가 실려 오면 Gemini를 호출하지 않는다 — 결정적 검색이라는
ADR 0009 원칙과 맞고, 후속 응답에서 LLM 왕복 1회가 사라진다.

칩 문구는 비교급(`더 ~`)을 버리고 **상태 전환**(`사람 적은 곳만`)으로 쓴다.
이미 켜진 축의 칩은 내려보내지 않는다 — "눌렀는데 왜 그대로지"를 없앤다.

기각한 대안: 클라이언트가 `여수 바다 중 사람 적은 곳`처럼 문자열을 합성하는
방식. 서버 무변경이지만 LLM 재추출이라 불안정하고 3~4번 누르면 문장이 무너진다.

### D5. 축제는 별도 캐시 풀로 노출한다

`fetch_festa_cards`에 `limit` 파라미터를 붙이고, `feed/services/kto_channels.py`에
`load_festival_pool(redis, kto)`(limit 60, 캐시 키 `festival:pool:v1`, TTL 1h)를
추가한다. 채널용 10건 캐시는 그대로 둔다. agent는 `feed`의 `services.py`를
경유해 읽는다(모듈 경계 준수).

지역 필터는 `regionHints`의 **원문 토큰을 카드 주소에 부분 문자열로** 맞춘다
(`제주` → `제주특별자치도 서귀포시` ✓, `여수` → `전남광주통합특별시 여수시` ✓).
스팟 경로처럼 `regions` 테이블로 시도를 매핑하면 안 된다 — 매핑 결과
`전라남도`는 축제 주소 `전남광주통합특별시`와 접두사가 어긋난다. 두 소스의
주소 어휘가 다르다는 사실을 그대로 받아들인다.

0건이면 **전국으로 폴백하되 답변 문장에 명시**한다
(`제주에는 오늘 열리는 축제가 없어 전국에서 골랐어요`). 표기 불일치를 조용히
삼키지 않는다.

## 설계

### 백엔드 — 스키마

```python
# schemas.py
Mood = Literal["sea", "mountain", "lake", "island", "hanok", "night", "street"]

class QueryIntent(BaseModel):
    categoryKeywords: list[str] = []
    regionHints: list[str] = []
    namedPlaces: list[ExtractedPlace] = []
    moodHints: list[Mood] = []          # 신규
    crowdPreference: CrowdPreference = "any"
    indoorOnly: bool = False
    nearMe: bool = False
    festivalOnly: bool = False          # 신규
    outOfScope: bool = False

class RefinePatch(BaseModel):
    crowdPreference: CrowdPreference | None = None
    indoorOnly: bool | None = None
    nearMe: bool | None = None
    drop: Literal["crowd", "indoor", "near", "region", "category"] | None = None

class Suggestion(BaseModel):
    label: str
    patch: RefinePatch

class AskRequest(BaseModel):
    question: str | None = None
    intent: QueryIntent | None = None   # 있으면 Gemini 스킵
    patch: RefinePatch | None = None
    lat: float | None = None
    lng: float | None = None
    # region / when / who 삭제
```

필수 입력 검증은 `question` · `photo` · `intent` **셋 중 하나**로 완화한다.
refine 요청은 `question` 없이 `intent` + `patch`만 보낸다. 대화 버블에 띄울
문구는 칩 `label`이라 클라이언트가 이미 갖고 있다.

```python
class AskResponse(BaseModel):
    steps: list[AskStep]
    answer: list[AnswerSegment]
    spots: list[AgentSpotCard]
    totalCount: int
    intent: QueryIntent                 # 신규 — 다음 턴이 되돌려 보낸다
    suggestions: list[Suggestion]       # list[str] 에서 변경
```

`ToolName`에 `mood_search` · `festival` 추가.

### 백엔드 — 흐름

```
ask()
├─ intent 있음 → apply_patch(intent, patch)          [Gemini 스킵]
├─ intent 없음 → intent_service.extract_intent()     [Gemini 1회]
│
├─ festivalOnly → feed.load_festival_pool → 지역 필터 → 카드
└─ 아니면
   ├─ namedPlaces → resolve_places (기존)
   ├─ codes    = resolve_category_codes(keywords)
   ├─ moods    = moodHints → mood_ids
   ├─ prefixes = regionHints → 시도 (조건 시트 경로 삭제)
   ├─ find_candidates(codes, mood_ids, prefixes, indoor_only, preference, near)
   ├─ crowd 필터 → nearby 정렬 (기존)
   └─ suggestions = derive_suggestions(intent, has_coords, result_count)
```

`indoorOnly`는 `codes`를 **대체하지 않고 별도 절로 AND** 한다. VE06·VE07은
중분류이고 `find_candidates`는 `lcls_systm3`로 거르기 때문에 코드 배열에 섞을
수 없다.

```sql
AND (spots.lcls_systm2 IN ('VE06','VE07')
     OR spots.lcls_systm3 IN ('VE020400','VE120300'))
```

이렇게 두면 `제주 실내 미술관` 같은 질의에서 `미술관`(VE070600)과 실내 절이
자연스럽게 교집합이 된다. 지금은 `미술관`이 코드로는 잡히는데 술어에서 0곳으로
잘려 나가지만, D1 이후에는 337곳이 된다.

`derive_suggestions` 규칙:

| 직전 상태 | 칩 |
|---|---|
| `crowdPreference == "any"` | `사람 적은 곳만` → `{crowdPreference: "quiet"}` |
| `crowdPreference == "quiet"` | `유명한 곳으로` → `{crowdPreference: "popular"}` |
| `indoorOnly == False` | `실내만` → `{indoorOnly: true}` |
| 좌표 있고 `nearMe == False` | `가까운 순으로` → `{nearMe: true}` |
| 결과 < 5 | `조건 하나 풀기` → `{drop: <가장 좁힌 축>}` |

최대 3개. 이미 켜진 축의 칩은 내보내지 않는다.

`drop` 대상은 서버가 고정 우선순위로 고른다 — `crowd` > `indoor` > `category` >
`near` > `region`. 지역을 마지막에 두는 이유는 사용자가 명시한 지역을 임의로
넓히는 것이 가장 큰 배신이기 때문이다.

축제 턴(`festivalOnly=true`)은 후속 칩을 내보내지 않는다. 혼잡도·실내·카테고리
축이 축제 풀에 적용되지 않아 누르면 아무 일도 일어나지 않기 때문이다.

### 백엔드 — 삭제

`AskFilters` · `Region`/`When`/`Who` 타입 · `REGION_PREFIXES` ·
`REGION_LABELS` · `WHO_KEYWORDS` · `WHEN_LABELS` · `BASE_SUGGESTIONS` ·
`NEAR_SUGGESTIONS` · `INDOOR_KEYWORDS`(코드 상수로 대체) ·
`resolve_region_prefixes`의 `region` 파라미터.

### 모바일 — 화면

`(tabs)/travel.tsx` 스크롤 순서:

```
헤드라인  오늘, 어디로 갈까요
PhotoStartCard          ← 신규 전폭 카드
ChannelRail  인기 관광지
ChannelRail  숨은 관광지
ChannelRail  내 근처
대화 턴들
─────────────
AskComposer  [칩 행] [입력]      ← 조건 칩 제거
```

`PhotoStartCard` — 레일이 아니라 액션 카드다. 같은 `ChannelRail`을 쓰면
스팟 카드처럼 보여서 눌리지 않는다.

- 제목 `사진으로 찾기`
- 설명 `마음에 든 사진을 올리면 닮은 국내 여행지를 찾아드려요`
- 각주 `원본은 비교 후 바로 폐기해요` (`ATTACH_NOTICE` 문구 재사용)
- 탭 → `pickTravelPhoto()` → **선택 즉시 제출**(전송 버튼 재탭 없음)

### 모바일 — 칩

초기 칩(대화 전)은 클라이언트 상수, 후속 칩은 서버 `Suggestion`.

```ts
type Chip =
  | { kind: "question"; label: string; question: string }
  | { kind: "refine"; label: string; patch: RefinePatch };
```

초기 칩 — 전부 실측으로 모수가 확인된 것만:

| 칩 | 질문 문자열 | 근거 모수 |
|---|---|---|
| 지금 열리는 축제 | `지금 열리는 축제` | 오늘 56건 |
| 여기서 가까운 순 *(좌표 있을 때만)* | `여기서 가까운 곳` | — |
| 사람 적은 바닷가 | `사람 적은 바닷가` | mood sea 763 (rated 530) |
| 비 와도 갈 만한 실내 | `비 와도 갈 만한 실내` | VE06+VE07 1,906 |
| 제주에서 한적한 곳 | `제주에서 한적한 곳` | 제주 rated 264 |

`사람 적은 곳` 단독 칩은 넣지 않는다 — `숨은 관광지` 레일과 결과가 겹친다.
혼잡도 축에는 항상 다른 축을 하나 더 붙인다.

### 모바일 — 사진 턴의 후속 칩

사진 매칭은 벡터가 필요해 intent 왕복만으로 재실행할 수 없다. `Turn`이 이미
`photo: PhotoUpload`를 들고 있으므로 **같은 사진을 다시 첨부해 patch와 함께
재요청**한다. 업로드 1회가 더 들지만 동작이 정직하다.

### 모바일 — 삭제

`ConditionSheet.tsx` · `stores/conditions-store.ts` · `lib/condition-labels.ts`
(+ 각 테스트) · `api.ts`의 `Conditions`/`RegionFilter`/`WhenFilter`/`WhoFilter`/
`DEFAULT_CONDITIONS` · `AskComposer`의 조건 칩과 `conditionLabel`/`conditionActive`
props.

## 테스트

백엔드 (`backend/tests`):

- `travel_category_sql()`이 VE06·VE07을 포함하고 VE08~VE11·AC·FD·SH·LS·EV를 제외한다
- `INDOOR_CODES` 경로가 체험관광을 끌어오지 않는다 (이번 사고의 회귀 테스트)
- `moodHints`가 `EXISTS` 필터로 걸리고 카테고리 코드와 AND 된다
- `intent`가 실린 요청에서 `extract_intent`가 **호출되지 않는다** (mock 호출 수 0)
- `apply_patch`의 각 필드와 `drop` 동작
- `derive_suggestions` — 켜진 축의 칩이 빠지고 최대 3개
- 축제: 지역 힌트 0건 매칭 시 전국 폴백 + 답변 문장에 폴백 명시
- 요청에 구 필드(`region`/`when`/`who`)가 와도 422가 아니라 무시된다

모바일 (`mobile/src/features/travel/**/__tests__`, `src/app` 밖):

- `PhotoStartCard` 탭 → picker → 즉시 제출
- 초기 칩이 좌표 유무로 갈린다
- `refine` 칩이 직전 턴의 `intent`와 `patch`를 함께 보낸다
- 사진 턴의 refine 칩이 `turn.photo`를 재첨부한다

## 문서

- **ADR 0010** — 조건 시트 폐기 + 여행 탭 전용 카테고리 술어 분기. ADR 0009의
  "조건 시트의 `언제`는 아직 필터가 아니다" 후속을 닫는다.
- `docs/reference/api.md` — `POST /agent/ask` 요청/응답 표 갱신 (조건 3종 삭제,
  `intent`/`patch`/`Suggestion` 추가)
- `docs/reference/travel-tab.md` — 화면 구성과 칩 목록
- `docs/reference/database-schema.md` — `moods`/`spot_moods`를 "시드/pipeline
  마스터 코드"에서 **서빙 표면 있음**으로 정정

## 범위 밖

- `pets` 채널(`KorPetTourService2`)을 에이전트 축으로 올리는 것 — 반려견 칩은
  이번에 삭제만 하고 되살리지 않는다
- 시장(SH06)·도서관(VE09) 포함
- 요일·시간대 혼잡도 예측 (데이터 없음, ADR 0009와 동일 판단)
- 일정 조립 (플랜 마법사와 함께 폐기됨)

## 착수 전 확인 1건

`spot_embeddings`에 VE06·VE07 스팟이 얼마나 들어 있는지 모른다. 술어를
`_VECTOR_MATCH_SQL`에도 적용하면 사진 매칭 후보가 넓어지는데, 임베딩이 없으면
JOIN에서 빠질 뿐이라 회귀는 없다. 다만 "사진으로 찾기"가 박물관을 찾아줄 수
있는지는 임베딩 커버리지에 달려 있어 구현 중 한 번 재보는 게 좋다
(`agent-axis-probe`에 섹션 추가로 확인 가능).
