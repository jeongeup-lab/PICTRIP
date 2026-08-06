# 여행 탭 대화 검증하기

> 여행 탭이 어떤 말에 어떻게 답해야 하는지를 고정한 골든셋과, 그것을 실제
> API에 던져 확인하는 방법.

`qa-travel-tab`이 **화면**을 본다면 이 문서는 **대답**을 본다. 같은 질문에
같은 종류의 답이 오는지, 검색이 돌지 말아야 할 자리에 돌지 않는지가 범위다.

## 전제

- 실행 대상 API가 Gemini 키와 실데이터를 갖고 있어야 한다. 프롬프트 변경은
  단위 테스트로 잡히지 않으므로 **모의 응답으로는 의미가 없다**.
- 로컬에서 돌릴 때는 `.env`에 `GEMINI_API_KEY`와 조회용 DB를 채운 뒤
  `uvicorn app.main:app --port 8099`로 띄운다.
- 케이스 하나가 Gemini 왕복 1회다. 61개면 약 5분, `agent_ask` 레이트리밋
  (20회/분)에 걸리지 않도록 러너가 3.5초 간격으로 던진다.

## 실행

```bash
cd backend
uv run python scripts/travel_golden_set.py                      # 전체
uv run python scripts/travel_golden_set.py --only D             # 그룹 하나
uv run python scripts/travel_golden_set.py --only 상세          # 이름으로도 된다
uv run python scripts/travel_golden_set.py --base-url https://api.pictrip.org
uv run python scripts/travel_golden_set.py --list               # 케이스 목록
```

케이스마다 `PASS/FAIL`, 실행된 툴 체인, 결과 수, 답변 앞부분을 찍는다. 실패가
하나라도 있으면 종료 코드가 1이다.

## 케이스가 고정하는 것

케이스는 **답변 문장 전체를 고정하지 않는다.** Gemini가 같은 뜻을 다른 말로
쓸 수 있기 때문이다. 대신 세 가지만 본다.

| 축 | 필드 | 뜻 |
|---|---|---|
| 라우팅 | `expect_tools` · `forbid_tools` | 어떤 툴이 돌았나 — "상세 질문에 검색이 돌면 실패" |
| 결과 | `expect_spots` (`some`·`none`·`any`) | 목록이 나와야 하는 턴인가 |
| 정직성 | `expect_text` · `forbid_text` | 답변이 적용된 조건을 말하는가, 안 한 일을 말하진 않는가 |

## 그룹

| 그룹 | 수 | 무엇을 지키나 |
|---|---|---|
| A 조건 없음 | 6 | `안녕`·`고마워`·`ㅇㅇ` 에 검색이 돌지 않는다 |
| B 검색 | 14 | 지역·카테고리·분위기·혼잡도·실내·근처·축제·장소명 축이 각각 산다 |
| C 후속 | 5 | 직전 턴의 조건을 잇고, 축 하나만 갈아끼운다 |
| D 상세 | 6 | 이용시간·휴무·주차·요금·문의·소개에 **검색이 아니라 답이** 온다 |
| E 범위 밖 | 6 | 해외·일정·예약·길찾기·날씨에 목록을 던지지 않는다 |
| F 데이터 경계 | 6 | 후보 풀에 없는 것(맛집·카페·숙소), 없는 지역, 일상 표기 지역 |
| G 방어 | 9 | 이모지·외국어·초장문·인젝션·SQL 흉내·빈 입력 |
| H 앵커 | 5 | Gemini 없이 도는 직송 경로 |
| I 칩 | 4 | intent·patch 왕복이 문장을 합성하지 않고 동작한다 |

## 알려진 실패

골든셋은 **아직 못 하는 일도 케이스로 갖고 있다.** 지우지 않는다 — 지우면
회귀가 아니라 사양이 된다.

| ID | 입력 | 지금 | 왜 남겨두나 |
|---|---|---|---|
| F1 · F2 | `통영 카페` · `부산 맛집` | 0곳 | 여행 후보 풀이 `HS·NA·EX·VE`뿐이라 `FD*`(음식·카페)가 구조적으로 빠진다. 앵커 칩은 찾는다 |
| E6 | `제주 호텔 추천해줘` | 0곳 | 숙박(`content_type_id=32`)은 풀에서 제외된다 |

## 자주 나는 문제

- **전부 `AGENT_INTENT_UNAVAILABLE`** — `GEMINI_API_KEY`가 비었거나 만료다.
- **A 그룹이 통과인데 B가 전부 0곳** — 조회 DB가 시드 데이터다. 실데이터를 본다.
- **`RATE_LIMITED`가 섞인다** — 같은 IP로 다른 클라이언트가 함께 던지고 있다.
  `--only`로 그룹을 나눠 돌린다.
- **D 그룹이 느리다** — 상세 캐시가 없는 스팟이면 KTO 라이브 조회가 붙는다
  (게이트웨이가 요청 절반을 4~8초 붙잡는다). 두 번째 실행부터 빨라진다.

---

관련: [qa-travel-tab](qa-travel-tab.md) · [travel-tab](../reference/travel-tab.md) ·
[api](../reference/api.md) ·
[ADR 0014](../adr/0014-travel-tab-answers-not-only-searches.md)
