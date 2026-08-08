# 여행 탭 화면 명세

> 여행 탭의 구성 요소·수치·상태 전이 조회표. 전환 배경은
> [ADR 0009](../adr/0009-travel-tab-conversational-agent.md), 조건 시트 폐기와
> 조회 축 교체는 [ADR 0010](../adr/0010-travel-tab-drops-condition-sheet.md),
> 칩 상태 기계는 [ADR 0011](../adr/0011-travel-tab-chip-state-machine.md),
> 턴별 각주 정리는 [ADR 0013](../adr/0013-travel-tab-drops-per-turn-footnotes.md),
> 검색 아닌 답변 경로는 [ADR 0014](../adr/0014-travel-tab-answers-not-only-searches.md),
> 시트 폐기와 지도 위 캐러셀 전환은
> [ADR 0017](../adr/0017-travel-tab-drops-the-sheet-for-a-map-carousel.md).
> 색·간격 정본은 `mobile/src/constants/theme.ts`.

탭은 홈 · 탐색 · **여행** · 마이 4개. 여행 탭만 이 문서의 범위다.

## 화면 구조

`src/app/(tabs)/travel.tsx` 는 풀블리드 지도 위에 **떠 있는 3층**을 얹는다.
시트도, 스냅도, 세로 스크롤도 없다. 화면에 존재하는 대화는 **마지막 턴 하나**다.

| 층 | 컴포넌트 | 세로 위치 | 조건 |
|---|---|---|---|
| 지도 | `features/map/components/KakaoWebMap` | 화면 전체 | 상시 |
| 답변 바 | `features/travel/components/AnswerBar` | `top = insets.top + 7` | 턴이 있을 때만 |
| 캐러셀 | `features/travel/components/SpotCarousel` | `bottom = dockBase` | 스팟이 있을 때. 질의 중에는 같은 자리에 `SpotCarouselSkeleton` |
| 독 | `features/travel/components/TravelDock` | `bottom = 0` | 상시 |

세 층은 전부 `position: absolute` 이고 사이가 비어 있다. 캐러셀을 감싼 슬롯
(`travel-carousel-slot`)은 `pointerEvents="box-none"` 이라 **칩 행 오른쪽 빈 자리,
층 사이 간격에서 시작한 팬은 지도에 닿는다.**

### 높이 계산 (`features/travel/lib/screen-layout.ts`)

독 높이는 상수가 아니라 **상태에서 계산한다.** 프라이머와 첨부 배너가 각각 독을
키우고, 그만큼 캐러셀 · 지도 여백 · 토스트가 함께 밀린다.

| 상수 | 값 |
|---|---|
| `DOCK_FIELD_PX` | 46 |
| `DOCK_PAD_BOTTOM_PX` | 12 |
| `DOCK_CHIP_ROW_PX` | 42 |
| `DOCK_ATTACH_ROW_PX` | 73 |
| `DOCK_PRIMER_PX` | 47 |
| `CAROUSEL_BLOCK_PX` | 135 (카드 112 + 9 + 바 3 + 11) |
| `FIT_TOP_PAD` · `FIT_SIDE_PAD` · `FIT_BOTTOM_MARGIN` | 96 · 40 · 24 |

```
dockBase   = 46 + 12 + (첨부 ? 73 : 42) + (프라이머 && !첨부 ? 47 : 0)
dockHeight = dockBase + (질의 중 || 스팟 있으면 135)
```

- 기본 `dockBase` = 100, 프라이머가 뜨면 147, 사진을 첨부하면 131.
- **첨부 중에는 프라이머를 그리지 않는다** — 둘을 동시에 더하면 독이 두 번 자란다.
- 지도 `fit` 패딩 = `{top: insets.top + 96, right: 40, bottom: dockHeight + 24, left: 40}`.
- 토스트는 `dockHeight + 12`, 검색 펄스(`SearchPulse`)는 `bottom = dockHeight`.

## 답변 바

턴이 있을 때만 그린다. 씨앗 카드가 들어와 있으면 턴을 비우므로 답변 바도 없다.

| 요소 | 값 |
|---|---|
| 바 | 좌우 14, padding 12(좌 14), radius 16, 1px `glassBorder`, `glassFill` |
| 사진 썸네일 | 40×40 radius 10. 그 턴이 사진을 실어 보냈을 때만 |
| 질문 줄 | 11/700 `ter` 1줄 말줄임 |
| 새 대화 | 우측 `close` 16 `ter` — `travel-new-chat` |
| 헤드라인 | 14.5/700 lineHeight 21 `ink`. `emphasis` 조각은 `accentText` |
| 보충 | 13/600 lineHeight 20 `sec`, 위 여백 5 |
| 펼침 셰브론 | `chevron-down`/`chevron-up` 18 `ter` |
| 대기 | 13px 링 스피너 + 단계 문구 12.5 `sec` |
| 실패 | 왼쪽 3px `accent` 띠 + `답변을 못 받았어요` 13.5 `accentText` + 사유 + `다시 시도`(h34, radius 12, `accent`) |

### 헤드라인과 보충이 갈리는 규칙

`features/travel/lib/answer-split.ts` 가 서버 `answer[]`(문장 조각 배열)을 자른다.

- **첫 문장 부호(`.` `?` `!`)까지가 헤드라인**이다. 뒤에 공백이나 끝이 와야 문장
  끝으로 친다 — `4.2km` 의 점에서 잘리지 않는다.
- 그 뒤 전부가 보충이고, 앞의 빈 조각과 공백은 버린다. 조각 하나가 두 문장을
  담고 있으면 그 조각을 쪼개고 `emphasis` 는 양쪽이 물려받는다.
- 보충이 있을 때만 셰브론이 붙는다. 접힘이 기본이고 탭하면 펼친다.
- **결과가 0장이면 처음부터 펼쳐 둔다** — 접을 이유가 없다.
- 대기 중이거나 실패한 턴에는 셰브론이 없다.

서버가 문장을 이 순서로 짓는다 — 구체적 사실이 앞, 조건·개수가 뒤
([api](api.md#post-agentask)).

## 결과 캐러셀

가로 `FlatList` 한 장. 스팟이 0개면 아예 렌더하지 않는다(`null`).

| 요소 | 값 |
|---|---|
| 카드 | 296×112, radius 18, 1px `glassBorder`, `glassFill` |
| 카드 간격 | 10 — 스냅 간격(`CARD_STRIDE`)은 306 |
| 좌우 여백 | 14 |
| 스냅 | `snapToOffsets`(index × 306) + `decelerationRate="fast"` |
| 진행 바 | h3, 위 9 / 아래 11, 좌우 18, radius 2, `fillStrong` 트랙 |
| 진행 채움 | `(focusedIndex + 1) / count` %, 최소 폭 14, `onDim` |

`추천 N곳` 목록 제목은 없다 — 개수는 답변 바가 문장으로 말하고, 어디쯤인지는
진행 바가 말한다.

**질의 중에는 같은 자리를 `SpotCarouselSkeleton` 이 채운다.** 같은 파일에서
export 하는 별도 컴포넌트로, 카드 치수(296×112, radius 18)의 `Skeleton` 판 2장과
빈 진행 트랙을 그려 `CAROUSEL_BLOCK_PX` 를 정확히 채운다. `FlatList` 도 포커스
콜백도 없어 포커스를 알리지 않고, `pointerEvents="none"` 이라 그 위에서 시작한
팬은 지도로 흘러간다. 화면은 스켈레톤과 `SpotCarousel` 을 형제로 두고 후자를
계속 마운트해 둔다 — 질의 중에는 스팟이 비어 스스로 `null` 을 돌려준다.

### 카드 해부 (`SpotCard`)

| 요소 | 값 |
|---|---|
| 썸네일 | 92×92 radius 12, `RemoteImage` |
| 번호 배지 | 20px 원, 11/800. 기본 `ink` 배경 + `bg` 글자, **보고 있는 카드만** `accent` 배경 + `onImage` 글자 |
| 제목 | 15/700 `ink` 1줄 |
| 지역 줄 | 12.5 `sec` — `regionLabel`, 거리가 있으면 ` · ` 뒤에 700 `ink` 로 붙는다 |
| 성질 칩 | h22 radius 7, 1px `line`, `fill`, 아이콘 13 + 11.5/700 `sec` |
| 상세보기 | h24 radius 8, 1px `line`, 우측 정렬, `상세보기` + `chevron-right` 12 |
| 하트 | 우상단 26×26, `heart`/`heart-fill` 17, 저장 시 `accent` |

거리는 **클라이언트가 잰다**(`lib/distance.ts` 하버사인). 좌표가 없으면 그리지
않는다. 1km 미만은 `m`(최소 10), 10km 미만은 소수 한 자리, 그 위는 정수 `km`.

성질 칩과 상세보기는 **같은 줄**이라 카드가 112를 넘지 않는다. 칩은 채워 있고
상세보기는 테두리만 있어 사실과 행동이 갈린다.

### 성질 칩은 서버 `tag` 를 그대로 쓴다 (`lib/metric.ts`)

클라이언트는 아이콘과 툴팁만 고른다. **라벨을 지어내지 않는다** — 서버가 준
문자열이 곧 라벨이다.

| 서버 `tag` | 아이콘 | 탭 툴팁 |
|---|---|---|
| `한산` · `보통` · `붐빔` · `하위 N%` | `users` | `tagBasis`, 없으면 `혼잡도 예측 기준` |
| `유사도 N%` (접두 일치) | `image` | `tagBasis`, 없으면 `사진 유사도 기준` |
| `D-N` | `calendar` | `축제 기간 기준` |
| `N.Nkm` · `Nm` | (칩 없음) | — |
| 그 밖의 값 | `tag` | 없음 — 탭 불가(`View`) |

툴팁이 있는 칩만 `Pressable` 이고, 탭하면 토스트로 그 문장을 띄운다. 접근성
라벨은 `"{라벨}, {툴팁}"` 이다. 거리 태그가 칩을 만들지 않는 이유는 지역 줄이
이미 같은 값을 말하기 때문이다.

## 독

씬 바닥에 붙는다. 위에서부터 **프라이머 → (첨부 배너 | 칩 행) → 필드**.

| 요소 | 값 |
|---|---|
| 독 | 좌우 14, 아래 패딩 12, `bottom = 0` |
| 위치 프라이머 | h38, 아래 9, radius 12, 1px `line`, `glassFill`. `location` 15 + `위치를 켜면 내 근처로 물어볼 수 있어요` 12.5/700 `sec` + `켜기` 11.5/800 `accentText` |
| 첨부 배너 | 아래 9, padding 8/10, radius 15, 1px `rgba(255,59,83,.32)`, `accentFill`. 46px 썸네일 + `이 사진 같은 분위기로 찾아요` 13.5/700 + `사진은 저장하지 않아요` 11.5 `sec` + `close` |
| 칩 행 | 고정 `사진` 칩 + 가로 `ScrollView`, 칩 간격 7, 밴드 아래 여백 9 |
| 칩 | h33 radius pill, 1px `line`, `raiseStrong`, 13/600 `ink` |
| 문맥 칩 | `accentFill` + 1px `rgba(255,59,83,.38)` + `accentText` 700, `map-pin` 14 |
| 사진 칩 | `image` 15 `accentText` + `사진` |
| 필드 | h46 radius 13, 1px `line`, `raiseStrong`. `search` 17 → 입력 15/600 → `camera` 30×32 → 전송 32×32 radius 8 |
| 전송 | 기본 `fillStrong`, 입력이나 첨부가 있으면 `accent` + `arrow-up` `onImage` |

- **프라이머는 권한이 `undetermined` 일 때만** 뜨고(`useNearbyCoords().askable`),
  **첨부 중에는 뜨지 않는다**. 탭하면 OS 권한 요청으로 간다.
- **첨부 배너는 칩 행 자리를 대체한다** — 둘이 동시에 뜨지 않아 세로 한 줄을 아낀다.
- 앨범은 `사진` 칩, 촬영은 필드 안 `camera` 아이콘이다. 둘 다 **첨부만** 하고
  전송은 하지 않는다. 실패 토스트는 권한 종류가 달라 나뉜다 —
  `사진을 불러오지 못했어요…` / `카메라를 열지 못했어요…`.
- placeholder 는 세 가지다 — 첨부 중이면 `지역이나 조건을 덧붙여 보세요`, 보고 있는
  카드가 있으면 `{제목}에 대해 물어보기`, 그 밖에는 `어디로 갈지 말해보세요`.
- 필드에 포커스가 가면 펼쳐 둔 문맥 칩이 닫힌다.
- 대기 중에는 필드·촬영·전송이 비활성이고 칩 탭도 무시한다.

### 칩 행 구성 (`lib/dock-chips.ts`)

`DockChip` 은 세 종류다 — `photo` · `context` · `query`(`lib/chips.ts` 의 `Chip`).

| 상태 | 칩 행 |
|---|---|
| 문맥 칩 **펼침** | `{제목}` (문맥, 닫기 `close` 달림) · `맛집` · `카페` · `볼거리` · `오늘 붐벼?`(`hasCrowd` 일 때만) |
| 답 있음 · refine 있음 | `사진` · `{제목} 근처`(보고 있는 카드) · refine 칩 |
| 답 있음 · refine 없음 | `사진` · `{제목} 근처` |
| 답 없음 · 좌표 O | `사진` · `근처 맛집` · `근처 볼거리` · `근처 카페` · `지금 축제` |
| 답 없음 · 좌표 X | `사진` · `지금 축제` · `사람 적은 바닷가` · `비 와도 갈 만한 실내` · `제주에서 한적한 곳` |

- `사진` 칩은 **스크롤 밖에 고정**된 첫 칸이다 — `ScrollView` 앞의 형제로 그려서
  칩이 아무리 많아도 밀려나가지 않는다. 사진 검색이 이 앱의 차별점이라 모든 칩
  상태에서 손이 닿아야 한다. 존재 여부는 여전히 `dockChips` 가 정하므로 문맥 펼침
  상태에서는 고정 자리도 비운다.
- `근처 볼거리` 만 앵커가 아니라 `intent{nearMe}` 다 — 앵커의 attraction 술어는
  전시·공연장을 빼기 때문이다. `지금 축제` 도 `intent{festivalOnly}` 직송이라
  Gemini 를 타지 않는다.
- 문맥 칩 펼침에서 **문맥 칩만 `accent`** 이고 술어(`맛집`·`카페`…)는 중립이다.
- 답이 온 뒤에는 초기 칩으로 돌아가지 않는다. refine 이 비면 칩 행은 사진 + 문맥
  칩만 남는다.

### 칩을 누르면 나가는 것

| 칩 | 요청 |
|---|---|
| `photo` | 요청 없음 — 앨범을 열어 첨부만 한다 |
| `context` | 요청 없음 — 펼침/접힘 토글 |
| `question` | 그 문자열을 자유문으로 전송 |
| `intent` | 준비된 `intent` 직송 (Gemini 없음) |
| `anchor` | 보고 있는 카드가 있으면 `{contentId, action}`, 없으면 `{action}`. 좌표도 카드도 없으면 아무것도 하지 않는다 |
| `refine` | 마지막 답의 `intent` + 그 칩의 `patch`. 사진 턴이면 **같은 사진을 다시 첨부해** 보낸다 |

`anchor` 칩의 질문 문구는 `"{제목} {라벨}"` 이고, 카드가 없으면 제목 자리에
`내 위치` 가 들어간다.

## 캐러셀과 지도

**보고 있는 카드가 곧 기준점이다.** 잡을 것도 풀 것도 없다 — 기준점을 고르거나
푸는 동작은 없고, 캐러셀이 멈춘 자리가 그대로 문맥이 된다
([ADR 0017](../adr/0017-travel-tab-drops-the-sheet-for-a-map-carousel.md)).

| 방향 | 동작 |
|---|---|
| 캐러셀 → 지도 | 스냅이 끝나면 `onMomentumScrollEnd` 가 인덱스를 계산해 지도 `center` 를 그 좌표로 옮기고 `anchorId` 를 그 `contentId` 로 준다. 펼쳐 둔 문맥 칩은 닫힌다 |
| 지도 → 캐러셀 | 핀 탭이 `onPinTap(contentId)` 로 오면 인덱스를 찾아 포커스를 옮기고 `scrollToOffset(index × 306, animated)` 로 그 장까지 스크롤한다. **상세로 보내지 않는다.** 목록에 없는 `contentId` 는 무시 |
| 새 답 | 포커스가 0번으로 돌아가고 `fit` 이 전체 핀을 담는다 |

핀 색은 앱 전체 규칙을 따른다 — 결과는 잉크, 기준점이 잡히면 그 핀만 라벨 달린
큰 `accent` 물방울이 되고 나머지 결과는 `PIN_RESULT`(파랑)로 바뀐다. 색은
`buildKakaoMapHtml` 이 HTML 에 굽는다(prop 으로 넘기면 WebView 가 리마운트된다).
카테고리 글리프·한반도 클램프는 지도 공용 규칙이다.

기준점이 무엇인지는 세 곳이 동시에 말한다 — 화면 가운데의 카드, `accent` 로 켜진
핀, 그리고 placeholder(`{제목}에 대해 물어보기`).

## 상세 진입

- **카드는 한 번 탭하면 상세다.** 카드 전체와 `상세보기` 버튼이 같은
  `/spots/{contentId}` 로 간다. `onPressIn` 이 상세를 프리페치한다.
- **탭 하나에 뜻이 하나뿐이다.** 두 번 탭 판정도, 그것 때문에 필요했던 VoiceOver
  커스텀 액션도 없다 — 스크린 리더가 카드를 활성화하면 상세로 간다.
- 하트는 카드 안에서 저장을 토글하고 성공 뒤에만 토스트를 띄운다.

## 스팟 상세에서 넘어오는 씨앗 카드

스팟 상세 아래의 `AskAboutSpot`(`{제목}에 대해 물어보기`)을 누르면
`travel/stores/anchor-store.ts` 에 그 스팟 한 장을 담고 여행 탭으로 이동한다.

- 씨앗이 있으면 여행 탭은 **대화를 비우고**(`clearTurns`) 그 한 장만 캐러셀에
  그린다. 답변 바도 `새 대화` 버튼도 없다.
- 지도는 그 스팟을 핀이자 중심으로 잡고 `anchorId` 도 그 카드다.
- placeholder 와 문맥 칩이 그 제목을 부르므로 곧바로 `근처 카페` 를 물을 수 있다.
- 질문을 보내면 씨앗을 비운다(`clearSeed`) — 답 위로 살아남지 않는다.
- 이전 답이 남은 채 씨앗이 도착하면 씨앗이 이긴다. `context.focusContentId` 에도
  씨앗의 `contentId` 가 실린다.

## 상태

| # | 상태 | 답변 바 | 캐러셀 | 독 |
|---|---|---|---|---|
| 1 | 빈 상태 · 좌표 O | 없음 | 없음 | 사진 · 근처 맛집 · 근처 볼거리 · 근처 카페 · 지금 축제 |
| 2 | 빈 상태 · 좌표 X | 없음 | 없음 | (미결정이면 프라이머) 사진 · 전국 칩 4개 |
| 3 | 사진 첨부 | 그대로 | 그대로 | 칩 행 자리를 첨부 배너가 대체, placeholder 교체 |
| 4 | 질의 중 | 질문 + 단계 스피너 | 스켈레톤 카드 | 초기 칩으로 되돌아가고 입력·전송 비활성, 지도 위 검색 펄스 |
| 5 | 결과 | 헤드라인 | 카드 N장 + 진행 바 | 사진 · 문맥 칩 · refine |
| 6 | 답변 펼침 | 헤드라인 + 보충 | 그대로 | 그대로 |
| 7 | 문맥 칩 펼침 | 그대로 | 그대로 | 문맥 칩 + 술어 칩 |
| 8 | 사진 턴 | 좌측에 보낸 사진 40px | 카드 N장 | 5와 같음 |
| 9 | 씨앗 카드 | 없음 | 씨앗 한 장 | 사진 · 문맥 칩 |
| 10 | 카드 없는 답 (0곳 · 상세 · 혼잡도) | 전문(항상 펼침) | 없음 | refine 이 있을 때만, 없으면 사진 칩만 |
| 11 | 실패 | `답변을 못 받았어요` + 사유 + `다시 시도` | 없음 | 초기 칩 |

- 10·11 은 캐러셀 자리가 비고 지도가 그만큼 더 보인다.
- 4 는 자리를 비우지 않는다 — 스켈레톤 카드가 들어가 `dockHeight` 가 그대로이므로
  답이 도착해도 지도 `fit` 이 다시 튀지 않는다. 스켈레톤은 `pointerEvents="none"`
  이라 그 위에서 시작한 팬도 지도에 닿는다.
- 4 에서 직전 결과는 화면에서 사라진다 — 답변 바는 새 질문을 이미 이름으로
  부르고 있는데 옛 카드가 남아 있으면 둘이 서로 다른 턴을 가리킨다.
- 11 의 `다시 시도` 는 실패한 **그 턴**을 재사용한다 — 질문·사진·`intent`·`patch`·
  `anchor`·`context` 를 그대로 다시 보내므로 턴이 늘어나지 않는다.
- 조건이 하나도 없는 질문은 검색하지 않는다 — `어디로 갈지 한 줄만 알려주세요…`
  한 줄과 초기 칩으로 끝난다.

---

관련: [ADR 0017](../adr/0017-travel-tab-drops-the-sheet-for-a-map-carousel.md) ·
[ADR 0014](../adr/0014-travel-tab-answers-not-only-searches.md) ·
[ADR 0011](../adr/0011-travel-tab-chip-state-machine.md) ·
[api](api.md) · [여행 탭 QA](../how-to/qa-travel-tab.md) ·
[architecture](../explanation/architecture.md)
