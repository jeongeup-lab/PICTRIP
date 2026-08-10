# 0014. 여행 탭이 검색만이 아니라 답도 한다

- 상태: 일부 대체 — "상세 프리워밍" 기각 근거(5만 곳)가 실측 모수(11,575곳)와
  달랐다. [0019](0019-detail-prewarm-resumes-on-a-smaller-set.md) 가 프리워밍을
  재개한다. 나머지 결정은 그대로다
- 날짜: 2026-08-06
- 관련: [0019 상세 프리워밍 재개](0019-detail-prewarm-resumes-on-a-smaller-set.md),
  [travel-tab](../reference/travel-tab.md), [api](../reference/api.md),
  [0009 여행 탭 대화형 에이전트](0009-travel-tab-conversational-agent.md),
  [0011 칩 상태 기계](0011-travel-tab-chip-state-machine.md),
  [0012 실제 지도·카드 탭](0012-travel-tab-live-map-and-card-tap.md)

## 맥락

여행 탭은 챗봇 모양을 하고 있지만 **자유문이 도달할 수 있는 결말이 스팟 목록
하나뿐이다.** `ask()` 의 분기는 요청 *모양*(anchor · photo · question)만 보고,
질문이면 `_ask_with_question` 으로 들어가 originPlace 앵커 · 축제 · 제목검색 ·
카테고리검색 중 하나를 고른다. 넷 다 목록으로 끝난다. 질문의 *종류*를 판정하는
지점이 코드에 없다.

프로덕션 왕복으로 확인한 결과다.

| 입력 | 실행된 툴 | 답변 |
|---|---|---|
| `세병관 영업시간 몇시야?` (직전 턴 실림) | intent → resolve_place → category_search 105곳 | 통영 20곳 |
| `통영 1박2일 일정 짜줘` | intent → category_search 105곳 | 통영 20곳 |
| `서울에서 통영 어떻게 가?` | intent → category_search | 목록 |

"영업시간"은 추출된 의도에 **흔적조차 남지 않는다.** `QueryIntent` 의 10개
필드가 전부 *어디를 찾는가*의 필터라 담을 칸이 없기 때문이다. 프롬프트를 고쳐도
스키마가 표현하지 못하는 의도는 나오지 않는다.

응답 계약도 같은 방향으로 굳어 있다. `AskResponse` 는 `spots` ·`totalCount` ·
`intent` ·`refinements` 를 모두 요구하고, 목록 없는 답변 경로는 혼잡도 칩 전용
`_anchor_crowd_response` 하나뿐이다. `ToolName` 리터럴에도 상세 조회가 없다.

**앵커와 말이 끊겨 있다.** 카드를 한 번 탭하면 그 스팟이 앵커가 되지만, 자유
입력을 시작하는 순간 앵커가 해제된다(`travel.tsx`). 카드를 골라놓고 "여기 몇
시까지야?"를 타이핑하면 그 선택이 서버로 가지 않는다. 말로 잇는 유일한 통로는
`originPlace` 인데 이건 "거기 근처"류만 잡는다.

답할 재료는 이미 있다 — `spot_details.intro_data` 의 `usetime` ·`restdate` ·
`parking` ·`infocenter`, 그리고 `tel` ·`homepage` ·`overview`. 다만 **캐시가
얇다**: 활성 스팟 50,577곳 중 상세가 적재된 곳이 1,680곳(3.3%)이고 그중
`usetime` 이 있는 곳이 870곳이다.

## 결정

**1. 의도 추출에 "무엇을 해달라는 턴인가" 축을 더한다.** `QueryIntent` 에
`task`(`search`·`detail`·`smalltalk`·`unsupported`, 기본 `search`) ·
`targetPlace` · `detailFields` 를 추가한다. 같은 `generate_json` 스키마에
필드를 더하는 것이라 **Gemini 왕복은 턴당 1회 그대로**이고, 검색은 여전히
결정적 SQL/pgvector다.

**2. `detail` 턴은 스팟 상세로 답한다.** 대상은 `focus`(앵커) → 직전 결과 제목
일치 → `resolve_places` 순으로 정한다. 값은 `spots` 모듈의 `load_spot_detail`
을 서비스 경유로 읽고 **원문 그대로** 문장에 얹는다. 없으면 없다고 말한다 —
지어내지 않는다.

**3. 캐시 미스는 라이브 KTO 1콜을 감수한다.** 상세 화면을 여는 것과 **같은
비용**이다(같은 `load_spot_detail`). 카드 두 번 탭이 이미 하는 일을 말로 하는
것뿐이라 새 비용이 아니다. KTO 게이트웨이가 요청 절반을 4~8초 붙잡으므로 대기
단계에 `상세 확인 중` 을 세운다.

**4. 앵커를 자유문에도 싣는다.** 입력을 시작해도 앵커를 해제하지 않고
`context.focusContentId` 로 보낸다. `0012` 가 정한 "자유 입력 시작 = 선택 해제"
규칙을 뒤집는다 — 그 규칙은 앵커가 칩으로만 쓰이던 때의 것이고, 지금은 말이
앵커를 쓰는 주된 방법이 된다.

**5. `unsupported` 는 못 한다고 말한다.** 일정 짜기 · 예약 · 길찾기 · 날씨는
목록을 던지지 않고 할 수 있는 일을 제안한다. 지금은 전부 검색으로 새어나간다.

## 고려한 대안

**분류를 위한 별도 LLM 콜.** 라우팅 전용 호출을 앞에 두면 의도 추출과 합쳐
왕복이 2회가 된다. 여행 탭 턴 지연이 그대로 두 배가 되고, Gemini 실패 지점도
둘로 늘어난다. 같은 스키마에 필드 3개를 더하는 쪽이 싸고 실패 표면도 좁다.

**규칙 기반 키워드 매칭.** `영업시간` ·`몇시` ·`주차` 같은 문자열로 라우팅하는
방법. 표현 다양성("언제까지 해?", "문 여나?", "쉬는 날 있어?")에 못 버티고,
지역명이 섞인 검색 질문("영업시간 긴 카페")을 상세로 오분류한다. 이미 의도
추출용 LLM 이 붙어 있는데 그 앞에 약한 규칙을 덧대는 것은 층만 늘린다.

**상세는 화면으로 넘기기.** "상세 화면에서 보세요"로 답하는 안. 카드 두 번
탭이면 되는 일을 대화가 거절하는 꼴이라, 챗봇 표면을 두고 있을 이유가 줄어든다.

**상세 프리워밍.** 5만 곳의 상세를 미리 채우면 라이브 콜이 사라진다. KTO 쿼터가
출시 후에나 증량되므로 지금은 불가능하고, 96.7%를 채우는 데 드는 콜 수가
일일 한도를 넘는다.

## 결과

- Gemini 호출 수는 변하지 않는다(턴당 1회).
- KTO 호출은 `detail` 턴에서만 최대 1회, 캐시 히트면 0회. 상세 화면 진입과
  같은 성격의 비용이다.
- `detail` 턴은 캐시 미스 시 4~8초까지 늘어날 수 있다.
- 오분류 위험이 생긴다 — `task` 기본값을 `search` 로 두고, `detail` 은 대상이
  특정될 때만 성립시켜 검색 쪽으로 안전하게 떨어뜨린다.
- 대화 회귀는 [여행 탭 대화 골든셋](../how-to/verify-travel-chat.md) 이 잡는다.

---

관련: [0009](0009-travel-tab-conversational-agent.md) ·
[0012](0012-travel-tab-live-map-and-card-tap.md) ·
[travel-tab](../reference/travel-tab.md) · [api](../reference/api.md)
