# 여행 탭 화면 명세

> 여행 탭의 구성 요소·수치·상태 전이 조회표. 채팅-first 전환과 LLM 라이터
> 도입 배경은 [ADR 0020](../adr/0020-travel-tab-chat-first-llm-writer.md).
> 구 지도-패널 구조(ADR 0015~0018)는 이 전환으로 폐기됐다.
> 색·간격 정본은 `mobile/src/constants/theme.ts`, SSE 계약은
> [api](api.md#post-agentchat).

탭은 홈 · 탐색 · **여행** · 마이 4개. 여행 탭만 이 문서의 범위다.

## 화면 구조

`src/app/(tabs)/travel.tsx` 는 **채팅 트랜스크립트** 화면이다. 위에서부터
헤더 → 트랜스크립트(FlatList) → 컴포저 세 층이고, 풀블리드 지도·패널·독은
없다. 지도는 턴 안의 인라인 카드로만 존재한다.

| 층 | 구성 | 비고 |
|---|---|---|
| 헤더 | 중앙 `PICTRIP` 워드마크 (16/800, letterSpacing 2.5, `onImage` 흰색, 아이콘 없음) + 좌측 새 대화 버튼(`plus` 19, 32px 원, `travel-new-chat`) | 새 대화 = 진행 중 스트림 abort + 스토어 clear |
| 트랜스크립트 | `travel-transcript` FlatList — 헤더로 `WelcomeBubble`, 항목 = 턴(유저 버블 + 어시스턴트 턴), 항목 간 `spacing.lg` | `onContentSizeChange` 마다 하단 자동 스크롤 |
| 컴포저 | `ChatComposer` — 키보드 높이만큼 리프트(`use-keyboard-height`) | 스트리밍 중 입력 잠금 |

## 첫 진입 — 웰컴 버블

`WelcomeBubble` 이 좌측 정렬 말풍선으로 인사말을 타이핑한다.

- 문구: `안녕하세요, PICTRIP 어시스턴트예요.\n뭐든 물어보세요.` (`WELCOME_TEXT`)
- 칩·추천 질문 없음 — 진입점은 컴포저뿐이다.

## 턴 해부

턴 = 유저 버블(`UserBubble`, 우측 정렬, 사진 턴이면 썸네일) + 어시스턴트
턴(`AssistantTurn`). 어시스턴트 턴은 위에서부터:

| 블록 | 내용 | 조건 |
|---|---|---|
| 스텝 행 | 체크(13, done) 또는 스피너 링 + 라벨 12.5 `sec` + badge 11.5/700 `ter` | `steps` 있을 때. 스트리밍인데 스텝이 아직 없으면 `답변을 준비하는 중` 한 줄 |
| 본문 | `RichAnswerText` — `**굵게**` 와 줄 시작 `- ` 불릿만 파싱, 그 외 마크다운 무시 | `delta` 누적 텍스트 |
| 카드 캐러셀 | 기존 `SpotCarousel`/`SpotCard` 재사용. 카드 탭 = `/spots/{contentId}`, 하트 저장, 거리(하버사인) | `spots` 있을 때 |
| 지도 카드 | 인라인 `KakaoWebMap` h190 radius 18, 핀 = spots, 핀 탭 = 캐러셀 포커스 동기화 | **최신 턴 + 좌표 있는 스팟이 있을 때만** (이전 턴은 미렌더 — 성능) |
| 출처 행 | 파비콘 겹침(20px, -7 겹침, ≤3) + `소스 N` 필. 탭 = `SourcesSheet` | `sources` 있을 때 |
| 실패 블록 | 좌측 3px `accent` 띠 + `답변을 못 받았어요` + `err.code` 사유 + `다시 시도`(h34, `accent`) | `status = error` |
| 팔로업 칩 | h31 pill, `accentText` 12.5/700, 탭 = 그 문자열로 새 턴 전송 | **최신 done 턴만** — 이전 턴 칩이 낡은 문맥으로 나가는 것 방지 |

`SourcesSheet` 는 Modal 바텀시트 — kind별 아이콘(naver_blog·kto·kakao), 제목·
날짜, url 탭 = `Linking`. KTO 행은 spots 가 있던 턴에 항상 포함된다.

## 컴포저

| 요소 | 값 |
|---|---|
| placeholder | `PICTRIP에게 물어보세요` (`ASK_PLACEHOLDER`) |
| 스트리밍 중 | `답변을 만드는 중…` + 입력·전송·첨부 잠금 |
| 사진 첨부 | 앨범·카메라 ActionSheet. 첨부 배너에 `사진은 저장하지 않아요` 유지 |
| 전송 | 텍스트 또는 사진이 있어야 활성. 사진 턴은 multipart(`photo`) |

## 스트리밍 소비 규칙 (`stores/chat-store.ts` · `lib/sse.ts`)

`streamChat` 이 `POST /agent/chat` SSE 를 `expo/fetch` ReadableStream 으로
읽는다(`SseParser` — CRLF·multi-line data·UTF-8 청크 경계 안전, AbortController).

- `step` — 같은 index 로 run→done upsert. `done` 수신 시 남은 run 스텝 일괄 done.
- `delta` — `text` 누적.
- `cards` / `sources` / `suggestions` — 턴 필드 교체.
- `done` — 조립본으로 턴 확정(`status: done`).
- `error` — `status: error` + `errorCode`. 스트림이 done/error 없이 끝나면
  `UNKNOWN` 실패로 처리한다(안전망).
- `activeId` 가드 — 새 대화 뒤 도착하는 늦은 이벤트는 버린다.
- `다시 시도` 는 실패한 턴을 **제자리 교체**한다(같은 `request` 재전송, 턴 수 불변).

## 서버로 나가는 것

전송 시 `{message, lat, lng, clientTime, context, history}` —

- `context` = 직전 done 턴의 intent·spots + 핀/캐러셀 포커스 `contentId`
  (`lib/conversation-context.ts`). 조회 연속성 담당.
- `history` = 마지막 8개 `{role, text, spotIds}` (어시스턴트는 앞 300자).
  라이터 문맥 담당.
- `clientTime` = ISO 문자열. 시간대 인지(늦은 밤 → 야간 언급).
- 좌표는 권한이 있으면 조용히 동봉(`use-nearby-coords`). 별도 프라이머 UI 없음.

## 상태

| # | 상태 | 화면 |
|---|---|---|
| 1 | 빈 상태 | 웰컴 버블 + 컴포저 |
| 2 | 질의 중 | 유저 버블 → 스텝 행(스피너→체크) → 본문이 스트리밍으로 자람 |
| 3 | 결과 | 본문 + 카드 + (최신 턴) 지도 + 출처 + 팔로업 칩 |
| 4 | 사진 턴 | 유저 버블에 첨부 썸네일, 이후 3과 동일 |
| 5 | 결과 0곳 | 본문(조건 변경 제안)만 — 카드·지도 없음 |
| 6 | 실패 | 실패 블록 + `다시 시도` |
| 7 | 새 대화 | 스트림 abort + 전체 초기화 → 1 |

---

관련: [ADR 0020](../adr/0020-travel-tab-chat-first-llm-writer.md) ·
[ADR 0009](../adr/0009-travel-tab-conversational-agent.md) ·
[api](api.md#post-agentchat) · [architecture](../explanation/architecture.md)
