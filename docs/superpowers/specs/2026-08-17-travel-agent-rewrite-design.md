# 여행 탭 채팅 에이전트 재작성 — 설계

- 작성 2026-08-17 · 대상 `backend/app/modules/agent/` + `mobile/src/features/travel/`
- 1차 마감 2026-09-21 기준 5주 계획
- **범위 밖**: 홈 채널 교체 (별도 진행) · 마이 탭 · 파이프라인

---

## 1. 배경 — 현재 결함 12가지

코드로 확인한 것만 적는다.

| # | 결함 | 위치 | 증상 |
|---|---|---|---|
| 1 | 기본 정렬이 제비뽑기 | `repositories.py:221` `md5(content_id‖날짜)` | "제주 카페" → 무작위 20곳 |
| 2 | 준비된 답변이 버려짐 | `chat.py:140` — `task` 분기 없음 | "다음주 날씨" → "조건에 맞는 곳이 없네요" |
| 3 | 무관한 질문이 통과 | `ask.py:1535` `_asks_for_nothing` 입구 검사만 | "파이썬 코드 짜줘" → 전국 관광지 20곳 |
| 4 | 스텝이 사후 재생 | `ask.py`가 일반 함수 | `run`/`done`이 붙어서 나감 |
| 5 | 블로그가 첫 글자를 막음 | `chat.py:119` writer 앞 `await` | 최대 1.8초 정지 |
| 6 | intent 타임아웃 60초 | `llm.py:52` | 키워드 폴백이 사실상 발동 못 함 |
| 7 | 카페·맛집이 안 됨 | KTO 커버리지 + 속성 필드 부재 | "군자 공부하기 좋은 카페" → 조건 증발 |
| 8 | 네이버 결과를 버림 | `ask.py:679` `and place.spot.contentId` | 이름·주소·좌표 받아놓고 폐기 |
| 9 | 마커 파서가 취약 | `writer.py:81` 55줄, ASCII `[[`만 | DeepSeek이 `【】` 뱉으면 노출 |
| 10 | 환각 방지 규칙이 파묻힘 | `writer.py:18` — 14줄 중 앞쪽 | Onyx 실측 기준 준수율 30% 구간 |
| 11 | 스키마 이중관리 | `intent.py` `_RESPONSE_SCHEMA` 130줄 | `QueryIntent`와 손으로 동기화 |
| 12 | 수제 프로바이더 4개 | `llm.py` 326줄 | 재시도·429 매핑이 제각각 |

1·2·3·7 = 품질 · 4·5·6 = 체감 속도 · 9~12 = 유지보수·DeepSeek 전환 리스크.

### 결함 2의 근본 원인 — `raise`면 살고 `return`이면 죽는다

```python
# chat.py:95 — 예외 경로
except AppError as exc:
    yield "delta", ChatDeltaEvent(text=exc.message)   # 준비된 문구가 그대로 ✅
    return                                            # writer 안 탐

# 정상 반환 경로는 아래로 계속 → writer 무조건 실행 → 답변이 덮어써짐 ❌
```

| 상황 | 코드가 택한 방식 | 결과 |
|---|---|---|
| 해외 질문 | `raise AgentOutOfScope()` | ✅ 살아남음 |
| 못 하는 요청·잡담 | `return _talk_response(...)` | ❌ 덮어써짐 |
| 결과 0건 | 경로마다 `raise`/`return` 혼재 | 비일관 |

우연히 예외를 쓴 것만 살아남았다.

---

## 2. 원칙 3개

1. **모델에게는 자연어만 맡기고, 알 수 있는 건 조회한다.**
   "어린이대공원역이 행정구역인가"는 `regions` 테이블에 답이 있다.
2. **결과를 못 내면 못 낸다고 말하는 것 외에 출구가 없게 타입으로 강제한다.**
   거절 단어 목록(`UNSUPPORTED_WORDS` 32개)은 항상 샌다.
3. **결정적 규칙은 프롬프트 맨 뒤에 둔다.**
   Onyx 실측 — 같은 문장을 몇 줄 옮기면 준수율 30% → 90%.

---

## 3. 구조

### 3.1 3층 분리 (Onyx 패턴)

```
routes.py            HTTP · 레이트리밋 · 파싱          변경 없음
agent/turn.py    ①  준비 — 검증 · 지역결정 · 히스토리 · 도구목록 · Emitter
agent/loop.py    ②  턴 — 컨텍스트 조립 · 추론#1 · 도구실행 · 랭킹 · 추론#2
agent/step.py    ③  단일 추론 — 스트림 → 패킷
```

`ask.py` 1675줄이 ①②③을 다 한다. **줄 수가 아니라 층이 안 나뉜 게 문제다** — Onyx
`process_message.py`는 93KB로 우리보다 크다.

### 3.2 도구는 2개

```python
@tool
async def search_places(deps, *, queries: list[str]) -> PlaceResults:
    """국내 여행지·맛집·카페를 찾는다.
    지역·랜드마크·분위기·조건은 전부 쿼리에 자연어로 그대로 담아라.
    지역 해석·카테고리 매핑·필터 추출은 downstream 에서 자동으로 한다."""

@tool
async def spot_detail(deps, *, content_id: str, fields: list[DetailField]) -> DetailResult:
    """앞서 보여준 장소의 이용시간·휴무·주차·요금·개요를 조회한다."""
```

**파라미터를 쪼개지 않는다.** Onyx `search_tool.py`가 `queries: string[]` 하나만 받고
프롬프트에 "필터 추출은 downstream 에서 자동 실행되니 네가 넣지 마라"를 박아둔 것과 같은
설계. `region`/`landmark`를 모델에게 분류시키면 **우리가 DB로 아는 걸 추측하게 만드는 것**이다.

`queries`가 배열이라 복합 질문이 도구 여러 개 없이 풀린다 — "제주 카페랑 축제" →
`["제주 카페", "제주 축제"]`.

### 3.3 출력 타입 8종

```python
SpotResults      spots, basis, applied_axes
PartialResults   spots, unmet, basis        # "영업시간은 확인 못 함"
NeedMoreInfo     missing
NoResults        blocking_axis              # 어느 조건이 막았는지
OutOfCapability  cannot, bridge
Smalltalk
OutOfScope
Refused          reason
```

`match`로 갈리고 mypy가 누락 분기를 잡는다. 결함 2가 구조적으로 사라진다.

| 타입 | 추론 #2 | LLM 호출 |
|---|---|---|
| `SpotResults` · `PartialResults` | 실행 | 2 |
| `NoResults` · `NeedMoreInfo` · `OutOfCapability` | 실행 (표식 컨텍스트) | 2 |
| `Smalltalk` · `OutOfScope` · `Refused` | **건너뜀** — 정해진 문구 | **1** |

### 3.4 검증 — 추론 #1은 되돌릴 수 있다

```python
if isinstance(out, SpotResults) and not out.applied_axes:
    raise ModelRetry("조건이 하나도 안 걸린 검색은 결과로 못 낸다. "
                     "OutOfCapability 나 NeedMoreInfo 로 답하라.")
```

결함 3이 여기서 막힌다. 현재 `_asks_for_nothing()`은 **입구에서만** 검사해서
`categoryKeywords=["코드"]`가 비어있지 않다는 이유로 통과하고, 필터 없는 SQL이 400개를 긁는다.

**추론 #2(스트리밍)에는 재시도가 없다.** 이미 나간 토큰을 못 되돌린다. 방어는 번호 참조로
표면을 줄이는 것이고, 산문 속 미지 장소는 `done` 직전 후검사로 로그·플래그만 한다.

### 3.5 Emitter

`ask.py`가 일반 함수라 중간 진행을 못 내보낸다(결함 4). `Deps`에 `asyncio.Queue` 기반
Emitter를 실어 내려보내면 각 검색 단계가 끝나는 즉시 스텝이 나간다.

```python
@dataclass
class Deps:
    session; redis; kto
    lat; lng
    region: ResolvedRegion
    emit: Emitter
```

---

## 4. 지역 결정 사다리

모든 턴에 적용한다. `turn.py`에서 **한 번만** 결정해 `Deps`에 싣는다.

```
① 질문의 지역        "제주 카페"            → 제주
② 직전 대화의 지역    context.intent        → 그 지역
   (카드 탭 시 그 카드) focusContentId
③ 좌표 → 역지오코딩   map.reverse_geocode() → 현재 지역 + 반드시 밝힘
④ 없음                                      → 묻는다
```

**②가 ③보다 위인 게 핵심.** 서울에서 제주 여행을 계획 중인 사용자에게 서울을 권하면 안 된다.

```python
@dataclass
class ResolvedRegion:
    hints: list[str]
    source: Literal["question", "context", "coords", "none"]
    label: str | None    # "광진구" — 화면에 밝힐 때
```

- `source == "coords"` → 리마인더에 "지역을 좌표로 추정했으니 밝히라" 추가
- `source == "none"` → 지역 필수 도구를 목록에서 빼서 `NeedMoreInfo`로 갈 수밖에 없게

`reverse_geocode()`는 이미 있다 — `map/services.py:133`, 카카오 `coord2regioncode` + Redis
캐시. 모듈 경계 규칙(cross-module은 상대 `services.py` 경유)에 맞다.

**부수 효과**: "카페 추천해줘"(지역 없음)에 지금은 되묻는데, 사다리를 타면 그냥 찾아준다.

---

## 5. 검색

### 5.1 소스 분기 — 카테고리가 아니라 **후보 수**로 갈린다

실측(§10) 결과 카테고리 기준이 틀렸다. 같은 "카페"라도 제주시는 134곳, 광진구는 1곳이다.
**KTO를 먼저 조회하고 결과 수로 결정한다.**

```
① KTO SQL 조회 (필터 적용)
     ├─ 검색 가능 후보 ≥ 10곳  →  KTO만으로 진행. 외부 콜 0~1
     └─ 10곳 미만              →  카카오 보충 (카페·맛집일 때만)
② 블로그 역방향 대조 1콜 (랭킹 + 인용 겸용)
```

| 질문 유형 | 실제 경로 | 외부 콜 |
|---|---|---|
| 관광지 "제주 박물관" | KTO + Phase A + 블로그 | 1 |
| 분위기 "야경 예쁜 곳" | + CLIP 재랭킹 | 1 |
| 카페 "제주 애월 카페" | **KTO 충분** → KTO + 블로그 | 1 |
| 카페 "군자 공부하기 좋은 카페" | **KTO 1곳** → 카카오 보충 | 3~4 |
| 못 하는 요청 · 잡담 · 해외 | 도구 없음 | 0 |

임계값 10은 초기값이다. W2에서 골든셋으로 조정한다.

### 5.2 downstream 추출 — 기존 코드 그대로

```
쿼리 문자열
 ① map_region_tokens_to_prefixes()  행정구역? → DB 조회로 확정
      ├─ 있음 → region_prefixes
      └─ 없음 → 랜드마크 → 카카오 지오코딩 1콜
 ② food_word() / food_action()      카페·맛집? → 소스 분기
 ③ dish_search_terms()              "횟집"·"삼겹살" + 부정어("말고")
 ④ taxonomy_word()                  "사찰" → "불교"
 ⑤ crowd / indoor / near 어휘
```

각 단계가 `deps.emit.step()`을 호출한다. `intent.py`가 사라지는 게 아니라 **라우팅 입력에서
도구 내부로 위치가 바뀐다.**

### 5.3 카페·맛집 — 역방향 대조

```
① 카카오 후보
     좌표 있음(근처·랜드마크) → 카테고리검색 CE7/FD6 + radius + sort=distance
     좌표 없음(행정구역)      → 키워드검색 "군자동 카페"
     요리 지정("횟집")        → 키워드검색 (카테고리는 너무 넓다)
  ↓ 28~45곳
② 네이버 블로그 1콜 "군자동 카공 카페" (display=100)
③ 역방향 대조 — 후보 이름이 몇 번, 서로 다른 블로그 몇 개에 나오나
④ 서로 다른 블로그 2개 이상만 → 언급 수 순
```

**추출이 아니라 대조**라 추가 LLM이 0회다. 후보별로 치지 않으니 콜이 폭발하지 않는다.

**속성 처리 2종**

| 유형 | 예 | 처리 |
|---|---|---|
| 판정 가능 | 카공, 24시, 주차, 반려동물 | 블로그 동시언급으로 **필터** |
| 판정 불가 | 분위기 좋은, 맛있는 | 버즈 순 **정렬로 근사 + 명시** |

판정하는 척은 하지 않는다. "'분위기 좋은'은 블로그 언급량으로 대신 판단했어요"라고 쓴다.

**광고 편향**: "서로 다른 블로그 2개 이상"으로 단일 협찬은 막는다. 완전히는 못 막으므로
답변 마지막에 기준을 밝힌다.

**없는 데이터** (영업시간 등): 카카오·네이버·KTO 어디에도 없다(`spot_details.usetime`
커버리지 9.2%, 카페는 사실상 0). → `PartialResults`로 **못 하는 걸 먼저 말하고** 할 수 있는
걸 그 다음에 준다.

### 5.4 CLIP — 관광지 재랭킹 전용

`ClipEmbedder`가 `transformers.CLIPModel`이라 `get_text_features()`가 이미 있다.
추가할 건 `embed_text()` ~10줄. 한국어 성능은 intent에서 영어 시각 묘사 필드를 하나 더
뽑아 해결한다 (추가 LLM 콜 0).

**카페엔 쓰지 않는다** — 임베딩은 `spots` 안에서만 찾고, 카카오 결과엔 사진이 없다.
CLIP은 **검색 도구가 아니라 재랭킹 도구다.**

### 5.5 카카오·네이버 결과 취급

현재 `ask.py:679`가 `and place.spot.contentId`로 버린다. 바꾼다:

```
카카오 후보
  ├─ KTO 매칭 (names_match() + 좌표 100m)  →  풀 카드 승격 (사진·저장·상세·혼잡도)
  └─ 없음                                  →  축소 카드
```

**DB 적재는 하지 않는다.** 매 요청 조회 — 약관 리스크 회피 + 폐업 반영 자동.

| 카드 등급 | 내용 |
|---|---|
| ① KTO 매칭 | 사진 · 저장 · 상세 · 혼잡도 + 카카오 전화·링크 |
| ② 카카오 전용 | 이름 · 주소 · 거리 · 전화 · "카카오맵에서 보기" |
| ③ 블로그 언급만 | 후보 탈락 (안 보여줌) |

**스키마 (하위호환)** — 전부 기본값 있는 추가 필드:

```python
class AgentSpotCard(BaseModel):
    contentId: str                              # kakao면 "kakao:1234567"
    source: Literal["kto", "kakao"] = "kto"     # 추가
    externalUrl: str | None = None              # 추가
    phone: str | None = None                    # 추가
    distanceM: int | None = None                # 추가
    saveable: bool = True                       # 추가
```

**모바일 4곳 변경** (앞선 "변경 없음"은 정정됨):
`api.ts` 타입 · `SpotCard`(축소 카드) · `AssistantTurn`(외부 링크) · `conversation-context`.

> 배포 순서 주의: 백엔드가 먼저 나가면 구 빌드가 `/spots/kakao:123`으로 이동해 404를 본다.
> **모바일 OTA를 먼저 내거나 같은 PR에 묶는다.**

---

## 6. 랭킹

```
① SQL 후보 40곳 (필터 적용)
② Phase A — 신규 데이터 0
     혼잡도 보유 DESC · overview 보유 DESC · mood 겹침 DESC · md5 타이브레이커
③ 블로그 1콜 (display 5→100, 타임아웃 1.0s, Redis 캐시 6h)
     후보 이름 등장 횟수 + 서로 다른 블로그 수
④ 최종 = Phase A + w·log1p(서로 다른 블로그 수)
     블로그 미언급은 Phase A 순서 유지
```

**`spot_signals` 사전계산 테이블은 만들지 않는다.** 이미 매 턴 부르는 블로그 호출을 랭킹에도
쓰고 `display`만 5→100으로 올린다. 역방향이라 동명이인 노이즈도 없다 — "제주 박물관"으로
검색한 글에 나온 "국립제주박물관"은 제주 것이 확실하다.

셔플은 **동점 타이브레이커로 남긴다.** 매일 결과가 조금씩 달라져 재방문 가치가 유지된다.

**타임아웃 시 Phase A로 카드를 먼저 낸다.** 성능 저하가 기능 상실이 아니라 순서 저하로만
나타난다. 네이버 미설정·장애 시에도 동일.

### 측정 — 골든셋으로는 랭킹을 못 잰다

`expect_spots="some"`은 "1개 이상 나왔나"만 본다. 셔플이든 랭킹이든 통과한다.

**A/B diff 하네스**
1. 같은 500케이스를 구/신으로 실행 → top-5 `contentId` 스냅샷
2. **바뀐 케이스만** 추출
3. 프록시 지표 대조 — 이미지 보유율↑ · `overview` 보유율↑ · 시군구 다양성 유지 ·
   **라우팅 통과율 불변**
4. 바뀐 것 중 **30개만 사람이 3점 척도**

기존 500턴은 **회귀 가드**로 남는다. 그리고 단언이 더 정밀해진다:
`expect_tools=("category_search",)`(확률적) → `expect_extracted={"region":"제주"}`
(**결정적** — downstream 추출은 코드다).

---

## 7. 프롬프트

```
[시스템]  정체성 + 출력형식 + (조건부 섹션)      ← 블로그 0건이면 인용 규칙 제외
[히스토리] search_places(["제주 한적한 박물관"]) → 7곳   ← 답변 300자 대신 도구 인자
[사용자]  원 질문
[결과]    {"documents":[{"document":1,"title":...,"region":...,"tag":...}]}
[리마인더] ← 맨 뒤, 생성 직전
   "documents 에 없는 장소 이름을 절대 쓰지 마라.
    장소는 [1] [2] 로만 참조하라. 영업시간·요금·전화는 언급하지 마라."
```

- 키 이름은 `citation_id`가 아니라 **`document`** — 추론에 아티팩트가 안 생긴다 (Onyx)
- 번호 **맨 앞**, 짧은 필드 순, 긴 내용 마지막 — LLM은 지역적 주목이 강하다
- 모델이 이름 대신 번호를 쓰니 이름 환각 표면이 줄어든다

**`[[cards]]` 마커와 `parse_stream` 55줄 폐기.** 대신 `CitationProcessor` — 부분 토큰 보류 +
**유니코드 괄호 변종(`【】`·`［］`) 처리**. 현재 파서는 ASCII `[[`만 봐서 DeepSeek 전환 시
마커가 노출될 수 있다.

---

## 7.5 LLM 프로바이더 — 전 구간 DeepSeek

> **2026-08-18 갱신.** 애초 이 절은 "writer 만 DeepSeek, intent 는 Gemini 유지"였다.
> 근거는 `responseSchema` 강제였는데, **운영 Gemini 크레딧이 소진되면서**
> (`429 RESOURCE_EXHAUSTED`) 그 전제가 무너졌다. 폴백이 살아 서비스는 유지됐지만
> intent 가 계속 키워드 매칭으로 돌아 품질이 떨어졌다 — `"비 와도"` 를 `"와도"` 라는
> 조건으로 뜯었다. **Gemini 를 기본에서 뺀다.**

| 단계 | 프로바이더 | 방식 |
|---|---|---|
| intent 추출 | **DeepSeek** | `response_format: json_object` + 스키마를 프롬프트에 실음 |
| writer | **DeepSeek** (`deepseek-chat`) | 스트리밍 |

Gemini 경로는 코드에 남아 있다 (`LLM_PROVIDER=gemini`). 크레딧을 채우면 즉시 되돌릴 수 있다.

**스키마는 프로바이더별로 만든다.** Gemini 는 대문자 방언(`"type": "OBJECT"`)이라 기존
`_RESPONSE_SCHEMA` 를 쓰고, OpenAI 계열은 `QueryIntent.model_json_schema()` 로 생성한다.
후자는 **모델이 곧 스키마**라 손으로 동기화할 것이 없다 — 130줄 이중관리가 사라진다.

DeepSeek 은 스키마를 강제하지 않으므로 최종 방어는 기존 `QueryIntent` 파싱이 맡고,
깨지면 `fallback_intent()` 키워드 폴백으로 떨어지는 경로가 그대로 살아있다.

**사진 질의는 거절한다.** 텍스트 전용 프로바이더에 `image_bytes` 가 오면
`AgentIntentUnavailable` 을 던진다. 이미지를 버리고 텍스트만으로 답하면 사용자가
왜 사진이 무시됐는지 알 수 없다.

```python
LLM_PROVIDER: Literal["gemini", "codex", "deepseek"] = "gemini"
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL: str = "deepseek-v4-flash"
```

`CodexClient`가 이미 OpenAI 호환이라 `OpenAIChatClient` 기반 클래스로 올리고
`CodexClient`/`DeepSeekClient`가 상속한다. 차이는 `Authorization` 헤더뿐이다.

**설정 검증** — codex는 local 전용이지만 deepseek은 호스티드라 운영에서도 허용한다.
대신 API 키 필수 + HTTPS 강제.

### 파생 효과 — Gemini 구조 탈출 경로가 꺼진다 (해소됨)

> 아래는 writer 만 옮겼을 때의 서술이다. 이제 intent 도 DeepSeek 이라
> `writer_depends_on_gemini() and structured_depends_on_gemini()` 가 둘 다 False 이고,
> 이 탈출 경로는 `LLM_PROVIDER=gemini` 로 되돌릴 때만 살아난다.

```python
# chat.py:122
if llm.writer_depends_on_gemini() and _llm_is_down(result):
    rescue = _deterministic_answer(result)   # 템플릿 답변
```

writer가 DeepSeek면 이 분기를 타지 않는다. Gemini intent가 429여도 →
`사전 매칭` 키워드 폴백으로 검색 → DeepSeek이 그 결과로 답을 쓴다.
**템플릿보다 나은 결과라 의도된 동작이다.** 다만 `사전 매칭` 배지 문구는
"LLM 죽음"이 아니라 "의도 추출만 폴백"을 뜻하게 되므로 W2에서 손본다.

### 스트림 주의 · 모델 선택 (2026-08-18 실측)

DeepSeek 추론 델타는 `delta.reasoning_content`로 오고 `delta.content`는 없다.
`_codex_stream_piece`가 `content is None`이면 건너뛰므로 깨지지 않는다 —
**추론을 노출하지 않기로 한 결정과 자연히 맞는다.**

> **정정:** 애초에 이 문서는 "`deepseek-v4-flash` 기준으로는 문제 없다"고 적었으나
> **틀렸다. v4-flash 는 추론 모델이다.** CT112 에서 실측:

| 모델 | 첫 콘텐츠 델타 | 총 소요 | 추론 델타 |
|---|---|---|---|
| `deepseek-chat` | **0.5~0.7s** | 3.0s | 없음 |
| `deepseek-v4-flash` | **3.4~4.4s** | 5.7s | 62개 선행 |

**기본 모델을 `deepseek-chat` 으로 한다.** writer 는 구조화 JSON 에서 산문을 쓰는 일이라
추론이 필요 없고, v4-flash 는 토큰과 첫 글자 지연을 둘 다 낭비한다. 카드가 ~1.9s 에 뜨는데
문장이 +4s 면 체감이 나빠진다.

추론 모델을 쓰게 되면 `_watchdog`(15초 무응답)을 다시 봐야 한다. 실측 추론 구간이
2~3.5초라 지금 값에 여유는 있지만, 프롬프트가 길어지면 늘어난다.

### 배포 절차

CT112 `/opt/pictrip-api/.env`에 두 줄 추가 후 재기동:
```
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
```
키가 비면 부팅이 `ValidationError`로 실패한다 — 조용히 Gemini로 되돌아가지 않는다.

---

## 8. UI

**레퍼런스 선정 중.** 확정되면 일회성 HTML 핸드오프 프로토타입으로 만들고 구현 후 폐기한다
(리포에 목업을 쌓지 않는다).

| # | 항목 | 출처 | 비용 |
|---|---|---|---|
| 1 | 프리셋 카드 3종 — 사진으로 찾기 / 지금 열리는 축제 / 사람 적은 곳 | Placelist ⑤ | 모바일 1파일 |
| 2 | 적용 조건 칩 — 실선=적용, 점선=탭하면 프리필, `(현재 위치)` 배지 | Placelist ① 변형 | `_applied_conditions()` 이미 있음 |
| 3 | 근거 칩 5종 — `한산`·`블로그 3곳`·`실내`·`240m`·`카카오맵` | Placelist ② 재정의 | 소 |
| 4 | 스텝 문구를 사람 말로 | Placelist ③ | Emitter 이후 |
| 5 | 축소 카드 | 신규 | 이미지 자리 아이콘, 저장 버튼 없음 |
| 6 | `PartialResults` 표현 | 신규 | 못 한 것을 결과 **위에** |
| 7 | `[1]` 탭 → 카드 스크롤 | 신규 | 소 |

**Placelist의 "언제·누구랑" 슬롯은 쓰지 않는다** — 우리 DB에 축이 없어 채워도 검색에 영향 0.
**캐릭터 로딩 카피도 쓰지 않는다** — 이모지 금지 방침 + 톤 불일치.

---

## 9. 5주 계획

| 주 | 작업 | 검증 |
|---|---|---|
| **W1** | ⚡ intent 타임아웃 60s→3~5s + `max_tokens`<br>⚡ 유니코드 괄호 처리 (DeepSeek 전 필수)<br>⚡ 리마인더 맨 뒤 재배치<br>⚡ 블로그 그라운딩 병렬화<br>· `_RESPONSE_SCHEMA` → `model_json_schema()`<br>· `embed_text()` 추가<br>· 실측 2건 | 골든셋 통과율 **불변** = 기준선 |
| **W2** | · 유니온 타입 8종 + `chat.py` `match`<br>· 지역 사다리 + `PartialResults`<br>· Phase A 랭킹 + 블로그 역방향 대조<br>· A/B diff 하네스<br>· 프리셋 카드 | 랭킹 A/B 1차 |
| **W3** | · 도구 방식 에이전트 **병렬 작성** — 트래픽 미연결<br>· 3층 분리 + Emitter<br>· `llm.py` 정리 | 같은 500턴 **양쪽 비교** |
| **W4** | · W3 승패 판정 → 교체 or 롤백<br>· 카카오·네이버 카페·맛집 경로 + 축소 카드<br>· 조건 칩 · 근거 칩 | A/B diff |
| **W5** | · 회귀 · 30케이스 사람 검수 · 버퍼 | — |

**W1의 ⚡ 4개가 가장 싸고 급하다.** 전부 반나절 이내고 DeepSeek 전환 전에 끝나야 한다.

**W3이 안전장치다.** "도구 방식이 나은가"를 논쟁하지 않고 둘 다 만들어 골든셋으로 재판한다.
져도 W1·W2는 이미 들어와 있다 — 스키마 이중관리 제거, 랭킹, 유니온 타입, 프롬프트 재배치,
프리셋.

---

## 10. 실측 · 리스크

### 실측 완료 (2026-08-17, 운영 DB·카카오 API 직접 조회)

**① KTO 음식점·카페 커버리지**

전국 (`show_flag=1`):

| food | cafe | 사진 보유(=검색 가능) | 전체 스팟 |
|---|---|---|---|
| 10,509 | 3,246 | **10,105** (73%) | 50,577 |

시군구 275개 분포 (검색 가능 기준):

| min | p25 | **중앙값** | p75 | max | <5곳 | <30곳 |
|---|---|---|---|---|---|---|
| 0 | 12 | **21** | 43 | 365 | 25개(9%) | **171개(62%)** |

**패턴: 관광지형은 두껍고 생활권은 비어 있다.**

| 지역 | food | cafe |
|---|---|---|
| 제주 제주시 | 231 | 134 |
| 제주 서귀포시 | 149 | 84 |
| 강원 강릉시 | 123 | 71 |
| 경북 경주시 | 101 | 50 |
| 전남 여수시 | 90 | 33 |
| 경남 통영시 | 38 | 11 |
| 전북 정읍시 | 13 | 7 |
| **서울 광진구** | 14 | **1** |
| **서울 강남구** | 180 | **19** |

> 시군구명은 `전주시 완산구` 형태로 저장된다 — 지역 매칭 시 주의.

**② 카카오 ↔ KTO 매칭률** (8쿼리 × 15곳 = 120곳, 정규화 이름 일치 + 좌표 500m)

| 쿼리 | 매칭 | 비율 |
|---|---|---|
| 제주 애월 카페 | 8/15 | 53% |
| 강릉 카페 | 8/15 | 53% |
| 여수 횟집 | 6/15 | 40% |
| 경주 황리단길 카페 | 5/15 | 33% |
| 통영 카페 | 3/15 | 20% |
| 정읍 맛집 | 2/15 | 13% |
| **서울 강남 카페** | **0/15** | **0%** |
| **서울 군자동 카페** | **0/15** | **0%** |
| **합계** | **32/120** | **27%** |

### 실측이 바꾼 결정

1. **소스 분기를 카테고리가 아니라 후보 수로 한다.** KTO를 먼저 조회하고
   검색 가능 후보가 임계(≈10) 미만이면 카카오로 넘어간다. 관광지형 지역은 KTO만으로
   충분하고(제주시 카페 134곳), 생활권은 KTO가 사실상 0이다(광진구 카페 1곳).
2. **축소 카드가 예외가 아니라 다수다.** 전체 73%, 서울 생활권 100%.
   UI 투자를 축소 카드에 몰아야 한다. "풀 카드에 뭔가 빠진 모양"으로 만들면
   대부분의 화면이 고장난 것처럼 보인다 — **독립된 카드 형태로 설계할 것.**

| 리스크 | 완화 |
|---|---|
| **모델의 도구 인자 정확도** — 최대 미지수 | W3 그림자 실행. 지면 롤백 |
| **DeepSeek 프롬프트 준수** — Gemini에서 먹던 지시가 안 먹을 수 있음 | Onyx 사례대로 지시를 사용자 메시지로 이동 |
| 네이버 API 약관 (저장) | **저장 안 함**으로 회피 완료 |
| 블로그 광고 편향 | 서로 다른 블로그 2개 이상 + 기준 명시. **완전 차단 불가** |
| 카카오 상한 (45건 / radius) | 문서 확인 필요 |

---

## 11. 채택하지 않은 것

| 항목 | 이유 |
|---|---|
| **pydantic-ai 도입** | 유니온·검증·DI 전부 순수 Pydantic 200줄. 소스는 **참고 문서로만** |
| **도구 파라미터 분리** (`region`/`landmark`/…) | 모델이 틀릴 자리를 6개 만드는 것. DB에 정답이 있다 |
| **CLIP으로 카페 검색** | 임베딩은 `spots` 안에서만 찾고 카카오 결과엔 사진이 없다 |
| **`spot_signals` 사전계산** | 실시간 역방향 대조가 대체. 노이즈에도 더 강하다 |
| **날씨 도구** | 사용자 결정 (`OutOfCapability` 유지) |
| **지도 뷰포트 재검색** | 여행 탭에 지도가 없다. 새 화면 + 새 스트림 = 5주에 안 맞음 |
| **reasoning 스트리밍** | 통제 불가 표면. SSE는 이미 있고 지연 원인이 다르다 |
| **ReAct 도구 루프** | 결정적 검색이라는 차별점을 버리는 것. 골든셋이 흔들린다 |
| **컨텍스트 압축** | 우리 히스토리는 8턴 × 300자 |
| **웹 검색 백엔드** | 결과가 `spots`에 없어 카드·저장·상세가 안 붙는다 |

---

## 12. 지키는 것

어떤 레퍼런스 레포에도 없는 도메인 자산이다. 재작성 중 **버리지 않는다.**

- **골든셋 500턴** (`scripts/travel_golden_set.py`) — 재작성의 유일한 안전망
- `retrieve.py` 지역·카테고리 해석 — `map_region_tokens_to_prefixes` ·
  `TAXONOMY_SYNONYMS`("사찰"→"불교") · `dish_search_terms` 부정어 처리("삼겹살 말고 회")
- 지역 확대 3단계 — 시군구→시도, 실내 0건이면 카테고리 포기
- `repositories.py` SQL — 혼잡도 percentile, 후보 검색
- 폴백 사슬 — `fallback_intent()` 키워드 매칭
- SSE 이벤트 계약 (`step`/`cards`/`delta`/`sources`/`done`/`error`)

---

## 부록 A. 참고 레포

| 레포 | 무엇을 |
|---|---|
| [onyx-dot-app/onyx](https://github.com/onyx-dot-app/onyx) | **주 레퍼런스.** `chat/README.md`(설계 이유 문서) · `search_tool.py`(파라미터 1개) · `citation_processor.py`(스트리밍 인용) · `search_flow_classification.py`(분류기 규율) |
| [ItzCrazyKns/Vane](https://github.com/ItzCrazyKns/Vane) (구 Perplexica) | `classifier.ts`(skipSearch) · `agents/search/index.ts`(검색 안 함 표식 컨텍스트) · widgets |
| [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | **문서로만.** `providers/deepseek.py` — v4가 `tool_choice=required` 미지원 등 실전 함정 |
| [domdomegg/google-maps-places-mcp](https://github.com/domdomegg/google-maps-places-mcp) | 장소 검색 도구를 텍스트 쿼리 하나로 통합한 사례 |

### Onyx에서 가져온 실측 지식

- **준수율 30% → 90%** — 같은 지시를 시스템 프롬프트 앞쪽이 아니라 관련 섹션/맨 뒤로 옮기면
- 필드명을 `citation_id`가 아니라 `document`로 — 추론 아티팩트 방지
- 도구 응답은 히스토리에서 버리고 **도구 인자는 남긴다** — 정보 밀도가 높고 토큰이 적다
- 분류기 규율 — 타임아웃 2초, `max_tokens=20`, 실패 시 안전한 쪽으로 폴백
- 파일 크기는 문제가 아니다 — `process_message.py` 93KB

---

## 13. 개정 (2026-08-19)

W1~W2 구간을 코드로 대조한 결과와 그 사이에 내린 결정을 남긴다.

### 13.1 진행표 정정

| 항목 | 문서 | 실제 |
|---|---|---|
| 출력 타입 8종 | 완료 | **7종** — `Refused` 없음. `PartialResults` 는 #297 에서 추가 |
| 3층 분리 | 완료 | **미착수** — 된 것은 갈래별(anchor·answer·food·photo_ask) **가로** 분할이다. §3.1 이 말한 `turn`/`loop`/`step` **세로** 분할은 파일이 없다 |
| 도구 방식 에이전트 (W3) | — | 미착수. `@tool`·`search_places` 흔적 0 |
| DeepSeek 전환 | 완료 | 코드 완료 · `config.py` 기본값은 아직 `gemini` (CT112 `.env` 두 줄이 남음) |

`agent` 모듈은 7,041 → 7,146줄로 **늘었다.** `ask.py` 를 691줄로 가른 뒤에도 그렇다 —
분할은 재배치였지 감축이 아니었다. 감축은 `[[cards]]`(−177)와 죽은 표면(−약 200)에서 나왔다.

### 13.2 이번에 내린 결정

**LLM 출력 후보정에 자리를 만든다 (`services/guard.py`).**
같은 모양이 셋이 됐다 — `reclassify_guessed_hints`(폴백 전용) · `hungry`(#287) · 숙소.
프롬프트는 266케이스 전역에 걸린 지점이라 한 줄만 바꿔도 26분 재측정이 필요하지만,
후보정은 좁고 결정적이라 그 규칙을 타는 테스트만 돌리면 된다. §2 원칙 1("알 수 있는 건
조회한다")의 출구다.

**못 찾은 지역을 밝힌다.** `resolve_region_scope` 가 매핑에 실패하면 빈 스코프를 주고
전국 검색이 됐다. `searched_intent` 가 `regionHints` 까지 덮어써 흔적도 없었다.
`RegionScope.unmapped` 로 이미 계산하고 버리던 값을 살렸다. §4 지역 사다리의 마지막 칸이다.
단 랜드마크는 제외한다 — "강남역" 은 실재하고 지역 필터로 못 쓸 뿐이다.

**`[[cards]]` 를 `[1]` 번호 참조로 바꾼다.** 마커가 실어 나르던 위치는 아무도 안 썼다
(`chat.py` 가 `WriterCards` 를 버렸다). 번호는 범위 검사가 가능해 **이름 환각이 기계로
검사된다.** 부록 A 의 Onyx `citation_processor.py` 방향과 같다.

**골든셋 F4 기대를 뒤집는다.** 아틀란티스는 해외가 아니라 존재하지 않는 곳이다.
`AGENT_OUT_OF_SCOPE` 문구("국내 여행지만 찾을 수 있어요")는 오타·낯선 지명에도 같이 나가
틀린 안내가 된다. `531ea34`(G6) 와 같은 판단.

### 13.3 §12 에 더할 것 — 골든셋의 구멍

§12 는 골든셋을 "재작성의 유일한 안전망" 이라 부르지만, 하네스는 `/v1/agent/ask` 를 때린다.
그 문은 결정적 세그먼트를 돌려주므로 **writer 가 실제로 쓴 문장 · 블로그 그라운딩 ·
outcome 분류 · SSE 는 커버리지가 0이었다.** #297 에서 `judge_chat` 과 P 그룹으로 덮었다.

결정적 산문 단언만 쓴다(심판 모델 없음): 마커 누출 · 합쇼체 · 전화번호 · 굵은 이름의 환각 ·
번호 범위 · 스트림↔`done` 일치 · 빈 답변.

### 13.4 채택하지 않기로 한 것 (§11 에 더함)

| 항목 | 이유 |
|---|---|
| **SSE 패킷 유니온 교체** | §12 가 6종 계약을 지키기로 했다. 필요하면 이벤트 **추가**로 간다 |
| **Onyx 다중 쿼리 + RRF** | 검색 N회. 우리 지연 예산과 안 맞고, 코퍼스가 문서가 아니라 정형 행이라 얻을 게 적다 |
| **자체 호스팅 증류 모델** | `CLIP_DEVICE=cpu`, 홈서버에 GPU 없음. Booking 의 TinyLlama+Medusa 는 인프라가 다르다 |
| **`/agent/ask` 삭제** | 프로덕션 소비자는 0이지만 골든셋 190케이스가 쓴다. 코어 직접 호출로 옮기는 건 하네스 재설계 |

### 13.5 남은 것

1. **`/agent/chat` 골든 케이스 라이브 검증** — P 그룹은 로컬 백엔드 + DeepSeek 키가 필요하다
2. **`Refused` 출력 타입** — §3.4 검증(`ModelRetry`)과 함께
3. **A/B diff 하네스** (§6) · `_rank_stats` 무효화 — 랭킹을 재려면 선행
4. **W3 도구 방식 A/B** — W1·W2 이득이 이미 확보돼 순수 도박 구간이다. 그물(1번)이 먼저다
5. 프리셋 카드 3종 · 30케이스 사람 검수
