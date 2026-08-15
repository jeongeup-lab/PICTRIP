# 0009. 플랜 마법사를 폐기하고 여행 탭을 대화형 에이전트로 전환한다

- 상태: 채택
- 날짜: 2026-07-25
- 관련: [travel-tab](../reference/travel-tab.md), [api](../reference/api.md),
  [0005 KTO 이미지 정책](0005-kto-image-policy.md),
  [0006 디자인 SSOT](0006-design-ssot-is-the-app.md)

## 맥락

플랜 탭은 마법사였다. `사진으로 시작` / `영상으로 시작` 두 진입구 →
`photo-match` · `from-video` · `places` 3화면을 순서대로 통과 → `assemble`이
일정을 조립 → `[planId]` 상세. 백엔드 `plan` 모듈 2,358 LOC, 모바일
`features/plan` 2,143 + 화면 961 LOC이 이 한 경로에 묶여 있다.

구조적 문제 셋:

- **입구가 콘텐츠를 요구한다.** 사진이나 유튜브 링크가 손에 없으면 탭에서
  할 수 있는 게 없다. 첫 화면이 빈 `내 일정` 목록이다.
- **조건을 되돌릴 수 없다.** "좀 더 가까운 곳"으로 바꾸려면 마법사를 처음부터
  다시 탄다. 3화면이 단방향 상태 머신이라 중간 수정 지점이 없다.
- **산출물이 일정표 하나다.** 대부분의 질문("비 와도 갈 만한 실내")은 일정이
  아니라 장소 목록을 원하는데, 마법사는 항상 day/slot 스케줄을 만든다.

같은 재료 — Gemini Flash 장소 추출, KTO 스팟 검색, CLIP 사진 매칭, 집중률 —
로 훨씬 넓은 질문을 받을 수 있다. 묶는 방식이 마법사일 이유가 없다.

## 결정

**플랜 탭을 여행 탭으로 바꾸고, 마법사를 대화형 에이전트 한 표면으로 대체한다.**

- 탭 이름 `플랜` → `여행`. 홈 · 탐색 · 마이는 손대지 않는다.
- 화면 = 채널 3단(인기 관광지 · 숨은 관광지 · 내 근처) + 그 아래로 대화가
  이어붙는 단일 스크롤. 하단 도크에 조건 칩 · 제안 칩 · 컴포저.
- 백엔드 진입점은 **`POST /v1/agent/ask` 하나**. 자유문 · 사진 · 정형 조건을
  한 요청으로 받고, 조회 단계 배열 + 답변 문장 + 스팟 목록을 한 번에 돌려준다.
- **검색은 결정적이다.** Gemini Flash는 자유문 → 구조화 의도(지역 · 카테고리
  키워드 · 혼잡도 선호 · 실내 여부) 추출에만 쓰고, 실제 조회는 기존 SQL·
  pgvector 툴이 한다. 정형 조건(지역 · 언제 · 누구와)은 시트/칩으로만 받아
  LLM을 거치지 않는다.
- **응답은 단일 JSON, 단계 재생은 클라이언트 애니메이션.** 서버가 실제 실행한
  툴과 각 단계의 잔여 건수를 `steps[]`로 내려주고, 모바일이 순차 재생한다.

## 고려한 대안

- **마법사 유지 + 검색 기능 추가** — 탭 안에 두 정신 모델이 공존한다. 첫
  화면에서 "무엇을 하는 탭인가"를 설명하지 못하는 지금 문제가 그대로 남는다. 기각.
- **SSE / 스트리밍 응답** — 단계를 진짜로 흘려보낸다. 다만 예상 지연이
  Gemini 의도 추출 0.6~1.2s + DB 조회 0.2s 수준이라, 스트리밍이 버는 체감이
  RN EventSource 도입 비용을 넘지 않는다. **실측 p95가 3초를 넘으면 재검토.**
- **LLM 툴콜 루프(모델이 툴을 고르고 반복 호출)** — 호출 수가 예측 불가라
  지연·비용이 튀고, 실패 모드가 사용자에게 "가끔 이상한 답"으로 샌다. 툴
  순서를 서버 코드가 고정하는 편이 같은 결과를 더 싸게 낸다. 기각.
- **CLIP 텍스트 인코더로 시맨틱 검색** — `app/ml/embedding.py`에는
  `embed_image`만 있고, ViT-B/32 텍스트 타워는 한국어 성능이 낮다. 한국어 →
  영어 번역 단계를 또 붙여야 한다. 카테고리 코드(`lcls_systm_codes`) 매칭이
  더 정확하고 설명 가능하다. 기각 — 사진 검색은 지금처럼 이미지 임베딩 유지.

## 결과

**모듈은 새로 만들지 않고 `plan`을 `agent`로 전환한다.** 재사용할 툴(Gemini
클라이언트 · 장소 해석 · 사진 매칭 · 지오)이 전부 그 모듈 안에 있어, 새 모듈을
세우면 `llm.py`·`naver.py`를 공유 패키지로 올리는 이사가 딸려온다. 이름만
바꾸면 교차 모듈 import가 하나도 생기지 않는다.

**폐기** — 마법사 전용 표면만 지운다.

- 백엔드: `POST /plan/import` · `/plan/assemble` · `/plan/from-spot` ·
  `/plan/photo-match`, `GET /plan/{id}` · `/plan/{id}/alternatives` ·
  `PATCH /plan/{id}`. services `assemble` · `seed` · `ingest` · `edit` ·
  `chains` · `titles`, `youtube.py`, `models.py`, 그리고 `PLAN_*` 에러 코드 전부.
- `plans` 테이블은 **드롭하지 않는다** — `curations`와 같은 처리로 ORM 모델만
  삭제하고 autogenerate `include_object`에서 제외한다 ([0002](0002-expand-contract-migrations.md)
  forward-only·contract 분리).
- 모바일: `app/plan/from-video.tsx` · `photo-match.tsx` · `places.tsx`,
  `plan-draft-store` · `recent-plans-store` · 마법사 전용 컴포넌트.

**존치** — 에이전트 툴로 재사용한다.

- `agent/services/resolve.py`(장소명 → KTO 스팟) · `geo.py` · `photo.py`,
  `agent/llm.py` · `naver.py`. 콘텐츠 → 장소를 뽑던 `extract.py`는 질문 → 의도를
  뽑는 `intent.py`로 대체된다(입력이 `IngestInput`에서 질문 한 줄로 바뀌었다).
- `GET /v1/home/channels/{key}` — 여행 탭 채널 3단이 그대로 쓴다.
- 결과 리스트 화면 `app/travel/results.tsx` (구 `app/plan/[planId].tsx` 자리).

**후속**

- KTO 출처 표기는 `마이 → 데이터 출처` 화면이 유일한 지점이 된다. 대화 답변에
  각주를 두지 않으므로 그 화면을 지우지 않는다 (`cpyrhtDivCd=Type3` 무변형 조건,
  [0005](0005-kto-image-policy.md)).
- 업로드 사진은 지금과 같이 **메모리에서만** 임베딩하고 바이트를 버린다.
- 조건 시트의 `언제`는 아직 **필터가 아니다**. `spot_concentration`이 일일
  스냅숏이라 미래 혼잡도가 없어, 답변 문구에만 실린다. 요일·시간대 예측이
  생기면 그때 필터로 승격한다.
- `docs/plans/agent-tab-prototype/`은 구현 완료 시 폐기 ([0006](0006-design-ssot-is-the-app.md)).
