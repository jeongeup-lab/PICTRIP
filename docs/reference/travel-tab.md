# 여행 탭 화면 명세

> 여행 탭의 구성 요소·수치·상태 전이 조회표. 전환 배경은
> [ADR 0009](../adr/0009-travel-tab-conversational-agent.md), 조건 시트 폐기와
> 조회 축 교체는 [ADR 0010](../adr/0010-travel-tab-drops-condition-sheet.md),
> 칩 상태 기계는 [ADR 0011](../adr/0011-travel-tab-chip-state-machine.md),
> 턴별 각주 정리는 [ADR 0013](../adr/0013-travel-tab-drops-per-turn-footnotes.md),
> 검색 아닌 답변 경로는 [ADR 0014](../adr/0014-travel-tab-answers-not-only-searches.md),
> 시트 폐기와 지도 위 캐러셀 전환은
> [ADR 0017](../adr/0017-travel-tab-drops-the-sheet-for-a-map-carousel.md),
> 세 층을 패널 하나로 합친 것은
> [ADR 0018](../adr/0018-travel-tab-answers-in-one-rising-panel.md).
> 색·간격 정본은 `mobile/src/constants/theme.ts`.

탭은 홈 · 탐색 · **여행** · 마이 4개. 여행 탭만 이 문서의 범위다.

## 화면 구조

`src/app/(tabs)/travel.tsx` 는 풀블리드 지도 위에 **패널과 독 두 층**을 얹는다.
시트도, 스냅도, 세로 스크롤도 없다. 화면에 존재하는 대화는 **마지막 턴 하나**다.

| 층 | 컴포넌트 | 세로 위치 | 조건 |
|---|---|---|---|
| 지도 | `features/map/components/KakaoWebMap` | 화면 전체 | 상시 |
| 결과 패널 | `features/travel/components/ResultPanel` | `bottom = dockBase` | 턴이나 씨앗이 있을 때만 |
| 독 | `features/travel/components/TravelDock` | `bottom = 0` | 상시 |

**결과 패널이 한 턴을 통째로 담는다.** 위에서부터 답변 문장(`AnswerBar`) → 가로
카드(`SpotCarousel`, 질의 중에는 `SpotCarouselSkeleton`) → 문맥 칩(`ChipRow`)
순이고, 셋은 같은 상자 안에 세로로 붙어 있다.

패널은 **불투명**(`colors.inset` + 1px `glassBorder` + `shadows.card`)하다.
지도는 카카오 기본 밝은 지도 그대로이므로 반투명 바탕으로는 글씨가 도로·라벨과
겹친다([ADR 0018](../adr/0018-travel-tab-answers-in-one-rising-panel.md)).

**그림자와 모서리 클리핑은 다른 뷰에 둔다.** 바깥(`travel-result-panel`)이
배경·radius·그림자를, 안쪽(`travel-result-surface`)이 테두리·패딩·
`overflow: hidden` 을 맡는다. iOS 는 같은 뷰의 `overflow: hidden` 으로 legacy
`shadow*` 까지 잘라내 그림자가 실기기에서 사라진다.

두 층 모두 `position: absolute` + `pointerEvents="box-none"` 이라 **패널 옆 여백,
칩 행 오른쪽 빈 자리에서 시작한 팬은 지도에 닿는다.**

### 높이 계산 (`features/travel/lib/screen-layout.ts`)

독과 패널 높이는 상수가 아니라 **상태에서 계산한다.** 프라이머와 첨부 배너가
독을, 칩 줄과 캐러셀이 패널을 키우고, 그만큼 지도 여백 · 토스트가 함께 밀린다.

| 상수 | 값 |
|---|---|
| `DOCK_FIELD_PX` | 46 |
| `DOCK_PAD_BOTTOM_PX` | 12 |
| `DOCK_CHIP_ROW_PX` | 42 |
| `DOCK_ATTACH_ROW_PX` | 73 |
| `DOCK_PRIMER_PX` | 47 |
| `PANEL_PAD_PX` | 26 (위 12 + 아래 12 + 테두리 2) |
| `PANEL_HEAD_PX` · `PANEL_COPY_PX` | 22 · 48 |
| `PANEL_CHIP_ROW_PX` · `PANEL_CHIP_GAP_PX` | 33 · 12 |
| `CAROUSEL_BLOCK_PX` | 135 (카드 112 + 9 + 바 3 + 11) |
| `FIT_TOP_PAD` · `FIT_SIDE_PAD` · `FIT_BOTTOM_MARGIN` | 96 · 40 · 24 |

```
dockBase   = 46 + 12 + (첨부 ? 73 : 패널 없으면 42, 있으면 0)
                     + (프라이머 && !첨부 ? 47 : 0)
어림값     = 26 + 22 + 48 + (칩 있으면 33 + (캐러셀 없으면 12))
                     + (질의 중 || 스팟 있으면 135)
panelBlock = 패널 실측 높이(onLayout) ?? 어림값
coveredPx  = dockBase + panelBlock
```

- 빈 화면 `dockBase` = 100(칩 줄 포함), 프라이머가 뜨면 147.
- **결과가 떠 있는 동안 독은 입력 줄만 남는다**(`dockBase` = 58) — 칩을 패널이
  가져갔기 때문이다. 사진을 첨부하면 배너가 들어와 131 이 된다.
- **첨부 중에는 프라이머를 그리지 않는다** — 둘을 동시에 더하면 독이 두 번 자란다.
- **패널 높이는 실측이 정본이다.** `ResultPanel` 의 `onLayout` 이 올려보낸 값이
  `coveredPx` 에 들어가고, `panelBasePx` 는 **첫 프레임용 어림값**으로만 쓰인다.
  답변을 펼치면 복사 영역이 42 → 최대 210 으로 자라는데, 어림값만 쓰면 토스트가
  펼친 답변 위를 덮고 지도 `fit` 이 아래쪽 핀을 패널 뒤에 숨긴다.
- `PANEL_HEAD_PX`·`PANEL_COPY_PX` 는 그 어림값의 재료다. `PANEL_PAD_PX` 만
  스타일시트와 잠겨 있다(`ResultPanel.test.tsx`).
- 실측이 `coveredPx` 를 바꿔도 패널 자신의 높이는 바뀌지 않는다 — 패널의 `bottom`
  은 `dockBase` 라 `coveredPx` 와 무관하다. 측정 루프가 생기지 않는 이유다.
- 지도 `fit` 패딩 = `{top: insets.top + 96, right: 40, bottom: coveredPx + 24, left: 40}`.
- 토스트는 `coveredPx + 12`, 검색 펄스(`SearchPulse`)는 `bottom = coveredPx`.

## 답변 바

패널의 첫 블록이다. 턴이 있을 때만 그린다 — 씨앗 카드가 들어와 있으면 턴을
비우므로 패널은 있고 답변 바만 없다.

| 요소 | 값 |
|---|---|
| 바 | 패널 안 좌우 14. 자체 배경·테두리 없음(패널이 바탕) |
| 사진 썸네일 | 40×40 radius 10. 그 턴이 사진을 실어 보냈을 때만 |
| 질문 줄 | 11/700 `ter` 1줄 말줄임 |
| 새 대화 | 우측 `close` 16 `ter` — `travel-new-chat` |
| 헤드라인 | 14.5/700 lineHeight 21 `ink`. `emphasis` 조각은 `accentText` |
| 보충 | 13/600 lineHeight 20 `sec`, 위 여백 5 |
| 펼침 셰브론 | `chevron-down`/`chevron-up` 18 `ter` |
| 대기 | 13px 링 스피너 + 단계 문구 12.5 `sec` |
| 실패 | 왼쪽 3px `accent` 띠 + `답변을 못 받았어요` 13.5 `accentText` + 사유 + `다시 시도`(h34, radius 12, `accent`) |

패널의 좌우 여백(14)은 카드 레일·칩 행과 같은 값이라 셋이 같은 왼쪽 선에 선다.

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
| 카드 | 296×112, radius 18, 1px `glassBorder`, `glassFill` — 패널 안쪽이라 좌우 334 중 다음 장이 36 남는다 |
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
**칩 행은 결과 패널이 없을 때만** 독에 있다 — 패널이 뜨면 칩은 패널 안으로 옮겨
가고 독은 프라이머·첨부 배너·필드만 남는다.

| 요소 | 값 |
|---|---|
| 독 | 좌우 14, 아래 패딩 12, `bottom = 0` |
| 위치 프라이머 | h38, 아래 9, radius 12, 1px `line`, `glassFill`. `location` 15 + `위치를 켜면 내 근처로 물어볼 수 있어요` 12.5/700 `sec` + `켜기` 11.5/800 `accentText` |
| 첨부 배너 | 아래 9, padding 8/10, radius 15, 1px `rgba(255,59,83,.32)`, `accentFill`. 46px 썸네일 + `이 사진 같은 분위기로 찾아요` 13.5/700 + `사진은 저장하지 않아요` 11.5 `sec` + `close` |
| 칩 행 | `ChipRow` — 고정 `사진` 칩 + 가로 `ScrollView`, 칩 간격 7. 독에서는 아래 여백 9, 패널 안에서는 좌우 14 |
| 칩 | h33 radius pill, 1px `line`, `raiseStrong`, 13/600 `ink` |
| 사진 칩 | `accentFill` + 1px `rgba(255,59,83,.38)` + `accentText` 700, `image` 15 |
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
- 대기 중에는 필드·촬영·전송이 비활성이고 칩 탭도 무시한다.

### 칩 행 구성 (`lib/dock-chips.ts`)

`DockChip` 은 두 종류다 — `photo` · `query`(`lib/chips.ts` 의 `Chip`). 만드는
함수도 둘이고, 나오는 자리가 다르다.

| 함수 | 자리 | 칩 행 |
|---|---|---|
| `dockChips()` | 독 (패널 없을 때) | `사진` · `근처 카페` · `근처 맛집` · `근처 볼거리` — **고정** |
| `panelChips()` | 패널 (카드 아래) | `사진` · `{제목} 근처 카페` · `{제목} 근처 맛집` · `{제목} 근처 볼거리` · `{제목} 오늘 붐벼?`(`hasCrowd` 일 때만) · refine 칩 |

- **첫 화면 칩은 좌표로 갈리지 않는다.** 좌표가 없어도 넷 그대로 그리고, 누른
  뒤에 위치를 묻는다([ADR 0018](../adr/0018-travel-tab-answers-in-one-rising-panel.md)).
  `useNearbyCoords().phase` 로 세 갈래다 — `checking` 이면
  `위치를 확인하는 중이에요`, 권한이 `undetermined`(`askable`)면 OS 요청,
  그 밖에는 `위치를 켜면 내 근처를 찾아드려요`.
- **좌표를 아직 모르는 구간을 거절과 섞으면 안 된다.** 권한을 이미 허용한
  사용자에게 켜라고 말하게 된다. `phase = "checking"` 이 두 구간을 모두 덮는다 —
  앱 진입 직후의 권한·좌표 조회, 그리고 `ask()` 가 OS 창을 띄우고 좌표를 받아올
  때까지. `ask()` 는 `askable` 만 내리는 게 아니라 `phase` 도 `checking` 으로
  되돌린다.
- **문맥 칩은 세 장 다 카드 이름을 앞에 단다** — `{제목} 근처 카페` 처럼. 펼침
  단계가 없어 한 번에 닿고, **칩 글씨가 곧 보낼 질문 문장**이다.
- `사진` 칩은 **스크롤 밖에 고정**된 첫 칸이다 — `ScrollView` 앞의 형제로 그려서
  칩이 아무리 많아도 밀려나가지 않는다. 사진 검색이 이 앱의 차별점이라 결과가
  떠 있는 동안에도 손이 닿아야 하므로 패널 칩 행에도 남긴다.
- 초기 칩의 `근처 볼거리` 만 앵커가 아니라 `intent{nearMe}` 다 — 앵커의 attraction
  술어는 3km 반경에 갇히기 때문이다. 문맥 칩의 `{제목} 근처 볼거리` 는 그 스팟
  좌표가 기준이므로 앵커(`nearby`)가 맞다.
- **카드가 0장이면 문맥 칩도 없다** — 이름을 붙일 카드가 없다. 그 턴의 칩 행은
  `사진` + refine 뿐이다.

### 칩을 누르면 나가는 것

| 칩 | 요청 |
|---|---|
| `photo` | 요청 없음 — 앨범을 열어 첨부만 한다 |
| `question` | 그 문자열을 자유문으로 전송 |
| `intent` | 준비된 `intent` 직송 (Gemini 없음). `nearMe` 인데 좌표가 없으면 위치부터 묻는다 |
| `anchor` | 보고 있는 카드가 있으면 `{contentId, action}`, 없으면 `{action}`. 좌표도 카드도 없으면 위치부터 묻는다 |
| `refine` | 마지막 답의 `intent` + 그 칩의 `patch`. 사진 턴이면 **같은 사진을 다시 첨부해** 보낸다 |

**칩 라벨이 그대로 질문 문구다.** 보고 있는 카드가 있으면 라벨(`천지연 근처 맛집`)
이 곧 턴의 `question` 이고, 카드가 없을 때만 `내 위치` 를 앞에 붙여
`내 위치 근처 카페` 로 만든다.

## 캐러셀과 지도

**보고 있는 카드가 곧 기준점이다.** 잡을 것도 풀 것도 없다 — 기준점을 고르거나
푸는 동작은 없고, 캐러셀이 멈춘 자리가 그대로 문맥이 된다
([ADR 0017](../adr/0017-travel-tab-drops-the-sheet-for-a-map-carousel.md)).

| 방향 | 동작 |
|---|---|
| 캐러셀 → 지도 | 스냅이 끝나면 `onMomentumScrollEnd` 가 인덱스를 계산해 지도 `center` 를 그 좌표로 옮기고 `anchorId` 를 그 `contentId` 로 준다. **문맥 칩 이름도 같이 바뀐다** |
| 지도 → 캐러셀 | 핀 탭이 `onPinTap(contentId)` 로 오면 인덱스를 찾아 포커스를 옮기고 `scrollToOffset(index × 306, animated)` 로 그 장까지 스크롤한다. **상세로 보내지 않는다.** 목록에 없는 `contentId` 는 무시 |
| 새 답 | 포커스가 0번으로 돌아가고 `fit` 이 전체 핀을 담는다 |

핀 색은 앱 전체 규칙을 따른다 — 결과는 잉크, 기준점이 잡히면 그 핀만 라벨 달린
큰 `accent` 물방울이 되고 나머지 결과는 `PIN_RESULT`(파랑)로 바뀐다. 색은
`buildKakaoMapHtml` 이 HTML 에 굽는다(prop 으로 넘기면 WebView 가 리마운트된다).
카테고리 글리프·한반도 클램프는 지도 공용 규칙이다.

기준점이 무엇인지는 네 곳이 동시에 말한다 — 화면 가운데의 카드, `accent` 로 켜진
핀, 카드 아래 문맥 칩(`{제목} 근처 카페`…), 그리고
placeholder(`{제목}에 대해 물어보기`).

## 상세 진입

- **카드는 한 번 탭하면 상세다.** 카드 전체와 `상세보기` 버튼이 같은
  `/spots/{contentId}` 로 간다. `onPressIn` 이 상세를 프리페치한다.
- **탭 하나에 뜻이 하나뿐이다.** 두 번 탭 판정도, 그것 때문에 필요했던 VoiceOver
  커스텀 액션도 없다 — 스크린 리더가 카드를 활성화하면 상세로 간다.
- 하트는 카드 안에서 저장을 토글하고 성공 뒤에만 토스트를 띄운다.

## 스팟 상세에서 넘어오는 씨앗 카드

스팟 상세 아래의 `AskAboutSpot`(`{제목}에 대해 물어보기`)을 누르면
`travel/stores/anchor-store.ts` 에 그 스팟 한 장을 담고 여행 탭으로 이동한다.

- 씨앗이 있으면 여행 탭은 **대화를 비우고**(`clearTurns`) 그 한 장만 패널 안
  캐러셀에 그린다. 답변 바도 `새 대화` 버튼도 없다.
- 지도는 그 스팟을 핀이자 중심으로 잡고 `anchorId` 도 그 카드다.
- placeholder 와 문맥 칩이 그 제목을 부르므로 곧바로 `근처 카페` 를 물을 수 있다.
- 질문을 보내면 씨앗을 비운다(`clearSeed`) — 답 위로 살아남지 않는다.
- 이전 답이 남은 채 씨앗이 도착하면 씨앗이 이긴다. `context.focusContentId` 에도
  씨앗의 `contentId` 가 실린다.

## 상태

| # | 상태 | 패널 | 독 |
|---|---|---|---|
| 1 | 빈 상태 | 없음 | 사진 · 근처 카페 · 근처 맛집 · 근처 볼거리 |
| 2 | 빈 상태 · 위치 미결정 | 없음 | 프라이머 + 1과 같은 칩 넷 |
| 3 | 사진 첨부 | 그대로 | 칩 행 자리를 첨부 배너가 대체, placeholder 교체 |
| 4 | 질의 중 | 질문 + 단계 스피너 → 스켈레톤 카드 → 사진 칩 | 입력 줄만, 전송 비활성, 지도 위 검색 펄스 |
| 5 | 결과 | 헤드라인 → 카드 N장 + 진행 바 → `{제목} 근처` 칩 셋 · refine | 입력 줄만 |
| 6 | 답변 펼침 | 헤드라인 + 보충. 카드·칩은 제자리, 패널이 위로 자란다 | 그대로 |
| 7 | 카드 스와이프 | 칩 셋 이름이 새 카드로 교체 | placeholder 교체 |
| 8 | 사진 턴 | 답변 바 좌측에 보낸 사진 40px | 5와 같음 |
| 9 | 씨앗 카드 | 답변 바 없이 카드 한 장 + `{제목} 근처` 칩 셋 | 입력 줄만 |
| 10 | 카드 없는 답 (0곳 · 상세 · 혼잡도) | 전문(항상 펼침) + 사진 칩 · refine. 카드 자리 없음 | 입력 줄만 |
| 11 | 실패 | `답변을 못 받았어요` + 사유 + `다시 시도` | 입력 줄만 |

- 1·2 는 패널이 없어 지도가 화면 거의 전부다.
- 10·11 은 카드 자리가 비어 패널이 얇아지고 지도가 그만큼 더 보인다.
- 4 는 자리를 비우지 않는다 — 스켈레톤 카드가 들어가 패널 높이가 그대로이므로
  답이 도착해도 지도 `fit` 이 다시 튀지 않는다. 스켈레톤은 `pointerEvents="none"`
  이라 그 위에서 시작한 팬도 지도에 닿는다.
- 4 에서 직전 결과는 화면에서 사라진다 — 답변 바는 새 질문을 이미 이름으로
  부르고 있는데 옛 카드가 남아 있으면 둘이 서로 다른 턴을 가리킨다.
- 11 의 `다시 시도` 는 실패한 **그 턴**을 재사용한다 — 질문·사진·`intent`·`patch`·
  `anchor`·`context` 를 그대로 다시 보내므로 턴이 늘어나지 않는다.
- 조건이 하나도 없는 질문은 검색하지 않는다 — `어디로 갈지 한 줄만 알려주세요…`
  한 줄과 초기 칩으로 끝난다.

---

관련: [ADR 0018](../adr/0018-travel-tab-answers-in-one-rising-panel.md) ·
[ADR 0017](../adr/0017-travel-tab-drops-the-sheet-for-a-map-carousel.md) ·
[ADR 0014](../adr/0014-travel-tab-answers-not-only-searches.md) ·
[ADR 0011](../adr/0011-travel-tab-chip-state-machine.md) ·
[api](api.md) · [여행 탭 QA](../how-to/qa-travel-tab.md) ·
[architecture](../explanation/architecture.md)
