# 여행 탭 — 조용한 챗봇 개편 설계

- 날짜: 2026-08-01
- 상태: 승인 (구현 대기)
- 관련: [travel-tab](../../reference/travel-tab.md),
  [ADR 0009 대화형 에이전트](../../adr/0009-travel-tab-conversational-agent.md),
  [ADR 0010 조건 시트 폐기](../../adr/0010-travel-tab-drops-condition-sheet.md),
  [ADR 0006 디자인 SSOT](../../adr/0006-design-ssot-is-the-app.md)

## 배경

여행 탭은 `PinBoard`(전체 · 인기 · 숨은 곳 · 내 근처 필터 + 매스너리 핀) 아래로
대화가 이어붙는 구조다. 두 가지 문제가 있다.

- **채널 보드가 홈 탭과 중복이다.** 홈 탭의 `ChannelTiles`가 같은 6개 채널을
  스토리 뷰어로 이미 제공한다.
- **화면이 사진·채팅이 아니라 채널 보드를 말한다.** 서비스 차별점인 사진 매칭이
  보드 안 점선 카드 한 장으로 밀려 있다.

Mindtrip · Layla · Google Lens · Pinterest Lens를 조사한 결과 두 가지가 확인됐다.

- Lens 계열조차 사진 진입을 **화면 중앙 히어로가 아니라 입력 지점(검색바·컴포저)
  안에** 둔다. 큰 드롭존 히어로는 레퍼런스가 없다.
- Layla의 "위는 대화 내러티브, 아래는 카드" 2층 구조는 우리 `ConversationTurn`이
  이미 하고 있다. 대화 표면은 검증된 패턴 위에 있고, 문제는 그 위에 얹힌 보드뿐이다.

## 결정

**채널 보드를 삭제하고 여행 탭을 조용한 챗봇 한 표면으로 만든다.** 사진 강조는
카피가 아니라 컴포저 안에서 처리한다.

| 항목 | 값 |
|---|---|
| 상단바 | 워드마크 **좌측 정렬** + 우상단 `새 대화` 버튼 |
| 빈 상태 | 인사말 중앙 (졸라맨 + `오늘, 어디로 갈까요`) |
| 컴포저 | **빈 상태에도 하단 고정** |
| 제안 칩 | **상시 노출** (빈 상태에도 숨기지 않음) |
| placeholder | `사진을 올리거나 물어보세요` |
| 사진 버튼 | 아이콘만, `colors.accent` 틴트 (라벨 없음, 배경 채우지 않음) |

### 왜 컴포저를 하단에 고정하는가

Claude 앱은 빈 상태에서 컴포저를 중앙에 세웠다가 대화가 시작되면 하단으로
내린다. 그 전환을 버린다.

- 첫 질문에서 컴포저가 움직이지 않는다 — 화면이 튀지 않는다.
- **키보드가 올라와도 레이아웃이 흔들리지 않는다.** 중앙 배치의 가장 큰 비용이다.
- 빈 상태와 대화 상태의 구조가 같아져 **빈 상태 전용 렌더 분기가 사라진다.**

### 왜 강조를 카피가 아니라 아이콘으로 하는가

안내 문구는 읽히지 않는다. 반면 placeholder는 커서 바로 옆이라 반드시 읽히고,
비용은 문자열 하나다. 아이콘 틴트는 **면적을 1px도 늘리지 않으면서** 회색
일색인 컴포저에서 유일하게 색을 가진 요소가 된다.

라벨 pill(`사진으로 찾기`)은 발견률이 더 높지만 `내 근처`와 나란히 서서 액션이
둘로 보이고, 조용한 톤을 넘어선다. 기각.

**감수하는 것** — `colors.accent`는 이미 저장(하트)과 선택(앵커 링)에 쓴다.
사진 아이콘까지 accent면 의미가 하나 더 얹힌다. "이 앱의 주요 행동"으로
통일된다고 보고 받아들인다.

## 화면 명세

### 상단바

```
PICTRIP                                          [새 대화]
```

- 워드마크 좌측 정렬. 현행 스타일 유지 (`fontSize: 20, fontWeight: "800",
  letterSpacing: -0.5`).
- 우상단 `새 대화` = `useConversation`의 **`clear()` 배선**. 이 액션은
  `conversation-store.ts`에 이미 존재하지만 **어디서도 호출되지 않는 죽은
  코드**다. 지금 앱에는 대화를 비울 방법이 없다.
- 좌상단 대화 목록(스레드)은 **이번 범위 밖**. 대화 영속이 전제인데
  `conversation-store`가 메모리 zustand라 보여줄 게 없다.

### 빈 상태 (turns.length === 0)

스크롤 영역 안에서 수직 중앙 정렬. 캐릭터 → 인사말 순.

- 졸라맨 60px, `colors.ink`, 아래 여백 16px
- 인사말 `오늘,\n어디로 갈까요` — `fontSize: 26, fontWeight: "800",
  letterSpacing: -0.9, lineHeight: 34`
- 첫 턴이 생기면 180ms 페이드로 사라진다. 컴포저·칩은 움직이지 않는다.

### 도크 (항상 하단)

위에서부터 `anchor 배너` → `attach 배너` → `제안 칩` → `컴포저`.
현행 `AskComposer`의 구성과 순서가 같다. **칩을 빈 상태에서 숨기지 않는 것만
다르다.**

컴포저는 pill에서 rounded-rect로 바꾼다 — 입력 줄 아래에 액션 행을 두기 위해서다.

```
┌─────────────────────────────────────┐
│ 사진을 올리거나 물어보세요             │
│                                     │
│ [📷]  [📍 내 근처]              [↑] │
└─────────────────────────────────────┘
```

- 컨테이너: `borderRadius: 24`, `borderWidth: 1 / colors.line`, `padding: 12 12 10`
- 사진 버튼: 36×36, `borderRadius: 18`, `borderColor: rgba(230,0,35,0.32)`,
  아이콘 `colors.accent` 17px
- `내 근처` pill: 높이 36, `borderColor: colors.line`, `colors.sec`.
  좌표가 없으면 렌더하지 않는다 (현행 `idleChips`의 `NEARBY_CHIP` 조건과 동일)
- 전송: 36×36, 비활성 `colors.control` → 활성 `colors.ink`

### 대화

변경 없음. `ConversationTurn` · `StepList` · `AnswerBlock` · `SpotCard`
(158×206) · 앵커 선택 링 · 앵커 칩 전환 모두 현행 유지.

## 졸라맨 (④ 액자형)

`src/features/travel/components/Mascot.tsx` — 단일 소비자이므로 `src/components`가
아니라 feature 안에 둔다. 온보딩·마이 탭에서 재사용이 생기면 그때 승격한다.

`react-native-svg`의 `Svg`/`Path`/`Circle`/`Rect`로 그린다. viewBox `0 0 64 64`,
`strokeLinecap="round"`, `strokeLinejoin="round"`, `fill="none"`.
획 두께는 크기 비례: `strokeWidth = (size / 60) * 2.6`.

```
circle  cx=32 cy=11 r=6.5                       머리
path    M32 17.5 V 26                           목·상체
path    M32 24 L 20 29                          왼팔
path    M32 24 L 44 29                          오른팔
rect    x=18.5 y=27 w=27 h=19 rx=3              액자
path    M22 42 L 28.5 34.5 L 33 39 L 36.5 35.5 L 42 42   액자 안 능선
circle  cx=38.5 cy=32 r=2.2                     액자 안 해
path    M27 46 L 25 58                          왼다리
path    M37 46 L 39 58                          오른다리
```

**60px 가독성 — (a)로 확정(2026-08-01).** 5개 변형(60/72/120px × 해 유무)을
같은 `strokeWidth` 규칙으로 래스터라이즈해 비교한 결과:

- (b) 72px는 해결책이 아니다. `strokeWidth`가 크기에 비례하므로 확대해도
  해의 잉크/구멍 비율이 그대로다 — 60px에서 검은 점이던 것이 72px에서 20%
  큰 검은 점이 될 뿐이다. 링으로 읽히기 시작하는 건 120px부터다.
- (a) 해를 빼면 60px에서 액자 + 능선이 깨끗하게 읽힌다.

따라서 `circle cx=38.5 cy=32 r=2.2`는 그리지 않는다. 크기는 60px 유지.

떠 있는 애니메이션은 **4.2초 주기 ±4px**. 조용한 톤을 깨지 않는 선.
`react-native-reanimated`가 없으므로 `Animated.loop` + `useNativeDriver: true`로
`translateY`만 움직인다. 거슬리면 제거해도 무방하다.

## 삭제 대상

- `src/features/travel/components/PinBoard.tsx`
- `src/features/travel/components/PhotoStartCard.tsx`
- `src/features/travel/lib/board.ts` (`mergeBoardSpots` · `splitBoardColumns` ·
  `boardPinHeight`)
- `src/features/travel/lib/channel-spots.ts` (`channelCardsToSpots`)
- `travel.tsx`의 `useChannelCards` 3회 호출, `filter` 보드 상태,
  `NEARBY_NOTICE`, `lede` 블록, 보드 진입용 `onPhotoStart`
  (`anchorSpot`은 대화 앵커라 존치 — 위 대화 절 참조)
- 위 모듈의 테스트

**존치** — `src/features/channels/`는 건드리지 않는다. 홈 탭 `ChannelTiles`와
`/channels` 스토리 뷰어가 계속 쓴다.

## 범위 밖

- 대화 영속 (`expo-file-system`으로 JSON 저장) 및 좌상단 스레드 목록.
  별도 작업으로 뺀다.
- 결과를 사진 중심 레이아웃으로 바꾸는 것 (히어로 1장 + 레일).
- 스텝 리스트를 완료 후 한 줄로 접는 것.
- 사진 촬영 진입 (`ImagePicker.launchCameraAsync`).
- 백엔드. **무변경이다.**

## 검증

```bash
cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test
```

- `PinBoard` 관련 테스트 삭제 후 남은 스위트가 통과할 것
- 빈 상태 → 첫 질문 → 컴포저가 이동하지 않음을 렌더 테스트로 고정
- 칩이 `turns.length === 0`에서도 렌더됨을 테스트로 고정
- `새 대화` 탭 시 `turns`가 비워짐을 테스트로 고정
- 실기기에서 키보드를 올렸을 때 레이아웃이 흔들리지 않는지 육안 확인 (미실시)
- 졸라맨 60px 가독성 → (a) 해 제거로 확정 (위 참조)
