# 여행 탭 채팅 시트 재구성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 여행 탭을 3단 스냅 바텀시트 채팅으로 재구성한다 — 대화 이력·2단계 후속 칩·엠프티 스테이트·연관 관광지 카드 포함 (프로토타입 `travel-sheet-proto.html` 확정 스펙).

**Architecture:** 지도 위에 `TravelSheet`(RN 내장 Animated, collapsed/mid/full 스냅) 하나가 대화 트랜스크립트 + 독을 담는다. 기존 `ResultPanel`/`AnswerBar`/패널 칩은 트랜스크립트 턴 렌더링과 `FollowUpChips` 2단계 흐름으로 대체된다. 정보 질문은 기존 agent `detail` 태스크, 근처 탐색은 기존 anchor 액션을 재사용하고, 연관 관광지만 백엔드에 anchor 액션 `"related"`(pgvector 임베딩 이웃)를 새로 만든다.

**Tech Stack:** Expo SDK 56 / RN 0.85 / React 19.2 / TS strict / Zustand / react-test-renderer(jest) · FastAPI / SQLAlchemy 2.0 async / pgvector / pytest

## Global Constraints

- 새 네이티브 모듈·라이브러리 추가 금지 (reanimated/bottom-sheet/blur 불가 — RN 내장 `Animated`·`Keyboard`만).
- 이모지 금지 — 아이콘은 line-SVG `<Icon>` 또는 `react-native-svg` 직접 사용.
- 코드 주석 금지 (도구가 요구하는 줄 제외).
- `src/app/**` 밖에 테스트 배치 (Expo Router가 라우트로 스캔).
- 테마 글로벌 토큰(`glassFill`/`raiseStrong`)은 변경하지 않는다 — 타 화면 14곳이 사용 중. 불투명은 시트 배경 `colors.inset`으로 달성한다.
- 모바일 에러 분기는 `err.code` 기준. API 응답은 JSend envelope.
- 백엔드 pytest: `POSTGRES_DB=pictrip_test NO_COLOR=1`.
- 커밋은 태스크마다 하지 않는다 — 마지막 태스크에서 유닛별(backend/mobile) 커밋 후 dev 대상 PR 1개 (사용자 메모리: no-intermediate-commits-single-pr). push/PR 생성 전 사용자 확인.
- 브랜치: `dev`에서 `feat/travel-chat-sheet` 분기. 최근 팀원(염준선)이 travel 키보드 커밋을 넣었으므로 머지 전 겹치는 열린 PR 확인 필수 (CLAUDE.md Workflow overlap 절차).

## 확정 스펙 (프로토타입 → 실제 매핑)

| 프로토타입 동작 | 실제 구현 |
|---|---|
| 시트 스냅 collapsed/mid(58%)/full(88%), 280ms | `Animated.timing` height, `sheet-layout.ts` 순수 함수 |
| 입력 포커스 → mid+키보드, 전송 → full, 답변 도착 → mid | travel.tsx 스냅 상태머신 |
| 지도 탭 → 대화 초기화+collapsed (busy 중엔 키보드만 닫기) | 지도 위 투명 Pressable |
| 대화 이력 전체 (유저 말풍선+답변+턴별 카루셀) | `ChatTranscript` |
| 후속 2단계: [근처 뭐 있어?]→[카페/맛집/볼거리], [여긴 어떤 곳이야?]→detail 질문 | `follow-ups.ts` + 기존 anchor/`detail` 태스크 |
| 정보 답변 후 남은 정보 질문 순환 제안 | `Turn.followKey`로 직전 질문 제외 |
| 연관 관광지는? → 텍스트+카드+핀 교체 | 백엔드 anchor `"related"` (임베딩 이웃) |
| 칩 동적 구성·중복 방지 (프로토타입엔 없던 확장) | `askedKeys` 이력 제외 + `categoryGroup` 제외 + `hasCrowd`·`refinements`·`suggestions`·detail 6필드 총동원, 최대 5개 캡 |
| 엠프티: 아바타 말풍선+예시 3타일+CTA 2개 | `EmptyGreeting`, 예시 탭 = 텍스트 질문 전송 |
| 초기 제안 칩은 시트 위 플로팅 | `ChipRow` 절대배치 재사용 |

확정 카피 (그대로 사용):
- 엠프티 말풍선: `어떤 분위기의 여행을 꿈꾸세요?\n사진 한 장 보여주시면, 그 분위기를 닮은 우리나라 여행지를 찾아드릴게요.` (강조: "그 분위기를 닮은 우리나라 여행지")
- 예시 캡션: `지금 사진이 없다면, 이런 분위기는 어때요?` / 타일: `바다 노을`·`감성 골목`·`숲길` → 질문 `바다 노을이 예쁜 여행지 알려줘`·`감성적인 골목길 여행지 알려줘`·`걷기 좋은 숲길 여행지 알려줘`
- CTA: `앨범에서 사진 고르기` / `카메라 촬영` (저장 안내 문구는 엠프티에 넣지 않음 — 첨부 배너가 담당)
- 후속 루트 문장: `{title} 근처의 카페·맛집·볼거리를 찾아드릴 수도 있고, 어떤 곳인지 더 알려드릴 수도 있어요.` 칩: `근처 뭐 있어?` `여긴 어떤 곳이야?` (+기존 refineChips)
- near 문장: `어떤 곳부터 찾아볼까요?` 칩: `카페`·`맛집`·`볼거리`·`‹ 뒤로`
- 정보 질문 칩: `여긴 어떤 곳이야?`→`{title}은 어떤 곳이야?` / `영업시간은?`→`{title} 영업시간 알려줘` / `연관 관광지는?`→anchor related. 정보 답변 뒤: `더 궁금한 게 있으세요?` + 남은 정보 칩 + `근처 뭐 있어?`

---

### Task 1: 시트 스냅 레이아웃 순수 함수

**Files:**
- Create: `mobile/src/features/travel/lib/sheet-layout.ts`
- Test: `mobile/src/features/travel/lib/__tests__/sheet-layout.test.ts`

**Interfaces:**
- Produces: `type SheetSnap = "collapsed" | "mid" | "full"`, `SHEET_ANIM_MS = 280`, `sheetHeightPx(input): number`, `sheetBottomPx(input): number`

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import {
  sheetHeightPx,
  sheetBottomPx,
  SHEET_ANIM_MS,
} from "@/features/travel/lib/sheet-layout";

const frame = { frameH: 844, insetTop: 59, insetBottom: 34 };

describe("sheet-layout", () => {
  it("collapsed는 독 높이만큼", () => {
    expect(
      sheetHeightPx({ ...frame, snap: "collapsed", keyboardPx: 0, dockPx: 72 }),
    ).toBe(72);
  });
  it("mid는 프레임의 58%", () => {
    expect(sheetHeightPx({ ...frame, snap: "mid", keyboardPx: 0, dockPx: 72 })).toBe(
      Math.round(844 * 0.58),
    );
  });
  it("full은 프레임의 88%", () => {
    expect(sheetHeightPx({ ...frame, snap: "full", keyboardPx: 0, dockPx: 72 })).toBe(
      Math.round(844 * 0.88),
    );
  });
  it("키보드가 있으면 남는 높이로 클램프", () => {
    expect(
      sheetHeightPx({ ...frame, snap: "full", keyboardPx: 336, dockPx: 72 }),
    ).toBe(844 - 336 - 59);
  });
  it("시트 bottom은 키보드 높이 (없으면 0)", () => {
    expect(sheetBottomPx({ keyboardPx: 0 })).toBe(0);
    expect(sheetBottomPx({ keyboardPx: 336 })).toBe(336);
  });
  it("애니메이션 길이 상수", () => {
    expect(SHEET_ANIM_MS).toBe(280);
  });
});
```

- [ ] **Step 2: 실패 확인** — `cd mobile && npx jest sheet-layout -t sheet` → FAIL (module not found)

- [ ] **Step 3: 구현**

```ts
export type SheetSnap = "collapsed" | "mid" | "full";

export const SHEET_ANIM_MS = 280;
export const SHEET_MID_RATIO = 0.58;
export const SHEET_FULL_RATIO = 0.88;

interface HeightInput {
  snap: SheetSnap;
  frameH: number;
  insetTop: number;
  insetBottom: number;
  keyboardPx: number;
  dockPx: number;
}

export function sheetHeightPx({
  snap,
  frameH,
  insetTop,
  keyboardPx,
  dockPx,
}: HeightInput): number {
  if (snap === "collapsed") return dockPx;
  const ratio = snap === "mid" ? SHEET_MID_RATIO : SHEET_FULL_RATIO;
  const wanted = Math.round(frameH * ratio);
  if (keyboardPx === 0) return wanted;
  return Math.min(wanted, frameH - keyboardPx - insetTop);
}

export function sheetBottomPx({ keyboardPx }: { keyboardPx: number }): number {
  return keyboardPx;
}
```

- [ ] **Step 4: 통과 확인** — `npx jest sheet-layout` → PASS

### Task 2: conversation-store에 followKey 추가

**Files:**
- Modify: `mobile/src/features/travel/stores/conversation-store.ts`
- Test: `mobile/src/features/travel/stores/__tests__/conversation-store.test.ts` (기존 파일에 케이스 추가)

**Interfaces:**
- Produces: `Turn.followKey?: FollowKey | null` (`type FollowKey = "about" | "hours" | "closed" | "parking" | "fee" | "related"` — `lib/follow-ups.ts`가 재선언하지 않도록 store에서 export), `start()` 입력에 `followKey?` 추가.

- [ ] **Step 1: 실패하는 테스트 추가** — 기존 테스트 파일 맨 아래:

```ts
it("start는 followKey를 보존한다", () => {
  const s = useConversation.getState();
  s.clear();
  s.start({ id: "t1", question: "영업시간은?", request: "", photo: null, followKey: "hours" });
  expect(useConversation.getState().turns[0].followKey).toBe("hours");
});

it("followKey를 안 주면 null", () => {
  const s = useConversation.getState();
  s.clear();
  s.start({ id: "t2", question: "q", request: "q", photo: null });
  expect(useConversation.getState().turns[0].followKey).toBeNull();
});
```

- [ ] **Step 2: 실패 확인** — `npx jest conversation-store` → FAIL
- [ ] **Step 3: 구현** — `export type FollowKey = "about" | "hours" | "related";` 추가, `Turn`에 `followKey: FollowKey | null`, `start` 입력 타입에 `followKey?: FollowKey | null`, 생성부에 `followKey = null` 기본값으로 저장.
- [ ] **Step 4: 통과 확인** — `npx jest conversation-store` → PASS. `npm run typecheck`.

### Task 3: follow-ups 상태머신 lib

**Files:**
- Create: `mobile/src/features/travel/lib/follow-ups.ts`
- Test: `mobile/src/features/travel/lib/__tests__/follow-ups.test.ts`

**Interfaces:**
- Consumes: `FollowKey`·`Turn` (store), `AnchorAction`·`Suggestion` (`api.ts`)
- Produces:

```ts
export type FollowBranch = "root" | "near";
export type FollowAction =
  | { kind: "branch"; to: FollowBranch }
  | { kind: "anchor"; action: AnchorAction; question: string }
  | { kind: "detail"; followKey: FollowKey; question: string }
  | { kind: "refine"; label: string; patch: RefinePatch }
  | { kind: "question"; question: string };
export interface FollowChip { label: string; action: FollowAction; muted?: boolean }
export interface FollowUpBlock { line: string; chips: FollowChip[] }
export const MAX_FOLLOW_CHIPS = 5;
export function askedKeys(turns: Turn[]): Set<string>;
export function followUps(input: {
  title: string;
  contentId: string | null;
  categoryGroup: string | null;
  hasCrowd: boolean;
  branch: FollowBranch;
  asked: ReadonlySet<string>;
  isDetailTurn: boolean;
  refinements: Suggestion[] | null;
  suggestions: string[] | null;
}): FollowUpBlock;
```

  `FollowKey`는 `"about" | "hours" | "closed" | "parking" | "fee" | "related"`로 확장한다 (Task 2에서 이 확장본으로 정의 — agent detail이 지원하는 필드: hours/closed/parking/contact/fee/overview 중 UI 가치가 있는 것).

**중복 방지·동적 구성 규칙 (구현·테스트의 기준):**

1. `askedKeys(turns)`: 각 턴에서 — `turn.anchor?.contentId` 있으면 `anchor:{action}:{contentId}`, `turn.followKey` 있으면 `detail:{followKey}:{turn.context?.focusContentId ?? ""}`, `turn.request`가 비지 않으면 `q:{request}`. 새 대화(clear)면 자동 초기화.
2. near 메뉴 옵션 [카페(cafe)·맛집(food)·볼거리(nearby)]에서 제외: (a) `anchor:{action}:{contentId}`가 asked에 있는 것, (b) 포커스 스팟의 `categoryGroup`이 그 옵션과 같은 것 — 카테고리→액션 매핑 상수는 백엔드 `agent/repositories.py:17 category_group()`의 실제 반환 문자열을 grep해서 작성 (예: 카페 계열 → `cafe`, 음식 계열 → `food`). 남은 옵션 뒤에 `hasCrowd && !asked`면 `지금 붐벼?`(anchor `crowd`), 마지막에 `‹ 뒤로`.
3. near 옵션이 (붐벼? 제외) 전부 제외되면 루트에서 `근처 뭐 있어?` 칩 자체를 숨긴다.
4. 루트의 정보 칩: `[about, hours, related, parking, fee]` 순서에서 **asked에 없는 첫 것 1개**만 노출 (라벨: `여긴 어떤 곳이야?`·`영업시간은?`·`연관 관광지는?`·`주차는 돼?`·`이용요금은?`).
5. 정보 답변 뒤(`isDetailTurn`): `더 궁금한 게 있으세요?` + asked에 없는 정보 칩 나열 + (near 살아있으면) `근처 뭐 있어?`.
6. 그 뒤에 `refinements`(kind refine), 그 뒤에 `suggestions`(kind question, `q:{text}`가 asked에 있으면 제외). 전체를 `MAX_FOLLOW_CHIPS`(5)로 자른다 (‹ 뒤로는 캡 계산에서 제외).

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import { askedKeys, followUps } from "@/features/travel/lib/follow-ups";

const base = {
  title: "동피랑 벽화마을",
  contentId: "c1",
  categoryGroup: null,
  hasCrowd: false,
  branch: "root" as const,
  asked: new Set<string>(),
  isDetailTurn: false,
  refinements: null,
  suggestions: null,
};

describe("followUps 루트", () => {
  it("안내 문장 + 근처/정보 칩", () => {
    const b = followUps(base);
    expect(b.line).toBe(
      "동피랑 벽화마을 근처의 카페·맛집·볼거리를 찾아드릴 수도 있고, 어떤 곳인지 더 알려드릴 수도 있어요.",
    );
    expect(b.chips.map((c) => c.label)).toEqual(["근처 뭐 있어?", "여긴 어떤 곳이야?"]);
    expect(b.chips[1].action).toEqual({
      kind: "detail",
      followKey: "about",
      question: "동피랑 벽화마을은 어떤 곳이야?",
    });
  });

  it("about을 이미 물었으면 다음 정보 칩(영업시간)으로 순환", () => {
    const b = followUps({ ...base, asked: new Set(["detail:about:c1"]) });
    expect(b.chips.map((c) => c.label)).toEqual(["근처 뭐 있어?", "영업시간은?"]);
  });

  it("refinements와 suggestions가 뒤에 붙고 5개로 캡", () => {
    const b = followUps({
      ...base,
      refinements: [
        { label: "조용한 곳만", patch: { crowdPreference: "quiet" } },
        { label: "실내만", patch: { indoorOnly: true } },
      ],
      suggestions: ["야경 좋은 곳도 볼래?", "비 오는 날 코스는?"],
    });
    expect(b.chips.map((c) => c.label)).toEqual([
      "근처 뭐 있어?",
      "여긴 어떤 곳이야?",
      "조용한 곳만",
      "실내만",
      "야경 좋은 곳도 볼래?",
    ]);
    expect(b.chips[4].action).toEqual({ kind: "question", question: "야경 좋은 곳도 볼래?" });
  });

  it("이미 물은 suggestion은 제외", () => {
    const b = followUps({
      ...base,
      suggestions: ["야경 좋은 곳도 볼래?"],
      asked: new Set(["q:야경 좋은 곳도 볼래?"]),
    });
    expect(b.chips.map((c) => c.label)).not.toContain("야경 좋은 곳도 볼래?");
  });
});

describe("followUps near 분기 — 중복 방지", () => {
  it("기본: 카페/맛집/볼거리 + 뒤로", () => {
    const b = followUps({ ...base, branch: "near" });
    expect(b.line).toBe("어떤 곳부터 찾아볼까요?");
    expect(b.chips.map((c) => c.label)).toEqual(["카페", "맛집", "볼거리", "‹ 뒤로"]);
    expect(b.chips[0].action).toEqual({
      kind: "anchor",
      action: "cafe",
      question: "동피랑 벽화마을 근처 카페",
    });
  });

  it("이미 물은 앵커(카페)는 빠진다", () => {
    const b = followUps({ ...base, branch: "near", asked: new Set(["anchor:cafe:c1"]) });
    expect(b.chips.map((c) => c.label)).toEqual(["맛집", "볼거리", "‹ 뒤로"]);
  });

  it("포커스 스팟이 카페면 근처 카페를 제안하지 않는다", () => {
    const b = followUps({ ...base, branch: "near", categoryGroup: CAFE_CATEGORY_GROUP });
    expect(b.chips.map((c) => c.label)).not.toContain("카페");
  });

  it("hasCrowd면 지금 붐벼? 칩이 붙는다 (crowd anchor)", () => {
    const b = followUps({ ...base, branch: "near", hasCrowd: true });
    expect(b.chips.map((c) => c.label)).toContain("지금 붐벼?");
  });

  it("전부 물었으면 루트에서 근처 뭐 있어?가 사라진다", () => {
    const b = followUps({
      ...base,
      asked: new Set(["anchor:cafe:c1", "anchor:food:c1", "anchor:nearby:c1"]),
    });
    expect(b.chips.map((c) => c.label)).not.toContain("근처 뭐 있어?");
  });
});

describe("정보 답변 뒤", () => {
  it("남은 정보 칩 + 근처 칩, 물은 건 제외", () => {
    const b = followUps({
      ...base,
      isDetailTurn: true,
      asked: new Set(["detail:about:c1", "detail:hours:c1"]),
    });
    expect(b.line).toBe("더 궁금한 게 있으세요?");
    expect(b.chips.map((c) => c.label)).toEqual([
      "연관 관광지는?",
      "주차는 돼?",
      "이용요금은?",
      "근처 뭐 있어?",
    ]);
    expect(b.chips[0].action).toEqual({
      kind: "anchor",
      action: "related",
      question: "동피랑 벽화마을 연관 관광지는?",
    });
  });
});

describe("askedKeys", () => {
  it("앵커·detail·질문 턴에서 키를 뽑는다", () => {
    const keys = askedKeys([
      { ...turnBase, anchor: { contentId: "c1", action: "cafe" } },
      { ...turnBase, followKey: "hours", context: { spots: [], focusContentId: "c1" } },
      { ...turnBase, request: "야경 좋은 곳도 볼래?" },
    ] as Turn[]);
    expect(keys.has("anchor:cafe:c1")).toBe(true);
    expect(keys.has("detail:hours:c1")).toBe(true);
    expect(keys.has("q:야경 좋은 곳도 볼래?")).toBe(true);
  });
});
```

  `CAFE_CATEGORY_GROUP`·`turnBase`는 테스트 상단에서 정의 — `CAFE_CATEGORY_GROUP`은 백엔드 `category_group()`이 카페 계열에 실제로 반환하는 문자열을 grep해서 채운다 (`backend/app/modules/agent/repositories.py:17` 부근).

- [ ] **Step 2: 실패 확인** — `npx jest follow-ups` → FAIL
- [ ] **Step 3: 구현** — 위 "중복 방지·동적 구성 규칙" 6개 항목과 테스트 문자열 그대로. 정보 칩 순서 고정 배열: about(`{t}은 어떤 곳이야?`) → hours(`{t} 영업시간 알려줘`) → related(anchor) → parking(`{t} 주차 돼?` 라벨 `주차는 돼?`) → fee(`{t} 이용요금 알려줘` 라벨 `이용요금은?`). `related`는 `FollowKey`지만 액션은 anchor(`action:"related"`).
- [ ] **Step 4: 통과 확인** — `npx jest follow-ups` → PASS. 참고: `api.ts`의 `AnchorAction`에 `"related"`가 아직 없으므로 이 태스크에서 `export type AnchorAction = "food" | "cafe" | "nearby" | "crowd" | "related";`로 함께 넓힌다 (백엔드는 Task 8).

### Task 4: TravelSheet 컴포넌트

**Files:**
- Create: `mobile/src/features/travel/components/TravelSheet.tsx`
- Test: `mobile/src/features/travel/components/__tests__/TravelSheet.test.tsx`

**Interfaces:**
- Consumes: `sheetHeightPx`/`sheetBottomPx`/`SHEET_ANIM_MS` (Task 1)
- Produces:

```tsx
interface Props {
  snap: SheetSnap;
  keyboardPx: number;
  dockPx: number;
  onGrabberTap: () => void;
  children: ReactNode;
}
export function TravelSheet(props: Props): JSX.Element
```

  testID `travel-sheet` 루트(절대배치 left/right 0, 배경 `colors.inset`, 상단 radius 22, `shadows.sheet`, 위쪽 `colors.glassBorder` 1px), testID `travel-sheet-grabber` (collapsed에선 미렌더), 내용은 children 그대로.

- [ ] **Step 1: 실패하는 테스트 작성** — TravelDock.test.tsx의 `mount`/`byId` 헬퍼 패턴을 복사해 사용:

```tsx
it("collapsed에서는 그래버가 없다", () => {
  const tree = mount({ snap: "collapsed" });
  expect(byId(tree, "travel-sheet-grabber")).toHaveLength(0);
});

it("mid에서는 그래버가 있고 탭하면 onGrabberTap", () => {
  const onGrabberTap = jest.fn();
  const tree = mount({ snap: "mid", onGrabberTap });
  const grabber = byId(tree, "travel-sheet-grabber")[0];
  act(() => grabber.props.onPress());
  expect(onGrabberTap).toHaveBeenCalled();
});

it("루트는 travel-sheet testID와 시트 스타일을 가진다", () => {
  const tree = mount({ snap: "mid" });
  expect(byId(tree, "travel-sheet").length).toBeGreaterThan(0);
});
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현** — `useRef(new Animated.Value(초기 height))` + `useEffect`로 `snap/keyboardPx` 변화 시 `Animated.timing(height, { toValue: sheetHeightPx(...), duration: SHEET_ANIM_MS, useNativeDriver: false })` + bottom도 동일 패턴. `frameH`는 `useWindowDimensions().height`, insets는 `useSafeAreaInsets`. 그래버는 `snap !== "collapsed"`일 때 `Pressable`(높이 20, 중앙 44×5 pill `colors.fillStrong`).
- [ ] **Step 4: 통과 확인** — `npx jest TravelSheet` → PASS

### Task 5: ChatTranscript (대화 이력 + 턴 렌더링, AnswerBar 대체)

**Files:**
- Create: `mobile/src/features/travel/components/ChatTranscript.tsx`
- Delete: `mobile/src/features/travel/components/AnswerBar.tsx`, `.../__tests__/AnswerBar.test.tsx`
- Test: `mobile/src/features/travel/components/__tests__/ChatTranscript.test.tsx`

**Interfaces:**
- Consumes: `Turn`(store), `splitAnswer`(`lib/answer-split.ts`), `pendingSteps`(`lib/pending-steps.ts`), `SpotCarousel`, `FollowUpBlock`(Task 3)
- Produces:

```tsx
interface Props {
  turns: Turn[];
  focusedIndex: number;
  scrollToIndex: number | null;
  origin: LatLng | null;
  followUp: FollowUpBlock | null;
  busy: boolean;
  onFollowChip: (chip: FollowChip) => void;
  onFocusChange: (index: number) => void;
  onDetail: (spot: TravelSpot) => void;
  onSaveToggle: (saved: boolean) => void;
  onMetricPress: (tooltip: string) => void;
  onRetry: () => void;
}
export function ChatTranscript(props: Props): JSX.Element
```

- [ ] **Step 1: 실패하는 테스트 작성** — 핵심 케이스만 실코드로:

```tsx
const doneTurn: Turn = {
  id: "t1", question: "바다 보이는 카페", request: "바다 보이는 카페",
  photo: null, intent: null, patch: null, anchor: null, context: null,
  followKey: null, status: "done",
  answer: { steps: [], answer: [{ text: "이 근처가 좋아요", emphasis: false }],
    spots: [spot], totalCount: 1, intent: {} as QueryIntent, suggestions: [] },
  errorMessage: null,
};

it("유저 말풍선과 답변 텍스트를 함께 렌더한다", () => {
  const tree = mount({ turns: [doneTurn] });
  expect(texts(tree)).toContain("바다 보이는 카페");
  expect(texts(tree)).toContain("이 근처가 좋아요");
});

it("pending 턴은 스텝 라벨을 보여준다", () => {
  const tree = mount({ turns: [{ ...doneTurn, status: "pending", answer: null }] });
  expect(byId(tree, "travel-turn-step").length).toBeGreaterThan(0);
});

it("failed 턴은 재시도 버튼을 보여준다", () => {
  const tree = mount({
    turns: [{ ...doneTurn, status: "failed", answer: null, errorMessage: "네트워크 오류" }],
  });
  const retry = byId(tree, "travel-retry")[0];
  act(() => retry.props.onPress());
  expect(base.onRetry).toHaveBeenCalled();
});

it("마지막 done 턴 아래에 followUp 문장과 칩을 렌더한다", () => {
  const tree = mount({
    turns: [doneTurn],
    followUp: { line: "어떤 곳부터 찾아볼까요?", chips: [{ label: "카페", action: { kind: "branch", to: "near" } }] },
  });
  expect(texts(tree)).toContain("어떤 곳부터 찾아볼까요?");
  act(() => byId(tree, "travel-follow-0")[0].props.onPress());
  expect(base.onFollowChip).toHaveBeenCalled();
});

it("스팟이 없는 done 턴(detail)은 카루셀을 렌더하지 않는다", () => {
  const tree = mount({
    turns: [{ ...doneTurn, answer: { ...doneTurn.answer!, spots: [], totalCount: 0 } }],
  });
  expect(byId(tree, "travel-carousel-slot")).toHaveLength(0);
});
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현** — `ScrollView`(ref, `onContentSizeChange`에서 `scrollToEnd({animated:true})`) 안에 턴 목록. 턴 렌더: 우측 정렬 말풍선(`colors.fillStrong` bg, radius 16/16/4/16, 사진 있으면 40px 썸네일) → 상태별: pending = 기존 AnswerBar의 spinner+step row 이식 (testID `travel-turn-step`), failed = `FAIL_TITLE`("답변을 못 받았어요")+메시지+`travel-retry` 버튼 이식, done = `splitAnswer` lead(14.5 bold)+rest(13 sec) 풀 텍스트(트랜스크립트는 스크롤이므로 접기 불필요 — `expandedAnswer` 개념 삭제) → `spots.length > 0`이면 `travel-carousel-slot` View + `SpotCarousel`(마지막 턴만 `focusedIndex`/`scrollToIndex`/`onFocusChange` 연결, 이전 턴은 focusedIndex 0 고정·no-op 콜백) → 마지막 턴이 done이고 `followUp`이 있으면 문장(13px `colors.sec`) + 칩 행(`travel-follow-{i}` testID, `muted`면 회색 스타일, `busy`면 disabled).
- [ ] **Step 4: 통과 확인** — `npx jest ChatTranscript` → PASS

### Task 6: EmptyGreeting + 플로팅 초기 칩

**Files:**
- Create: `mobile/src/features/travel/components/EmptyGreeting.tsx`
- Create: `mobile/src/features/travel/components/TravelerAvatar.tsx`
- Test: `mobile/src/features/travel/components/__tests__/EmptyGreeting.test.tsx`

**Interfaces:**
- Produces:

```tsx
export const GREETING_LINE1 = "어떤 분위기의 여행을 꿈꾸세요?";
export const GREETING_LINE2 =
  "사진 한 장 보여주시면, 그 분위기를 닮은 우리나라 여행지를 찾아드릴게요.";
export const SAMPLES_CAPTION = "지금 사진이 없다면, 이런 분위기는 어때요?";
export const SAMPLE_MOODS: { label: string; question: string }[] = [
  { label: "바다 노을", question: "바다 노을이 예쁜 여행지 알려줘" },
  { label: "감성 골목", question: "감성적인 골목길 여행지 알려줘" },
  { label: "숲길", question: "걷기 좋은 숲길 여행지 알려줘" },
];
interface Props {
  onSample: (question: string) => void;
  onAlbum: () => void;
  onShoot: () => void;
}
export function EmptyGreeting(props: Props): JSX.Element
```

  `TravelerAvatar`: `react-native-svg`로 32px 원형 배경(`colors.fillStrong`) 안 스틱피겨 (Circle cx12 cy6.5 r3.6 + Path M12 10.5V16 / M12 12.5L7.5 15 / M12 12.5L16.5 15 / M12 16L9 21 / M12 16L15 21, stroke `colors.ink`, strokeWidth 1.9, strokeLinecap round, viewBox 0 0 24 24).

- [ ] **Step 1: 실패하는 테스트 작성**

```tsx
it("인사 카피와 캡션을 렌더한다", () => {
  const tree = mount();
  expect(texts(tree)).toContain(GREETING_LINE1);
  expect(texts(tree)).toContain(SAMPLES_CAPTION);
});

it("예시 타일 탭은 해당 질문으로 onSample", () => {
  const tree = mount();
  act(() => byId(tree, "travel-sample-0")[0].props.onPress());
  expect(base.onSample).toHaveBeenCalledWith("바다 노을이 예쁜 여행지 알려줘");
});

it("앨범/촬영 CTA", () => {
  const tree = mount();
  act(() => byId(tree, "travel-empty-album")[0].props.onPress());
  act(() => byId(tree, "travel-empty-shoot")[0].props.onPress());
  expect(base.onAlbum).toHaveBeenCalled();
  expect(base.onShoot).toHaveBeenCalled();
});
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현** — 좌측 아바타+말풍선(bg `colors.fill`, border `colors.line`, radius 4/16/16/16, LINE2의 "그 분위기를 닮은 우리나라 여행지"는 `colors.accentText` span), 캡션(12px `colors.ter`), 타일 3개 flex-row 높이 76 radius 12 — 배경은 `expo-image` 없이 `LinearGradient` 불가(모듈 금지)이므로 단색 3종(`#C74B50`/`#3B4664`/`#1E5E58`) View + 좌하단 라벨(11px 800 white). CTA: primary(`colors.accent` bg, `colors.onImage` 글자) / ghost(`colors.fill` bg + border) 높이 46 radius 13.
- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: 플로팅 칩** — 별도 컴포넌트 불필요: travel.tsx(Task 7)에서 대화 없음+collapsed일 때 `ChipRow`를 시트 위 `position:absolute`(`bottom: dockPx + 10`)로 렌더. 이 태스크에서는 `ChipRow`가 불투명 배경이 필요함만 처리: `ChipRow`에 `opaque?: boolean` prop 추가 → 칩 bg를 `colors.raiseStrong` 대신 `colors.inset`으로. 기존 ChipRow 테스트에 opaque 케이스 1개 추가.

### Task 7: travel.tsx 통합 (시트 상태머신)

**Files:**
- Modify: `mobile/src/app/(tabs)/travel.tsx` (전면 재구성)
- Modify: `mobile/src/features/travel/components/TravelDock.tsx` (bottom prop 제거 — 시트 내부 배치로 전환, 독 내부 칩 행 제거)
- Delete: `mobile/src/features/travel/components/ResultPanel.tsx` + 관련 테스트
- Modify: `mobile/src/features/travel/lib/dock-chips.ts` (`panelChips` 삭제, `dockChips`만 유지) + `lib/chips.ts` (`contextChips` 삭제) + 두 테스트 파일 정리
- Modify: `mobile/src/features/travel/lib/screen-layout.ts` (`panelBasePx`·`PANEL_*` 상수 삭제, `dockBasePx`의 chips 인자 삭제)

**Interfaces:**
- Consumes: Task 1~6 전부.
- Produces: 화면 상태 — `const [snap, setSnap] = useState<SheetSnap>("collapsed")`, `const [branch, setBranch] = useState<FollowBranch>("root")`.

- [ ] **Step 1: 상태머신 연결** (동작 스펙 — 코드는 기존 콜백 구조 유지하며 삽입)
  - 입력 `onFocus`: `snap === "collapsed"`면 `setSnap("mid")` (TravelDock의 TextInput onFocus prop 복원 필요).
  - `submit`/anchor/intent/refine/detail 모든 전송 직전: `setSnap("full")`, `setBranch("root")`.
  - `resolveTurn` 성공 콜백: `setSnap("mid")`.
  - 그래버 탭: `setSnap(snap === "full" ? "mid" : "full")`.
  - 지도 탭(지도 위 투명 `Pressable`, testID `travel-map-dismiss`): `Keyboard.dismiss()`; `busy`가 아니면 `onNewChat()` + `setSnap("collapsed")`.
  - seeded(상세에서 진입) 시: `setSnap("mid")`.
- [ ] **Step 2: 후속 칩 배선** — `const asked = useMemo(() => askedKeys(turns), [turns])`; `followUp = lastTurn?.status === "done" ? followUps({ title: focused?.title ?? MY_LOCATION, contentId: focused?.contentId ?? null, categoryGroup: focused?.categoryGroup ?? null, hasCrowd: focused?.hasCrowd === true, branch, asked, isDetailTurn: answer !== null && answer.spots.length === 0, refinements: answer?.refinements ?? null, suggestions: answer?.suggestions ?? null }) : null`. `onFollowChip`: `branch` → `setBranch(to)`; `anchor` → 기존 anchor 전송 경로 재사용하되 `question`을 말풍선 문구로 (crowd·related 포함); `detail` → `submit(question)` 경로에 `followKey` 전달(`startTurn({ ..., followKey })` — context에 `focusContentId` 포함되도록 기존 `contextFrom` 유지); `refine` → 기존 refine 전송 경로; `question` → `submit(question, null)`. 포커스 스팟이 바뀌면 `setBranch("root")`(기존 `onFocusChange`에 추가).
- [ ] **Step 3: 렌더 트리 교체**

```tsx
<View style={styles.root}>
  <KakaoWebMap ... />
  <Pressable testID="travel-map-dismiss" style={StyleSheet.absoluteFill} onPress={onMapTap} />
  <SearchPulse active={busy} bottom={sheetPx} />
  {idleChipsShown ? <ChipRow chips={dockChips()} opaque ... /> : null}
  <TravelSheet snap={snap} keyboardPx={keyboardPx} dockPx={dockPx} onGrabberTap={onGrabberTap}>
    {turns.length === 0 && snap !== "collapsed" ? (
      <EmptyGreeting onSample={(q) => submit(q, null)} onAlbum={...pick} onShoot={...shoot} />
    ) : (
      <ChatTranscript turns={turns} followUp={followUp} ... />
    )}
    <TravelDock ... />
  </TravelSheet>
  <Toast ... bottom={sheetPx + TOAST_LIFT} />
</View>
```

  `sheetPx = sheetHeightPx(...) + keyboardPx` (지도 fit padding·SearchPulse·Toast 공용). `panelPx` 측정 로직(`onPanelHeight`)과 `expandedAnswer` state 삭제. 지도 탭 Pressable은 지도 위·시트 아래 z순서(시트가 나중에 렌더되므로 자연 충족). 핀 탭이 죽지 않도록 `KakaoWebMap` 위 Pressable 대신 **시트 밖 영역 전체를 덮지 않는** 방식 확인 — KakaoWebMap은 WebView라 자체 터치를 소비하므로 dismiss Pressable은 `pointerEvents` 검증 후 필요 시 WebView `onTouchStart` 콜백으로 대체 (기존 `onPinTap` 유지 필수).
- [ ] **Step 4: 검증** — `npm run lint && npm run typecheck && npm test` 전부 통과. 삭제된 export를 참조하는 테스트(ResultPanel/AnswerBar/dock-chips/screen-layout) 정리 완료 확인.
- [ ] **Step 5: 실기기 확인** — `npx expo start` → iOS 시뮬레이터에서: 초기 칩 플로팅 / 입력 포커스 시 시트+키보드 상승·입력창 가림 없음 / 전송→full→답변→mid / 그래버 토글 / 지도 탭 리셋 / 후속 2단계 / 연관 관광지(백엔드 Task 8 배포 전이면 이 칩만 에러 토스트 확인) / 사진 첨부 배너.

### Task 8: 백엔드 anchor `"related"` (임베딩 이웃)

**Files:**
- Modify: `backend/app/modules/agent/schemas.py:12` (`AnchorAction`에 `"related"`)
- Modify: `backend/app/modules/agent/services/ask.py` (`_ask_with_anchor` 분기)
- Modify: `backend/app/modules/agent/repositories.py` (`load_spot_embedding` 추가)
- Test: 기존 agent anchor 테스트 파일(`backend/tests/`에서 `anchor`로 grep해 같은 파일에 추가)

**Interfaces:**
- Consumes: `repositories.match_spots_by_vector(session, vector, ...)` (기존), `spot_embeddings.embedding halfvec(512)`
- Produces: `POST /agent/ask` body `{"anchor": {"contentId": "...", "action": "related"}}` → `AskResponse(spots=유사 스팟 카드, answer="「{title}」과 분위기가 비슷한 곳이에요...", tagBasis="분위기 유사도 기준")`

- [ ] **Step 1: 실패하는 테스트 작성** — 기존 anchor 테스트(cafe/food)의 픽스처 패턴을 그대로 복사해 `related` 케이스 작성: 앵커 스팟+임베딩 시드 → 응답 200, `data.spots`에 앵커 자신 미포함, `data.tagBasis == "분위기 유사도 기준"`. `contentId` 없이 `related` 호출 시 422/`VALIDATION_FAILED` 케이스도 추가.
- [ ] **Step 2: 실패 확인** — `cd backend && POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests -k related -x` → FAIL
- [ ] **Step 3: 구현**

```python
async def load_spot_embedding(session: AsyncSession, content_id: str) -> list[float] | None:
    row = await session.execute(
        text("SELECT embedding::text FROM spot_embeddings WHERE content_id = :cid"),
        {"cid": content_id},
    )
    raw = row.scalar_one_or_none()
    if raw is None:
        return None
    return [float(v) for v in raw.strip("[]").split(",")]
```

  `_ask_with_anchor`의 `crowd` 분기 아래에:

```python
if anchor.action == "related":
    if row is None:
        raise ValidationFailed("related anchor requires contentId")
    vector = await repositories.load_spot_embedding(session, anchor.contentId)
    if vector is None:
        raise AgentNoResults()
    matches = await repositories.match_spots_by_vector(session, vector, ...)  # 기존 시그니처 확인 후 self 제외, RESULT_LIMIT 적용
    ...
    answer = [
        AnswerSegment(text=f"「{row.title}」"),
        AnswerSegment(text="과 분위기가 비슷한 곳으로 "),
        AnswerSegment(text=f"{len(spots)}곳 찾았어요."),
    ]
    return AskResponse(steps=[AskStep(tool="related", label=f"{row.title} 연관 관광지 조회", badge=f"{len(spots)}곳")], answer=answer, spots=spots, totalCount=len(spots), intent=QueryIntent(), tagBasis="분위기 유사도 기준", refinements=[])
```

  구현 시 `match_spots_by_vector`의 실제 시그니처·카드 변환(`retrieve.to_card`)에 맞춰 조정하고, 유사도 태그는 기존 `_ask_card`의 `유사도 N%` 포맷 재사용.
- [ ] **Step 4: 통과 확인** — pytest -k related PASS 후 전체 게이트: `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports && POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest`

### Task 9: 스펙 자기검토 + 최종 게이트

- [ ] mobile 전체: `npm run lint && npm run typecheck && npm run format:check && npm test`
- [ ] backend 전체 게이트 (Task 8 Step 4와 동일 명령) 재확인
- [ ] 확정 스펙 표를 훑으며 각 행이 실제 화면에서 동작하는지 시뮬레이터로 최종 확인 (superpowers:verification-before-completion)
- [ ] 프로토타입 산출물은 리포에 넣지 않는다 (scratchpad에 그대로 두고 폐기 — CLAUDE.md 규칙)

### Task 10: 커밋 + PR (사용자 확인 후)

- [ ] 사용자에게 커밋·푸시 승인 요청 (CLAUDE.md: commit/push only when asked)
- [ ] 커밋 2개: `feat(backend): 연관 관광지 anchor 를 임베딩 이웃으로 답한다` / `feat(travel): 여행 탭을 바텀시트 채팅으로 재구성한다`
- [ ] PR → dev, 본문은 `.github/pull_request_template.md` 4섹션(요약/변경 단위/핵심 결정/검증, 체크박스 ≥1) — HDA 스타일 불릿, Claude 푸터 금지
- [ ] 머지 전 겹치는 열린 PR 확인: `gh pr list --state open --base dev` + pr-check overlap job summary (travel 파일을 만진 팀원 커밋이 최근에 있었음 — 충돌 순서 조정)
