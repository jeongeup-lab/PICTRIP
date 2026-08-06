# API 레퍼런스

> 공개 API(`/v1`)와 에러 코드의 조회용 표. 라우트 정본은
> `backend/app/modules/*/routes.py`, 자동 문서는 `/v1/docs`.

모든 응답은 JSend `{data, error, meta}`. 인증 열이 비면 게스트 가능.

## 엔드포인트

| Method | Path | 목적 | 인증 |
|---|---|---|---|
| POST | `/auth/oauth/{provider}` | OIDC id_token → 토큰쌍 (kakao·google·apple) | — |
| POST | `/auth/email/signup` | 이메일 가입 (rate-limit 5/분/IP) | — |
| POST | `/auth/email/login` | 이메일 로그인 (rate-limit 10/분/IP) | — |
| POST | `/auth/refresh` | 슬라이딩 재발급 (denylist 확인) | refresh 본문 |
| POST | `/auth/logout` | 멱등 로그아웃 (jti denylist) | — |
| GET | `/users/me` | 내 프로필 | JWT |
| DELETE | `/users/me` | 탈퇴 (익명화·OAuth 해제·토큰 폐기) | JWT |
| GET / PUT | `/users/me/consents` | 동의 상태 조회/upsert | JWT |
| GET | `/users/me/saved` | 저장 목록 (커서) | JWT |
| POST / DELETE | `/users/me/saved/{contentId}` | 저장/해제 (멱등) | JWT |
| GET | `/spots/{contentId}` | 스팟 상세 (KTO lazy fetch, 7일 캐시) | — |
| GET | `/feed` | 홈 피드 — 해외 게시물 (seed+cursor, 6개) | — |
| GET | `/explore` | 탐색 그리드 (동일 소스, 30개) | — |
| GET | `/overseas/{id}/matches` | 해외→국내 매칭 3곳 | — |
| GET | `/home/channels` | 채널 메타 (가용성 포함) | — |
| GET | `/home/channels/{key}` | 채널 카드 (`around`는 lat/lng 필요) | — |
| POST | `/agent/ask` | 여행 탭 질의 — 자유문·사진·intent → 단계+답변+스팟 (아래) | — |
| GET | `/map/nearby` | 내 주변 (bbox+카테고리, ≤30) | — |
| GET | `/map/region` | 좌표→행정구역 라벨 (fail-open null) | — |
| GET | `/map/regions-tree` | 시도·시군구 트리 (centroid 포함, 24h 캐시) | — |
| GET | `/meta/version` | 버전·환경·ktoApiStatus | — |
| GET | `/health` *(루트, /v1 밖)* | liveness | — |

`GET /spots/{contentId}`는 `X-PicTrip-Detail-Mode: deferred-v1` 요청에 한해 캐시가
없을 때 기본 관광지 정보와
`detailStatus="pending"`을 먼저 반환하고 KTO 상세를 백그라운드에서 채운다. 모바일은
`pending`인 동안 1.5초 간격으로 다시 조회한다. 7일 캐시가 만료된 경우에는 기존 상세와
`detailStatus="stale"`을 즉시 반환하고 갱신하며, KTO 갱신 실패 후 60초 동안은
`detailStatus="unavailable"`로 재시도를 제한한다. 캐시가 없는 `unavailable` 화면은
백오프가 끝나는 60초 뒤 다시 조회한다. 헤더가 없는 기존 클라이언트에는 배포 호환성을
위해 KTO 조회가 끝난 완성 응답을 유지한다.

어드민 콘솔은 `/v1` 밖 `/admin` — 페이지 4종 + `/admin/api/*`(수집·임베딩
상태/트리거, 이력, 헬스, overseas 목록·`is_hidden` 토글). 서명 쿠키 세션,
`admin_users` 인증. `images` 모듈은 공개 엔드포인트 0(임베딩 잡 전용).

## `POST /agent/ask`

여행 탭의 유일한 질의 표면. 자유문·사진·직전 턴의 의도를 한 요청으로 받아 한 번에
응답한다(스트리밍 없음 — [ADR 0009](../adr/0009-travel-tab-conversational-agent.md)).
사진이 붙으면 `multipart/form-data`, 아니면 JSON. rate-limit 20/분/IP.

**요청** — `question` · `photo` · `intent` · `anchor` **넷 중 하나 이상**이
있어야 한다(없으면 `VALIDATION_FAILED`).

| 필드 | 타입 | 비고 |
|---|---|---|
| `question` | string | 자유문. 사진에 덧붙이면 지역·근처 조건으로 함께 적용된다 |
| `photo` | file | multipart 전용. 임베딩 후 즉시 폐기, **디스크에 닿지 않는다**(아래) |
| `intent` | `QueryIntent` | 직전 응답의 `intent`를 되돌려 보내는 refine 경로. **있으면 Gemini를 호출하지 않는다** |
| `patch` | `RefinePatch` | `intent` 위에 덮어쓸 축. `{crowdPreference?, indoorOnly?, nearMe?, drop?}` |
| `anchor` | `{contentId, action}` | 카드 선택 후속 경로. `action` = `food`·`cafe`·`nearby`(앵커 좌표 반경 3km 결정적 조회, 거리순) · `crowd`(혼잡도 답변 전용 턴). **있으면 question/intent를 무시**하고 Gemini를 호출하지 않는다. 사진과 함께 오면 `VALIDATION_FAILED` |
| `lat` / `lng` | float | 거리 정렬·`내 근처` 의도에만 사용 |
| `region` | string | 폐기된 조건 시트의 잔재. OTA 전 구 앱만 보내고, 지역 조건으로만 옮겨 태운다(아래) |

multipart에서 `intent`/`patch`/`anchor`는 **JSON 문자열 필드**로 온다 (파싱
실패 시 `VALIDATION_FAILED`). 정형 조건 시트(`region`/`when`/`who`)는 폐기됐다
([ADR 0010](../adr/0010-travel-tab-drops-condition-sheet.md)).

**구 앱 `region` 호환 셈(OTA 롤아웃까지만).** 백엔드는 dev 머지 즉시 배포되고
모바일 OTA는 뒤따라 도착한다. 그 사이 구 앱은 조건 시트의 `region`을 계속 보내는데,
그냥 무시하면 `제주`를 골라둔 사용자가 200 + 전국 결과를 받는다. 그래서 `region`만
`schemas.PRE_OTA_REGION_PREFIXES`로 addr1 접두사(`jeju` → `제주`,
`capital` → `서울`·`경기`·`인천`)로 옮겨 조회에 싣는다. 질문에서 뽑은
`regionHints`가 있으면 그쪽이 이긴다. 알 수 없는 값과 `all`은 전국이고, 422를
내지 않는다. `when`/`who`는 폐기 전에도 조회를 바꾸지 않았으므로(문장 장식과
빈 키워드 튜플) 계속 무시한다. **OTA가 다 깔리면 `PRE_OTA_*` 심볼째 지운다.**

`QueryIntent` = `{categoryKeywords[], regionHints[], namedPlaces[], moodHints[],
crowdPreference, festivalOnly, indoorOnly, nearMe, outOfScope}`. 배열은 전부
길이 상한이 있다(키워드·지역 힌트 20, 지목 장소 10, mood 7). 문자열 하나도
80자 상한이고, 넘으면 `VALIDATION_FAILED`(422)다 — 지역 힌트 한 개가 공백으로
쪼개져 만드는 토큰은 최대 4개, `regions` 조회는 토큰 100개에서 끊는다.
`moodHints`는 `sea`·`mountain`·`lake`·`island`·`hanok`·`night`·`street` —
`spot_moods`에 모수가 0이 아닌 7종만 열거한다.
`drop` 축은 `crowd`·`indoor`·`near`·`region`·`category`이고, 해당 축의 intent
필드를 기본값으로 되돌린다(`category`는 `categoryKeywords`+`moodHints` 둘 다).

Gemini Flash는 `question` → 구조화 의도 추출에만 쓴다. 의도에 `outOfScope`가
서면("파리 가볼 만한 곳") 검색을 돌리지 않고 `AGENT_OUT_OF_SCOPE`로 끊는다 —
빈 의도로 전국 검색이 돌아 엉뚱한 국내 스팟을 추천하는 일이 없도록. 단 사진
질의는 예외로, 해외 사진 → 국내 매칭이 제품의 본래 동작이라 그대로 진행한다.

**응답 `data`**

| 필드 | 타입 | 비고 |
|---|---|---|
| `steps[]` | `{tool, label, badge}` | 서버가 **실제로 실행한** 툴 순서. `badge`는 그 단계 후 잔여 건수(`128곳`) 또는 근거 표시(`Gemini` · `pgvector`) |
| `answer[]` | `{text, emphasis}` | 문장 조각. `emphasis=true`는 `accentText` 800으로 렌더 (HTML을 보내지 않는다) |
| `spots[]` | `{contentId, title, regionLabel, imageUrl, tag, lat, lng, categoryGroup, hasCrowd}` | 상위 20곳 — 대화 레일이 전부 그린다. `tag`는 카드 좌상단 배지(`하위 8%` · `4.2km` · `유사도 86%`). `categoryGroup`은 `lcls_systm*`에서 파생한 지도 핀 글리프 키(`food`·`cafe`·`attraction`·`leisure`·`shopping`, 없으면 `null`). `anchor.action=crowd`는 빈 배열 |
| `totalCount` | int | `spots[]` 길이 |
| `intent` | `QueryIntent` | 서버가 **실제로 적용한** 의도. 다음 턴이 그대로 되돌려 보낸다 |
| `refinements[]` | `{label, patch}` | 후속 제안 칩 최대 3개. `label`은 상태 전환 문구(`사람 적은 곳만`), `patch`는 그 칩이 바꿀 축 |
| `suggestions[]` | `string[]` | `patch.drop`이 없는 `refinements[]`의 `label`만 **같은 순서**로 담은 목록. OTA 이전 구버전 앱과의 하위호환 전용이고 새 클라이언트는 `refinements`를 읽는다 |

`imageUrl`은 서명된 `img.pictrip.org` 프록시 URL — 클라이언트는 변형 없이 그대로
쓴다(`cpyrhtDivCd=Type3` 무변형, [ADR 0005](../adr/0005-kto-image-policy.md)).

**툴** — `steps[].tool` 값이자 서버가 고정 순서로 실행하는 단위.

| tool | 구현 | 하는 일 |
|---|---|---|
| `intent` | `agent/services/intent.py` | Gemini Flash 자유문 → 구조화 의도 |
| `photo_match` | `agent/services/photo.py` | CLIP 임베딩 → pgvector 유사도 (지역 조건은 SQL에 포함) |
| `resolve_place` | `agent/services/resolve.py` | 장소명 → KTO 스팟 (질문이 특정 장소를 지목할 때) |
| `category_search` | `agent/repositories.py` + `lcls_systm_codes` | 카테고리 키워드 → lcls 코드 → 스팟 조회 |
| `mood_search` | `agent/repositories.py` + `spot_moods` | `moodHints` → mood id → `EXISTS` 서브쿼리. 카테고리 코드와 **AND** |
| `festival` | `feed/services/kto_channels.py` | `festivalOnly`면 다른 축을 건너뛰고 `searchFestival2` 오늘 진행분 풀만 본다 (로컬 `spots` 가시 행과 교집합) |
| `title_search` | `spots/services/search.py` | 키워드가 lcls 코드에 하나도 안 걸릴 때의 폴백 (스팟 이름 trigram, 지역별로 각각 조회) |
| `concentration` | `agent/services/retrieve.py` | 집중률 백분위 하위/상위 30%로 추림. 후보가 적어 아무도 30% 안에 못 들면 가장 한적한/붐비는 쪽 20곳을 남긴다 (선호를 버리고 전체로 되돌리지 않는다) |
| `nearby` | `agent/repositories.py` · `spots/services/nearby.py` | 현재 위치 기준 거리순 (SQL `ORDER BY`). `anchor` 경로는 `find_nearby_spots`로 앵커 스팟 좌표 반경 3km(food·cafe·attraction 분류) |

조회 모수는 지도 탭과 다르다. 에이전트는 `travel_category_sql()`을 쓰고
(`spots/services/nearby.py`) 제외 집합이 `VE08`~`VE11`이라 VE06 공연시설·VE07
전시시설이 들어온다. 지도 "주변 관광지"의 `attraction_category_sql()`은
`VE06`~`VE11`을 전부 뺀 채로 남아 있다. `indoorOnly`는 카테고리 코드를 대체하지
않고 **코드 절로 AND** 한다 — 중분류 `VE06`·`VE07` 또는 소분류
`VE020400`(수족관)·`VE120300`(기타문화시설). 이름 ILIKE 매칭은 쓰지 않는다
([ADR 0010](../adr/0010-travel-tab-drops-condition-sheet.md)). 실내 ∩ 카테고리
코드가 0건이면 `실내로만 다시 조회` 단계로 **카테고리 코드를 버리고** 실내 절만
남겨 다시 조회한다 — 실내를 포기하지는 않는다.

**업로드 사진은 디스크에 닿지 않는다.** Starlette의 multipart 파서는 파일 파트를
`SpooledTemporaryFile(max_size=1MB)`에 담아 1MB를 넘으면 임시 파일로 롤오버한다 —
일반적인 폰 사진이 전부 여기 걸린다. 그래서 (1) 본문을 `MAX_BODY_BYTES`(8MB +
64KB) 상한으로 **스트리밍하며** 버퍼링해 초과분은 파싱 전에 `IMAGE_INVALID`로
끊고, (2) `MultiPartParser.spool_max_size`를 그 상한까지 올려 허용 범위는
메모리에만 머물게 한다. 롤오버가 일어나면 실패하는 회귀 테스트가 있다
(`test_photo_upload_never_rolls_over_to_disk`).

**장소명만 물으면 그 장소만 돌려준다.** 질문이 특정 장소만 지목하고 카테고리·지역
키워드도 근처·혼잡도·분위기·실내 선호도 없으면 broad search를 아예 건너뛴다.
`경복궁 같은 한옥`처럼 축이 하나라도 더 붙으면 그 축으로 검색을 돌려 지목한 곳
뒤에 붙인다. 해석에 실패하면 `AGENT_NO_RESULTS` — 물어본 장소와 무관한 전국
스팟을 붙이지 않는다.

**앞에 꽂는 장소도 같은 필터를 통과해야 한다.** 지목한 장소는 결과 맨 앞에
붙지만 풀이 통과한 절대 축(`indoorOnly` · `moodHints` · `any`가 아닌
`crowdPreference`)을 그대로 검사해서 떨어지면 뺀다 — `실내만` 칩을 누른 응답이
야외 궁궐로 시작하면 응답이 자기가 한 일을 잘못 말하는 것이다(`resolve_place`
배지도 살아남은 수를 센다). `nearMe`는 필터가 아니라 정렬이라 장소를 빼지 않는다.
실내·mood 여부는 `load_candidates_by_ids`가 같은 한 번의 조회에서 함께 읽고,
혼잡도는 `retrieve.passes_filters`가 `한산`/`붐빔` 경계(`CALM_RATE`/`BUSY_RATE`)로
판정한다.

**키워드가 코드에 안 걸리면 넓히지 않고 좁힌다.** LLM이 뽑은 카테고리 키워드가
`lcls` 코드로 하나도 매핑되지 않으면 조건 없는 전국 검색이 아니라 `title_search`
폴백으로 가고, 그것도 비면 0곳 응답이다. 유형을 물었는데 아무 관광지나
추천하지 않는다. 단 **`moodHints`나 `indoorOnly`가 있으면 폴백하지 않는다** —
`title_search`는 그 두 축을 SQL에 싣지 못해 `사람 적은 바닷가` 같은 질문이
바다·한적함을 통째로 잃기 때문이다. 이때는 코드 없이 mood·실내 절만으로 조회한다.

**혼잡도 단계는 실제로 걸렀을 때만 찍는다.** `title_search`·`resolve_place`가
채운 후보는 `cume_dist()` 백분위가 없어 `filter_by_crowd`가 통과만 시킨다.
그런 턴에서는 `concentration` step 자체를 넣지 않는다 — 잔여 건수가 그대로인
`혼잡도로 추림` 배지는 하지 않은 일을 했다고 말하는 것이다.

**사진 질의도 덧붙인 말을 읽는다.** 사진 + 텍스트면 CLIP 임베딩과 Gemini 의도
추출을 **동시에** 돌리고(지연은 둘 중 큰 쪽), 그 다음 지역 조건을 **벡터 SQL 안에**
넣어 검색한다 — 전역 상위 12개를 뽑고 나서 지역으로 거르면 13위 밖의 그 지역
후보를 아예 못 본다. 의도 추출이 실패해도 사진 결과는 그대로 내려간다(best-effort).

**정렬도 필터도 LIMIT보다 먼저다.** 후보 400개를 임의 순서로 자른 뒤 파이썬에서
정렬하거나 거르면 진짜 가까운/한적한/그 지역의 곳이 잘려나간다. 거리·집중률 정렬은 `ORDER BY`로 내려가고
`LIMIT`은 그 뒤에 붙는다. 혼잡도 백분위도 `cume_dist()` 윈도로 **필터를 만족하는
전체 집합** 기준으로 계산한다 — 잘린 400개 안의 상대 순위가 아니다.

**후속 칩은 문장이 아니라 intent를 되돌려 보낸다.** 응답의 `intent`에 `patch`를
얹어 다시 보내면 서버가 `apply_patch` 후 곧장 조회한다 — Gemini 왕복이 없다.
`refinements`는 **이미 켜진 축을 빼고** 만들어 "눌렀는데 그대로"를 없앤다:
`crowdPreference=any`면 `사람 적은 곳만`, `quiet`면 `유명한 곳으로`,
`indoorOnly=false`면 `실내만`, 좌표가 있고 `nearMe=false`면 `가까운 순으로`.
최대 3개다.

**결과가 있는 턴에는 조건 완화 칩이 없다.** `조건 하나 풀기`·`실내 조건 풀기`류를
전부 뺐다 — 사용자가 켠 조건을 서버가 골라 풀어주는 칩은 무엇이 사라지는지
라벨만으로 알 수 없었다. 조건을 바꾸는 것은 말로 한다. 결과 턴의 `refinements`는
축을 **켜는** 칩만 담는다(`patch.drop`이 없는 칩만 내려간다).

**0곳 턴에만 `지역 넓히기` 하나가 남는다**(`patch.drop = "region"`). 지역은
사용자가 말한 조건 중 유일하게 "더 보기"가 자연스러운 축이고, 넓히면 결과가
실제로 늘어난다. 지역 힌트가 SQL에 닿지 않았거나(`searched_intent`가 지움) 풀고
나면 장소명만 남는 의도면(`refine.drop_leaves_named_place_only`) 이 칩도 없다 —
`경복궁 같은 한옥`에서 지역을 풀면 `named_place_is_the_only_constraint`에 걸려
**넓히라고 누른 칩이 결과를 더 줄인다**.

축제 턴은 혼잡도·실내·카테고리 축이 축제 풀에 걸리지 않으므로 칩을 아예
내려보내지 않는다.

**`suggestions`는 라벨만 담은 하위호환 필드다.** 백엔드는 dev 머지 즉시
배포되지만 앱은 OTA를 받아야 갱신된다. 그 시차 동안 구버전 앱이 문자열로
그리는 `suggestions`의 타입을 바꾸면 답변 블록이 그대로 깨지므로, 구조화 칩은
`refinements`로 **추가**하고 `suggestions`는 라벨만 그대로 유지한다. 구버전
앱은 라벨을 자유문 질문으로 되쏘는 기존 동작을 이어간다.

**`suggestions`는 `drop` 칩을 뺀다.** `사람 적은 곳만`·`실내만`은 자유문으로
되쏴도 Gemini가 혼잡도·실내 의도를 다시 뽑아내 직전 턴의 문맥만 잃는다.
`지역 넓히기`는 풀 축이 `patch.drop`에만 있어 자유문으로는 빈 의도가 되고,
구버전 앱이 보고 있던 지역·카테고리·사진 문맥을 통째로 버린 전국 결과가
돌아온다. 그래서 레거시 투영은 `patch.drop`이 있는 칩을 **구조로**
걸러낸다(라벨 문자열 비교가 아니다 — 문구가 바뀌면 조용히 썩는다).
`refinements`는 손대지 않는다. 남는 불변식: `suggestions`는 `patch.drop`이 없는
`refinements` 항목의 라벨을 **그 상대 순서 그대로** 담는다.

**칩은 그 경로가 실제로 적용하는 축만 낸다.** `derive(axes=...)`가 경로별
축 집합을 받는다. 사진 경로는 `near`·`region`뿐이라(벡터 SQL의 지역 절 + 거리
정렬) 혼잡도·실내 칩을 내려보내지 않는다 — 눌러도 60초짜리 CLIP 재임베딩 끝에
같은 결과가 돌아오기 때문이다. `title_search` 폴백은 `category`·`near`·`region`만
낸다(집중률 백분위가 없는 경로라 혼잡도 축이 걸리지 않는다). `drop` 후보도 같은
집합 안에서만 고른다.

**축제 풀은 최근 1년 안에 시작해 오늘까지 진행 중인 축제 전량이다.**
`load_festival_pool`은 `searchFestival2`를 `eventStartDate = 오늘-365일`로 조회하고
`eventstartdate <= 오늘 <= eventenddate`인 카드만 남긴다. 홈 채널 `festa`는 건드리지
않는다 — 90일 창·10장·`channel:festa:v4` 그대로다. `arrange`에 행사일 정렬이 없어
(제목순·수정일순·생성일순뿐) 정렬로 상한을 걸면 **진행 중인 축제가 잘릴 수 있다**.
그래서 자르지 않고 짧은 페이지가 올 때까지 길어낸다 — 300행 × 최대 20페이지, 4페이지씩
병렬(최악 20요청 · 5왕복). 상한 6,000건에 닿으면 `feed.festival.pool_page_cap_reached`
경고를 남긴다(조용한 절단 금지). 못 담는 것은 **시작일이 1년보다 오래된 상설 행사**,
대표이미지 없는 행사, 그리고 상한을 넘긴 경우뿐이다. 캐시는 Redis `festival:pool:v2`,
TTL 48h이며 **신선도는 TTL이 아니라 저장된 날짜로 판정한다** — 날짜가 바뀔 때만
다시 받으므로 갱신 비용은 하루 최대 20요청이다. TTL이 이틀인 것은 KTO 장애 때
어제 풀을 폴백으로 쓰기 위함이고(24h면 최초 조회 시각 기준이라 오늘 하루를 못
버틴다), 폴백으로 나가는 카드는 종료일을 오늘 기준으로 다시 판정해 끝난 축제를
버리고 D-day를 다시 계산한다.

**축제 지역 매칭은 토큰 접두 + 시도 별칭이다.** `festivalOnly` 경로는
`load_festival_pool`(Redis `festival:pool:v2`, TTL 48h · 날짜 기준 신선도)을 읽고
`regionHints`를 공백으로 쪼갠 뒤(최대 `MAX_HINT_TOKENS`=4개, 2자 미만 토큰은 버림)
**모든 힌트 토큰이** 카드 지역 라벨(주소 앞 2토큰) 중 하나의 **접두**여야 그 카드를
지역 매치로 본다. `제주 서귀포` → `제주특별자치도 서귀포시`가 이 규칙으로 붙는다.
`regions` 테이블로 시도를 매핑하지 않는다 — 축제 주소는 `전남광주통합특별시`,
`spots.addr1`은 `전라남도`라 두 소스의 어휘가 다르다. 접두로 안 붙는 시도 장·단형만
`SIDO_ALIASES`(`전라남도`↔`전남`, `경상북도`↔`경북`, `충청남도`↔`충남`, `제주도`→`제주` 등
14개)로 보완한다. 부분 문자열 매칭은 쓰지 않는다 — `광주`가
`전남광주통합특별시`에 걸리는 오탐이 생긴다(그런 힌트는 전국 폴백으로 간다).

**축제 카드는 `spots`에 보이는 것만 내려간다.** `searchFestival2`는 실시간이고
`spots`는 일일 ETL이라, 마지막 동기화 뒤 새로 뜬 축제는 `contentId`가 로컬에 없다.
그대로 내려보내면 상세(`GET /spots/{id}`)와 저장(`POST /me/saved`)이 둘 다 404다.
그래서 풀을 `load_active_spot_cards_by_ids`(= `show_flag=1`, 상세·저장과 같은 술어)로
교집합한 뒤 자른다. 갓 등록된 축제는 다음 동기화까지 안 보인다.

지역 매치가 0건이면 전국 풀을 쓰되 이유를 구분해 말한다 — 그 지역에 오늘 축제가
아예 없으면 `제주에는 오늘 열리는 축제가 없어 전국에서 골랐어요`, 있는데 아직
`spots`에 없어 못 여는 경우면 `제주 축제는 아직 상세 정보가 없어 전국에서 골랐어요`.
교집합 후 전국도 0건이면 `AGENT_NO_RESULTS`다.

**이어지는 질문은 앞 대화를 함께 보낸다.** 자유문 후속 질문은 `context`에 직전
턴의 적용된 `intent`와 결과 제목(최대 8개)을 실어 보낸다. 의도 추출이 그것까지
읽으므로 `더 한적한 곳`이 직전 지역·유형을 유지한다.

**앞 결과를 중심으로 묻는 질문은 앵커 조회로 넘어간다.** `거기 근처 카페는?`
처럼 직전 결과 한 곳을 기준점으로 삼으면 의도 추출이 `originPlace`에 그 이름을
넣고, 서버는 `context.spots`에서 같은 이름을 찾아 그 `contentId`로 앵커 경로를
탄다. 자유문 후보 풀은 `travel_category_sql()`이라 음식(`FD`)이 아예 없으므로
`카페`·`맛집`은 앵커의 반경 조회가 아니면 답할 수 없다. 카테고리 낱말로
`food`·`cafe`를 고르고, 아니면 `nearby`다.

**서버는 대화를 저장하지 않는다.** `conversationId`도 세션 테이블도 없다 —
문맥은 클라이언트가 자기 화면에서 만들어 매 요청에 싣는다. 대화 이력의 주인이
클라이언트이므로 TTL·만료·정리가 필요 없고, 인증이 denylist-only인 이 서비스에
새로운 서버 상태를 만들지 않는다. `intent`가 이미 준비돼 있으면(칩 경로)
`context`가 있어도 추출을 건너뛴다 — 칩은 이미 무엇을 바꿀지 알고 있다.

**조건 때문에 0곳이면 에러가 아니라 답이다.** 자유문·사진 질의에서 사용자가 건
조건이 결과를 0으로 만들면 `200 + spots: []`로 답한다. 에러로 돌리면 화면이
`다시 시도`만 남는데, 같은 입력을 다시 보내면 결과도 같으므로 막다른 길이 된다.
**단, 되짚을 조건이 하나도 없으면 `AGENT_NO_RESULTS` 에러다** — 조건 없는 사진
질의가 아무것도 못 맞춘 경우가 그렇다. "이 조건으로는 0곳"이라고 말할 조건 자체가
없어 답변이 거짓이 된다.

응답은 세 가지를 유지한다 — 어디서 죽었는지 보이는 `steps` 퍼널(배지에 `0곳`이
찍힌 마지막 단계가 최종 실패 지점이다. **아무것도 거르지 않은 단계는 아예
남기지 않으므로** 0곳 배지는 전부 실제로 돌린 조회다 — 재시도가 여러 번이면
그 시도들이 차례로 보인다), 건 조건을 이름으로 되짚는 `answer`(`제주 + 실내 조건으로는
0곳이에요. 조건을 조금 바꿔서 다시 물어봐 주세요.`), 그리고 지역 힌트가 살아
있으면 `지역 넓히기` 한 장뿐인 `refinements`. `intent`는 **실제로 SQL에 닿은 축만
남긴 값**(`searched_intent`)을 돌려준다 — 해석 못 한 지역 힌트, 코드로 안 풀린
카테고리 키워드, 좌표 없는 `nearMe`는 지워서 내려간다. 칩·문구·반환 intent가
같은 값을 읽으므로 셋이 서로 다른 말을 할 수 없고, 완화 칩을 누른 다음 요청이
적용된 적 없는 조건을 되살리지 않는다.

근처 조건이 범인일 수 있으면 **추측하지 않고 재본다** — 근처만 뺀 같은 조회를
한 번 더 돌려 결과가 있으면 근처가 원인이고, 그 건수를 `근처 조건 없이 다시
재보기` 단계로 남긴다. 0곳으로 끝나는 요청에서만 도는 쿼리 하나다.

`AGENT_NO_RESULTS`는 **탈출구를 못 주는 0곳에 남는다.** 탈출구 없는 200은
에러보다 나쁘다 — 사용자가 정상처럼 보이는 빈 턴에 갇힌다.

- 풀 조건 자체가 없을 때 — 지목한 장소를 못 찾음(`place_only`), 앵커 반경
  3km에 아무것도 없음, 축제 풀 0건, 조건 없이 올린 사진이 아무것도 못 맞춤.
- **OTA 이전 클라이언트** — 구 앱은 `refinements`가 아니라 호환 필드
  `suggestions`를 그린다. 그 필드는 `patch.drop`이 있는 항목을 제외하는데
  (구 앱이 라벨을 자유문 질문으로 되보내기 때문) 0곳 칩은 전부 drop이라
  구 앱에는 빈 배열이 내려간다. 0곳 계약은 OTA 이후 클라이언트 전용이다.

카드 태그 우선순위는 거리(`4.2km`) → 혼잡도 백분위(`하위 8%`) → 혼잡 라벨
(`붐빔`·`보통`·`한산`), 사진 질의는 `유사도 86%`, 축제는 `D-3`.

## 에러 코드

정본 `app/web/errors.py` — union은 `mobile/src/lib/app-error.ts`와 동기.
**새 코드는 양쪽을 함께 갱신한다.**

| code | HTTP | 용도 |
|---|---|---|
| `VALIDATION_FAILED` | 422 | 요청 형식 부적합 |
| `AUTH_TOKEN_INVALID` / `AUTH_TOKEN_EXPIRED` | 401 | 무효/만료 (만료는 모바일 silent refresh 트리거) |
| `GUEST_FORBIDDEN` | 403 | 게스트 불가 → 로그인 시트 |
| `PERMISSION_DENIED` | 403 | 권한 없음 |
| `RESOURCE_NOT_FOUND` | 404 | 리소스 없음 |
| `DUPLICATE_RESOURCE` | 409 | 중복 |
| `EMAIL_TAKEN` | 409 | 가입된 이메일 |
| `AUTH_INVALID_CREDENTIALS` | 401 | 이메일/비번 불일치 |
| `AUTH_SESSION_REVOKED` | 401 | 폐기된 세션 — 재로그인 |
| `IMAGE_INVALID` | 422 | 미지원 이미지 |
| `RATE_LIMITED` | 429 | 요청 과다 |
| `LBS_CONSENT_REQUIRED` | 403 | 위치 동의 필요 |
| `KTO_API_UNAVAILABLE` | 502 | KTO 무응답 → 부분 degrade |
| `OAUTH_PROVIDER_UNAVAILABLE` / `OAUTH_ID_TOKEN_INVALID` | 502 / 401 | 소셜 공급자 장애 / id_token 무효 |
| `SESSION_STORE_UNAVAILABLE` | 503 | 세션 저장소 일시 장애 |
| `ADMIN_UNAUTHORIZED` · `ADMIN_HISTORY_NOT_FOUND` · `ADMIN_TRIGGER_FAILED` · `ADMIN_VALIDATION` | 401·404·502·422 | 어드민 전용 |
| `AGENT_INTENT_UNAVAILABLE` | 502 | Gemini Flash 무응답 → 재시도 칩 |
| `AGENT_NO_RESULTS` | 422 | 지목한 장소를 못 찾음 · 앵커 반경에 아무것도 없음 · 축제 0건. **조건 때문에 0곳인 경우는 에러가 아니라 200이다** |
| `AGENT_OUT_OF_SCOPE` | 422 | 해외 여행지 질의 → 국내만 가능 안내 |
| `INTERNAL_ERROR` | 500 | 미분류 기본값 |

---
관련: [architecture](../explanation/architecture.md) · [database-schema](database-schema.md) · [glossary](../explanation/glossary.md)
