# 여행 탭 지도 우선 개편 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 여행 탭의 3단 글래스 시트를 걷어내고, 지도를 상시 주인공으로 두고 결과를 지도 위 좌우 캐러셀로 그린다.

**Architecture:** 화면은 3층 고정이다 — 상단 답변 바(질문 라벨 + 답변 헤드라인), 중간 결과 캐러셀, 하단 독(칩 행 + 입력 필드). 시트·스냅·드래그·대화 이력·앵커 모드가 전부 사라지고 화면에는 마지막 턴 하나만 존재한다. 백엔드는 답변 문장의 순서만 뒤집는다(구체적 사실 → 개수).

**Tech Stack:** Expo SDK 56 · RN 0.85 · React 19.2 · TypeScript strict · Zustand · jest-expo / react-test-renderer · FastAPI · pytest

**Spec:** `docs/superpowers/specs/2026-08-08-travel-tab-map-first-design.md`

## Global Constraints

- **코드에 주석을 달지 않는다.** 의도는 이름·구조로 드러낸다 (CLAUDE.md 금지 조항).
- **이모지·신규 네이티브 모듈 금지.** 아이콘은 `@/components/Icon` 의 라인 SVG 만 쓴다.
- **중간 커밋을 하지 않는다.** 각 태스크는 검증까지만 하고, 마지막 태스크에서 브랜치 한 번 커밋 + PR 하나를 연다.
- 모바일 검증 4종: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`
- 백엔드 검증: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest`, 그리고 `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports`
- 모바일 테스트는 `src/app/**` 밖에 둔다 (Expo Router 가 라우트로 스캔한다).
- 색·간격은 `@/constants/theme` 의 토큰만 쓴다. 하드코딩 금지 (반투명 accent 파생색은 예외).
- 백엔드 `routes.py` 는 DB/models/sqlalchemy 를 임포트하지 않는다.
- 브랜치: `dev` 에서 잘라 `feat/travel-map-first`.

### 확정 수치 (프로토타입 기준)

| 요소 | 값 |
|---|---|
| 카드 | 296×112, radius 18, `glassFill` + 1px `glassBorder`, 카드 간 gap 10 |
| 캐러셀 스냅 간격 | 306 (카드 296 + gap 10) |
| 썸네일 | 92×92, radius 12 |
| 번호 배지 | 20px 원형, 흰 배경 + `#0C0E11` 숫자 |
| 진행 바 | 높이 3, 좌우 마진 4, 아래 여백 11, 최소 폭 14 |
| 칩 | 높이 33, radius pill, 행 간 여백 9 |
| 필드 | 높이 46, radius 13 |
| 답변 바 | `top: insets.top + 7`, 좌우 14, radius 16, 접힘 2줄 clamp |
| 독 하단 | 탭바(49 + `insets.bottom`) 바로 위, 아래 패딩 12 |

---

## File Structure

**신규 (mobile)**

| 경로 | 책임 |
|---|---|
| `src/features/travel/lib/answer-split.ts` | `AnswerPart[]` 를 헤드라인/보충으로 가른다 |
| `src/features/travel/lib/metric.ts` | `tag` + `tagBasis` → 성질 칩 `{icon, label, tooltip}`, 거리 태그 판별 |
| `src/features/travel/lib/dock-chips.ts` | 독 칩 모델 — 고정 사진 칩 · 문맥 칩 · 펼침 상태 |
| `src/features/travel/components/AnswerBar.tsx` | 질문 라벨 + 답변 헤드라인 + 펼침 + 진행/실패 |
| `src/features/travel/components/SpotCard.tsx` | 카드 한 장 |
| `src/features/travel/components/SpotCarousel.tsx` | 가로 스냅 캐러셀 + 진행 바 + 포커스 인덱스 통지 |
| `src/features/travel/components/TravelDock.tsx` | 칩 행 + 입력 필드 (+ 첨부 배너 · 위치 프라이머) |

**폐기 (mobile)** — `StartActions.tsx` · `Mascot.tsx` · `AnchorPreview.tsx` · `PhotoCompare.tsx` · `StepList.tsx` · `ConversationTurn.tsx` · `AnswerBlock.tsx` · `ResultRow.tsx` · `AskComposer.tsx` · `hooks/use-card-tap.ts` · `lib/sheet-snap.ts` · `stores/anchor-store.ts` 와 각각의 테스트.

**수정** — `src/app/(tabs)/travel.tsx` (전면 재작성) · `src/features/travel/lib/chips.ts` · `backend/app/modules/agent/services/ask.py`

**유지** — `lib/question.ts` · `lib/conversation-context.ts` · `lib/distance.ts` · `lib/spot-geo.ts` · `lib/agent-errors.ts` · `lib/pending-steps.ts` · `stores/conversation-store.ts` · `hooks/use-nearby-coords.ts` · `usecases/pick-travel-photo.ts` · `components/SearchPulse.tsx` · `components/GlassSheet.tsx`(지도 탭이 쓴다)

---

### Task 1: 백엔드 — 검색 답변의 순서를 뒤집는다

**Files:**
- Modify: `backend/app/modules/agent/services/ask.py:1165-1203`
- Test: `backend/tests/test_agent_ask.py:128-162`

**Interfaces:**
- Consumes: 없음
- Produces: `_answer(top, *, intent, near, lat, lng, region_widened=None) -> list[AnswerSegment]` — 시그니처 불변. 첫 문장이 구체적 사실, 둘째 문장이 조건 + 개수.

- [ ] **Step 1: 기존 세 테스트를 새 순서로 다시 쓴다**

`backend/tests/test_agent_ask.py` 의 `test_answer_emphasises_the_result_count` ·
`test_an_answer_names_the_conditions_it_searched` ·
`test_an_answer_with_no_nameable_condition_keeps_the_plain_opening` 을 통째로 아래로 교체한다.

```python
def test_a_quiet_answer_leads_with_the_percentile_not_the_count() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(crowdPreference="quiet"),
        near=False,
        lat=None,
        lng=None,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("혼잡도 ")
    assert "안쪽으로만 골랐어요." in text
    assert "4곳" in text
    assert [s.text for s in segments if s.emphasis][0].startswith("하위 ")


def test_a_near_answer_leads_with_the_closest_distance() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(nearMe=True),
        near=True,
        lat=35.0,
        lng=128.0,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("가장 가까운 곳이 ")
    assert "km예요." in text


def test_an_answer_with_no_specific_fact_leads_with_the_conditions() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(regionHints=["통영"], categoryKeywords=["계곡"]),
        near=False,
        lat=None,
        lng=None,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("통영 + 계곡 조건으로 4곳이에요.")


def test_an_answer_with_nothing_nameable_keeps_the_plain_opening() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(namedPlaces=[ExtractedPlace(name="감천문화마을")]),
        near=False,
        lat=None,
        lng=None,
    )

    assert "".join(s.text for s in segments).startswith("조건에 맞는 곳으로 4곳이에요.")


def test_a_widened_answer_leads_with_the_region_it_widened_to() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(regionHints=["수영"]),
        near=False,
        lat=None,
        lng=None,
        region_widened=retrieve.RegionScope(
            narrowed_label="수영구", widened_label="부산광역시", prefixes=["부산광역시"]
        ),
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("수영구 안에서는 찾지 못해 부산광역시 전체에서 골랐어요.")
    assert "4곳" in text


def test_an_answer_never_emphasises_a_bare_count() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(crowdPreference="quiet"),
        near=False,
        lat=None,
        lng=None,
    )

    assert "4곳" not in [s.text for s in segments if s.emphasis]
```

`retrieve.RegionScope` 의 실제 필드명이 다르면 그 파일을 열어 맞춘다
(`backend/app/modules/agent/services/retrieve.py`). import 는 이미 파일 상단에 있는
`from app.modules.agent.services import retrieve` 를 쓴다 — 없으면 추가한다.

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -k "answer" -v
```

Expected: FAIL — 현재 문장은 `"통영 + 계곡 조건으로 4곳 추렸어요"` 로 시작한다.

- [ ] **Step 3: `_answer` 를 헤드라인 + 보충으로 다시 짠다**

`ask.py:1172-1203` 의 `_answer` 를 통째로 교체하고 헬퍼 둘을 바로 위에 둔다.
`_answer_opening` 은 그대로 두고 `_scope_sentence` 가 그것을 쓴다.

```python
def _scope_sentence(top: list[CandidateRow], *, intent: QueryIntent) -> list[AnswerSegment]:
    return [
        AnswerSegment(text=_answer_opening(intent)),
        AnswerSegment(text=f"{len(top)}곳이에요."),
    ]


def _lead_sentence(
    top: list[CandidateRow],
    *,
    intent: QueryIntent,
    near: bool,
    lat: float | None,
    lng: float | None,
    region_widened: retrieve.RegionScope | None,
) -> list[AnswerSegment]:
    if region_widened is not None:
        return [
            AnswerSegment(text=f"{region_widened.narrowed_label} 안에서는 찾지 못해 "),
            AnswerSegment(text=region_widened.widened_label, emphasis=True),
            AnswerSegment(text=" 전체에서 골랐어요."),
        ]
    if intent.crowdPreference == "quiet":
        pcts = [row.percentile for row in top if row.percentile is not None]
        if pcts:
            return [
                AnswerSegment(text="혼잡도 "),
                AnswerSegment(text=f"하위 {max(pcts)}%", emphasis=True),
                AnswerSegment(text=" 안쪽으로만 골랐어요."),
            ]
    if near and lat is not None and lng is not None:
        kms = [km for row in top if (km := retrieve.distance_km(row, lat=lat, lng=lng)) is not None]
        if kms:
            return [
                AnswerSegment(text="가장 가까운 곳이 "),
                AnswerSegment(text=f"{min(kms):.1f}km", emphasis=True),
                AnswerSegment(text="예요."),
            ]
    return []


def _answer(
    top: list[CandidateRow],
    *,
    intent: QueryIntent,
    near: bool,
    lat: float | None,
    lng: float | None,
    region_widened: retrieve.RegionScope | None = None,
) -> list[AnswerSegment]:
    lead = _lead_sentence(
        top, intent=intent, near=near, lat=lat, lng=lng, region_widened=region_widened
    )
    scope = _scope_sentence(top, intent=intent)
    if not lead:
        return [*scope, AnswerSegment(text=" 마음에 드는 게 없으면 조건을 좁혀 말해주세요.")]
    return [*lead, AnswerSegment(text=" "), *scope]
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -v
```

Expected: PASS. `test_an_empty_sigungu_widens_to_the_sido_and_says_so` 는 `"수영"` 과
`"부산광역시"` 가 답변에 있는지만 보므로 그대로 통과한다.

- [ ] **Step 5: 정적 검사**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports
```

Expected: 전부 통과. `_widen_sentence` 가 더 이상 `_answer` 에서 쓰이지 않지만 사진
경로(`ask.py:248`)가 여전히 쓰므로 지우지 않는다.

---

### Task 2: 백엔드 — 나머지 답변 문장도 사실을 앞세운다

**Files:**
- Modify: `backend/app/modules/agent/services/ask.py:242-249`, `:338-347`, `:915-923`, `:965-971`, `:1038-1042`, `:1252-1261`
- Test: `backend/tests/test_agent_ask.py`, `backend/tests/test_agent_anchor.py`

**Interfaces:**
- Consumes: Task 1 의 `_lead_sentence` / `_scope_sentence` 는 검색 경로 전용이라 여기서 쓰지 않는다.
- Produces: 없음 (문자열만 바뀐다)

- [ ] **Step 1: 각 경로의 새 문장을 테스트로 못박는다**

`backend/tests/test_agent_ask.py` 끝에 추가한다.

```python
def test_a_zero_answer_leads_with_the_conditions_that_failed() -> None:
    segments = ask_service._zero_answer(
        QueryIntent(regionHints=["울릉도"], indoorOnly=True),
        axes=suggest_service.ALL_AXES,
    )

    text = "".join(s.text for s in segments)
    assert text.startswith("울릉도 + 실내 조건으로는 없어요.")
    assert "지역을 넓히면" in text
    assert [s.text for s in segments if s.emphasis] == ["울릉도 + 실내"]
```

`suggest_service` 가 아직 import 되어 있지 않으면 상단에
`from app.modules.agent.services import suggest as suggest_service` 를 더한다.

`backend/tests/test_agent_anchor.py` 끝에 추가한다.

```python
def test_an_anchor_answer_leads_with_the_nearest_distance() -> None:
    from app.modules.agent.repositories import NearbyRow
    from app.modules.agent.services import ask as ask_service

    segments = ask_service._anchor_lead("성산일출봉", "food", nearest_m=420)

    text = "".join(s.text for s in segments)
    assert text.startswith("가장 가까운 맛집이 420m 거리예요.")
    assert [s.text for s in segments if s.emphasis] == ["420m"]


def test_an_anchor_answer_without_a_distance_states_the_scope() -> None:
    from app.modules.agent.services import ask as ask_service

    segments = ask_service._anchor_lead("성산일출봉", "cafe", nearest_m=None)

    assert "".join(s.text for s in segments) == "성산일출봉 주변 카페예요."
```

사용하지 않는 `NearbyRow` import 는 넣지 않는다 — 위 첫 테스트에서 그 줄을 지운다.

- [ ] **Step 2: 실패를 확인한다**

```bash
cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py::test_a_zero_answer_leads_with_the_conditions_that_failed tests/test_agent_anchor.py -v
```

Expected: FAIL — `_anchor_lead` 가 없고, `_zero_answer` 는 `"…조건으로는 0곳이에요."` 를 낸다.

- [ ] **Step 3: 여섯 지점을 고친다**

**(a) `_zero_answer` (`ask.py:1252`)** — 통째로 교체한다.

```python
def _zero_answer(intent: QueryIntent, *, axes: frozenset[DropAxis]) -> list[AnswerSegment]:
    conditions = _applied_conditions(intent, axes=axes)
    if not conditions:
        return [
            AnswerSegment(text="이 조건으로는 없어요."),
            AnswerSegment(text=" 조건을 조금 바꿔서 다시 물어봐 주세요."),
        ]
    return [
        AnswerSegment(text=" + ".join(conditions), emphasis=True),
        AnswerSegment(text=" 조건으로는 없어요."),
        AnswerSegment(text=" 지역을 넓히면 나올 수 있어요."),
    ]
```

**(b) 앵커 공용 헤드라인** — `_anchor_crowd_response` 바로 위(`ask.py:387` 근처)에 새 헬퍼를 둔다.

```python
def _anchor_lead(origin: str, action: AnchorAction, *, nearest_m: int | None) -> list[AnswerSegment]:
    noun = ANCHOR_NOUNS[action]
    if nearest_m is None:
        return [AnswerSegment(text=f"{origin} 주변 {noun}예요.")]
    return [
        AnswerSegment(text=f"가장 가까운 {noun}이 "),
        AnswerSegment(text=_meters_label(nearest_m), emphasis=True),
        AnswerSegment(text=" 거리예요."),
    ]
```

**(c) 앵커 결과 (`ask.py:338-347`)** — `answer` 조립 블록과 그 아래 `nearest` 블록을 이걸로 바꾼다.

```python
    nearest = kept[0].dist
    answer = [
        *_anchor_lead(origin, anchor.action, nearest_m=nearest),
        AnswerSegment(text=f" {origin} 주변으로 "),
        AnswerSegment(text=f"{len(spots)}곳이에요."),
    ]
```

**(d) 근처 맛집/카페 (`ask.py:915-923`)** — 같은 모양으로 바꾼다.

```python
    answer = [
        *_anchor_lead(origin, action, nearest_m=kept[0].dist),
        AnswerSegment(text=f" {origin} 주변으로 "),
        AnswerSegment(text=f"{len(spots)}곳이에요."),
    ]
```

**(e) 지역 맛집 (`ask.py:967-971`)** — `answer=[...]` 인라인 리스트를 바꾼다.

```python
        answer=[
            AnswerSegment(text=where, emphasis=True),
            AnswerSegment(text=f" {noun} "),
            AnswerSegment(text=f"{len(spots)}곳이에요."),
        ],
```

**(f) 사진 (`ask.py:242-249`)** — 1순위 이름을 앞세운다.

```python
    answer = [
        AnswerSegment(text=spots[0].title, emphasis=True),
        AnswerSegment(text="이 가장 비슷해요. 사진과 닮은 곳으로 "),
        AnswerSegment(text=f"{len(top)}곳이에요."),
    ]
    if widened is not None:
        answer.extend(_widen_sentence(widened))
    answer.append(AnswerSegment(text=" 원본 사진은 비교 후 바로 폐기했어요."))
```

**(g) 축제 (`ask.py:1038-1042`)**

```python
    answer = [
        AnswerSegment(text=spots[0].title, emphasis=True),
        AnswerSegment(text="이 오늘 열려요. 오늘 열리는 축제로 "),
        AnswerSegment(text=f"{len(spots)}곳이에요."),
    ]
```

- [ ] **Step 4: 전체 백엔드 테스트를 돌린다**

```bash
cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest
```

Expected: PASS. 문자열을 보는 기존 테스트가 깨지면 **테스트를 새 문장에 맞춘다** —
단, `"0곳"` 을 찾는 두 테스트(`test_nothing_matching_answers_with_zero_and_a_way_out:355`,
`test_a_photo_that_matches_nothing_answers_with_zero_not_an_error:629`)는 이제 `"없어요"` 를
찾도록 바꾼다.

- [ ] **Step 5: 정적 검사**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports
```

Expected: 전부 통과.

---

### Task 3: `answer-split` — 답변을 헤드라인과 보충으로 가른다

**Files:**
- Create: `mobile/src/features/travel/lib/answer-split.ts`
- Test: `mobile/src/features/travel/lib/__tests__/answer-split.test.ts`

**Interfaces:**
- Consumes: `AnswerPart` from `@/features/travel/api`
- Produces: `splitAnswer(parts: AnswerPart[]): { lead: AnswerPart[]; rest: AnswerPart[] }`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```ts
import { splitAnswer } from "@/features/travel/lib/answer-split";
import type { AnswerPart } from "@/features/travel/api";

const part = (text: string, emphasis = false): AnswerPart => ({ text, emphasis });

describe("splitAnswer", () => {
  it("첫 문장까지를 헤드라인으로 가른다", () => {
    const { lead, rest } = splitAnswer([
      part("혼잡도 "),
      part("하위 20%", true),
      part(" 안쪽으로만 골랐어요. 제주 동쪽으로 8곳이에요."),
    ]);

    expect(lead.map((p) => p.text).join("")).toBe("혼잡도 하위 20% 안쪽으로만 골랐어요.");
    expect(rest.map((p) => p.text).join("")).toBe("제주 동쪽으로 8곳이에요.");
  });

  it("헤드라인 안의 강조를 유지한다", () => {
    const { lead } = splitAnswer([part("혼잡도 "), part("하위 20%", true), part(" 안쪽이에요. 뒤.")]);

    expect(lead.filter((p) => p.emphasis).map((p) => p.text)).toEqual(["하위 20%"]);
  });

  it("문장 부호가 없으면 전부 헤드라인이다", () => {
    const { lead, rest } = splitAnswer([part("아직 정보가 없어요")]);

    expect(lead.map((p) => p.text).join("")).toBe("아직 정보가 없어요");
    expect(rest).toEqual([]);
  });

  it("물음표·느낌표도 문장 끝으로 센다", () => {
    const { lead, rest } = splitAnswer([part("어디로 갈까요? 조건을 알려주세요.")]);

    expect(lead.map((p) => p.text).join("")).toBe("어디로 갈까요?");
    expect(rest.map((p) => p.text).join("")).toBe("조건을 알려주세요.");
  });

  it("빈 입력에도 빈 두 조각을 준다", () => {
    expect(splitAnswer([])).toEqual({ lead: [], rest: [] });
  });

  it("문장 부호가 마지막 조각 끝에 있으면 보충이 비어 있다", () => {
    const { lead, rest } = splitAnswer([part("한 문장뿐이에요.")]);

    expect(lead.map((p) => p.text).join("")).toBe("한 문장뿐이에요.");
    expect(rest).toEqual([]);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/lib/__tests__/answer-split.test.ts
```

Expected: FAIL — `Cannot find module '@/features/travel/lib/answer-split'`

- [ ] **Step 3: 구현한다**

```ts
import type { AnswerPart } from "@/features/travel/api";

const SENTENCE_END = /[.?!]/;

export interface SplitAnswer {
  lead: AnswerPart[];
  rest: AnswerPart[];
}

export function splitAnswer(parts: AnswerPart[]): SplitAnswer {
  const lead: AnswerPart[] = [];

  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    const at = part.text.search(SENTENCE_END);
    if (at === -1) {
      lead.push(part);
      continue;
    }
    const head = part.text.slice(0, at + 1);
    const tail = part.text.slice(at + 1).trimStart();
    if (head) lead.push({ ...part, text: head });
    const rest = tail ? [{ ...part, text: tail }, ...parts.slice(index + 1)] : parts.slice(index + 1);
    return { lead, rest };
  }

  return { lead, rest: [] };
}
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd mobile && npx jest src/features/travel/lib/__tests__/answer-split.test.ts
```

Expected: PASS (6 tests)

---

### Task 4: `metric` — 태그를 아이콘 칩으로 옮긴다

**Files:**
- Create: `mobile/src/features/travel/lib/metric.ts`
- Test: `mobile/src/features/travel/lib/__tests__/metric.test.ts`

**Interfaces:**
- Consumes: `IconName` from `@/components/Icon`
- Produces:
  - `isDistanceTag(tag: string | null | undefined): boolean`
  - `metricOf(tag: string | null | undefined, tagBasis: string | null | undefined): Metric | null`
  - `interface Metric { icon: IconName; label: string; tooltip: string }`

서버 `tag` 값은 `"2.4km"` · `"하위 8%"` · `"한산"`/`"보통"`/`"붐빔"` · `"유사도 87%"` ·
`"D-3"` · `null` 이다. **라벨은 서버 문자열을 그대로 쓴다** — 목업의 `분위기 비슷` 처럼
클라이언트가 새 낱말을 지어내지 않는다. 아이콘과 툴팁만 `tagBasis` 에서 고른다.
거리 태그는 칩이 아니라 카드의 지역 줄이 맡으므로 `metricOf` 가 `null` 을 준다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```ts
import { isDistanceTag, metricOf } from "@/features/travel/lib/metric";

describe("isDistanceTag", () => {
  it.each(["2.4km", "870m", "12km"])("거리 태그를 알아본다: %s", (tag) => {
    expect(isDistanceTag(tag)).toBe(true);
  });

  it.each(["한산", "하위 8%", "D-3", null, undefined])("거리가 아닌 것: %s", (tag) => {
    expect(isDistanceTag(tag)).toBe(false);
  });
});

describe("metricOf", () => {
  it("거리 태그는 칩이 되지 않는다 — 지역 줄이 이미 말한다", () => {
    expect(metricOf("2.4km", "직선거리 기준")).toBeNull();
  });

  it("혼잡도 태그는 사람 아이콘과 예측 근거를 든다", () => {
    expect(metricOf("한산", "혼잡도 8/3 예측 기준")).toEqual({
      icon: "users",
      label: "한산",
      tooltip: "혼잡도 8/3 예측 기준",
    });
  });

  it("백분위 태그도 혼잡도로 읽는다", () => {
    expect(metricOf("하위 8%", "혼잡도 예측 기준")?.icon).toBe("users");
  });

  it("사진 유사도는 이미지 아이콘을 쓰고 서버 문구를 그대로 든다", () => {
    expect(metricOf("유사도 87%", "사진 유사도 기준")).toEqual({
      icon: "image",
      label: "유사도 87%",
      tooltip: "사진 유사도 기준",
    });
  });

  it("축제 디데이는 달력 아이콘을 쓰고 근거 줄이 없다", () => {
    expect(metricOf("D-3", null)).toEqual({
      icon: "calendar",
      label: "D-3",
      tooltip: "축제 기간 기준",
    });
  });

  it("태그가 없으면 칩도 없다", () => {
    expect(metricOf(null, "직선거리 기준")).toBeNull();
    expect(metricOf("", null)).toBeNull();
  });

  it("모르는 태그는 근거 없이 중립 아이콘으로 낸다", () => {
    expect(metricOf("바다뷰", null)).toEqual({
      icon: "tag",
      label: "바다뷰",
      tooltip: "",
    });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/lib/__tests__/metric.test.ts
```

Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현한다**

```ts
import type { IconName } from "@/components/Icon";

export interface Metric {
  icon: IconName;
  label: string;
  tooltip: string;
}

const DISTANCE = /^[\d.]+(km|m)$/;
const CROWD = /^(한산|보통|붐빔|하위 \d+%|상위 \d+%)$/;
const DDAY = /^D[-+]\d+$|^D-DAY$/;
const CROWD_FALLBACK = "혼잡도 예측 기준";
const PHOTO_FALLBACK = "사진 유사도 기준";
const FESTIVAL_BASIS = "축제 기간 기준";

export function isDistanceTag(tag: string | null | undefined): boolean {
  return typeof tag === "string" && DISTANCE.test(tag);
}

export function metricOf(
  tag: string | null | undefined,
  tagBasis: string | null | undefined,
): Metric | null {
  if (!tag) return null;
  if (isDistanceTag(tag)) return null;
  if (CROWD.test(tag)) {
    return { icon: "users", label: tag, tooltip: tagBasis ?? CROWD_FALLBACK };
  }
  if (tag.startsWith("유사도 ")) {
    return { icon: "image", label: tag, tooltip: tagBasis ?? PHOTO_FALLBACK };
  }
  if (DDAY.test(tag)) {
    return { icon: "calendar", label: tag, tooltip: FESTIVAL_BASIS };
  }
  return { icon: "tag", label: tag, tooltip: "" };
}
```

- [ ] **Step 4: `Icon` 에 없는 이름을 채운다**

```bash
cd mobile && grep -n "users\|calendar\|\"tag\"" src/components/Icon.tsx
```

`users` · `calendar` · `tag` 중 없는 것이 있으면 `Icon.tsx` 의 `IconName` 유니온과 path
맵에 추가한다. 획은 기존 아이콘과 같은 규칙(`fill="none"`, `strokeLinecap="round"`,
`strokeLinejoin="round"`)을 따르고 viewBox 는 `0 0 24 24` 다.

```tsx
users: <><Circle cx="9.5" cy="8" r="3.2" /><Path d="M3.5 19c0-3 2.7-5 6-5s6 2 6 5" /><Path d="M16.4 5.2a3.1 3.1 0 010 5.9M17.6 14.4c2 .7 3.4 2.3 3.4 4.6" /></>,
tag: <><Path d="M4 4h7l9 9-7 7-9-9z" /><Circle cx="8" cy="8" r="1.4" /></>,
```

`calendar` 는 `StartActions` 가 이미 쓰고 있으므로 존재한다.

- [ ] **Step 5: 통과를 확인한다**

```bash
cd mobile && npx jest src/features/travel/lib/__tests__/metric.test.ts && npm run typecheck
```

Expected: PASS (10 tests), 타입 통과

---

### Task 5: `dock-chips` — 칩이 보고 있는 카드를 따라간다

**Files:**
- Create: `mobile/src/features/travel/lib/dock-chips.ts`
- Test: `mobile/src/features/travel/lib/__tests__/dock-chips.test.ts`
- Modify: `mobile/src/features/travel/lib/chips.ts` (`ANCHOR_CHIPS` 라벨을 술어로 줄인다)

**Interfaces:**
- Consumes: `Chip` · `ANCHOR_CHIPS` · `idleChips` · `refineChips` from `@/features/travel/lib/chips`
- Produces:
  - `type DockChip = { kind: "photo" } | { kind: "context"; title: string; expanded: boolean } | { kind: "query"; chip: Chip }`
  - `dockChips(input: DockChipsInput): DockChip[]`
  - `interface DockChipsInput { answer: ChipAnswer | null; focused: TravelSpot | null; expanded: boolean; hasCoords: boolean; hasCrowd: boolean }`

`ANCHOR_CHIPS` 의 라벨은 문맥 칩이 장소명을 이미 들고 있으므로 `근처 맛집` → `맛집`,
`근처 카페` → `카페`, `주변 볼거리` → `볼거리` 로 줄인다. `오늘 붐벼?` 는 그대로 둔다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```ts
import { dockChips } from "@/features/travel/lib/dock-chips";
import type { TravelSpot } from "@/features/travel/api";

const spot: TravelSpot = {
  contentId: "1",
  title: "성산일출봉",
  regionLabel: "서귀포시",
  imageUrl: null,
  tag: "한산",
  lat: 33.4,
  lng: 126.9,
  hasCrowd: true,
};

const base = { answer: null, focused: null, expanded: false, hasCoords: false, hasCrowd: false };

describe("dockChips", () => {
  it("사진 칩은 항상 맨 앞에 있다", () => {
    expect(dockChips(base)[0]).toEqual({ kind: "photo" });
    expect(dockChips({ ...base, focused: spot })[0]).toEqual({ kind: "photo" });
  });

  it("보고 있는 카드가 없으면 초기 칩을 낸다", () => {
    const labels = dockChips({ ...base, hasCoords: true })
      .flatMap((c) => (c.kind === "query" ? [c.chip.label] : []));

    expect(labels).toContain("근처 맛집");
  });

  it("보고 있는 카드가 있으면 문맥 칩이 사진 칩 다음에 온다", () => {
    const chips = dockChips({ ...base, focused: spot });

    expect(chips[1]).toEqual({ kind: "context", title: "성산일출봉", expanded: false });
  });

  it("펼치면 사진 칩이 빠지고 문맥 칩 뒤에 술어만 온다", () => {
    const chips = dockChips({ ...base, focused: spot, expanded: true, hasCrowd: true });

    expect(chips[0]).toEqual({ kind: "context", title: "성산일출봉", expanded: true });
    expect(chips.slice(1).map((c) => (c.kind === "query" ? c.chip.label : ""))).toEqual([
      "맛집",
      "카페",
      "볼거리",
      "오늘 붐벼?",
    ]);
  });

  it("혼잡도를 모르는 곳에는 붐빔 술어를 내지 않는다", () => {
    const chips = dockChips({ ...base, focused: spot, expanded: true, hasCrowd: false });

    expect(chips.map((c) => (c.kind === "query" ? c.chip.label : ""))).not.toContain("오늘 붐벼?");
  });

  it("접힌 상태에서는 문맥 칩 뒤에 refine 칩이 붙는다", () => {
    const chips = dockChips({
      ...base,
      focused: spot,
      answer: {
        totalCount: 8,
        refinements: [{ label: "사람 적은 곳만", patch: { crowdPreference: "quiet" } }],
      },
    });

    expect(chips.map((c) => (c.kind === "query" ? c.chip.label : ""))).toContain("사람 적은 곳만");
  });

  it("펼침은 보고 있는 카드가 있을 때만 성립한다", () => {
    expect(dockChips({ ...base, expanded: true })[0]).toEqual({ kind: "photo" });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/lib/__tests__/dock-chips.test.ts
```

Expected: FAIL — 모듈 없음

- [ ] **Step 3: `chips.ts` 의 앵커 라벨을 줄인다**

`mobile/src/features/travel/lib/chips.ts` 의 `ANCHOR_CHIPS` 를 교체한다.

```ts
export const ANCHOR_CHIPS: AnchorChip[] = [
  { kind: "anchor", label: "맛집", action: "food" },
  { kind: "anchor", label: "카페", action: "cafe" },
  { kind: "anchor", label: "볼거리", action: "nearby" },
  { kind: "anchor", label: "오늘 붐벼?", action: "crowd" },
];
```

`chips.test.ts` 에 `"근처 맛집"` 을 기대하는 단언이 있으면 새 라벨로 고친다.
`NEARBY_IDLE_CHIPS` 의 `근처 맛집` · `근처 카페` 는 **내 위치 기준**이라 그대로 둔다.

- [ ] **Step 4: 구현한다**

```ts
import { anchorChips, idleChips, refineChips, type Chip } from "@/features/travel/lib/chips";
import type { AgentAnswer, QueryIntent, TravelSpot } from "@/features/travel/api";

export type DockChip =
  | { kind: "photo" }
  | { kind: "context"; title: string; expanded: boolean }
  | { kind: "query"; chip: Chip };

type ChipAnswer = Pick<AgentAnswer, "totalCount" | "refinements"> & {
  intent?: QueryIntent | null;
};

export interface DockChipsInput {
  answer: ChipAnswer | null;
  focused: TravelSpot | null;
  expanded: boolean;
  hasCoords: boolean;
  hasCrowd: boolean;
}

function queries(chips: Chip[]): DockChip[] {
  return chips.map((chip) => ({ kind: "query", chip }));
}

export function dockChips({
  answer,
  focused,
  expanded,
  hasCoords,
  hasCrowd,
}: DockChipsInput): DockChip[] {
  if (focused && expanded) {
    return [
      { kind: "context", title: focused.title, expanded: true },
      ...queries(anchorChips(hasCrowd)),
    ];
  }

  const refine = refineChips(answer?.refinements);
  const trailing = refine.length > 0 ? refine : answer ? [] : idleChips(hasCoords);
  const context: DockChip[] = focused
    ? [{ kind: "context", title: focused.title, expanded: false }]
    : [];

  return [{ kind: "photo" }, ...context, ...queries(trailing)];
}
```

- [ ] **Step 5: 통과를 확인한다**

```bash
cd mobile && npx jest src/features/travel/lib/__tests__/dock-chips.test.ts src/features/travel/lib/__tests__/chips.test.ts && npm run typecheck
```

Expected: PASS

---

### Task 6: `AnswerBar` — 답변이 헤드라인이 된다

**Files:**
- Create: `mobile/src/features/travel/components/AnswerBar.tsx`
- Test: `mobile/src/features/travel/components/__tests__/AnswerBar.test.tsx`

**Interfaces:**
- Consumes: `splitAnswer` (Task 3)
- Produces: `AnswerBar` with props
  ```ts
  interface Props {
    question: string;
    answer: AnswerPart[] | null;
    photoUri: string | null;
    step: string | null;
    errorMessage: string | null;
    expanded: boolean;
    top: number;
    onToggle: () => void;
    onClose: () => void;
    onRetry: () => void;
  }
  ```

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```tsx
import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { AnswerBar } from "@/features/travel/components/AnswerBar";
import type { AnswerPart } from "@/features/travel/api";

const answer: AnswerPart[] = [
  { text: "혼잡도 ", emphasis: false },
  { text: "하위 20%", emphasis: true },
  { text: " 안쪽으로만 골랐어요. 제주 동쪽으로 8곳이에요.", emphasis: false },
];

const base = {
  question: "제주에서 한적한 곳",
  answer,
  photoUri: null,
  step: null,
  errorMessage: null,
  expanded: false,
  top: 60,
  onToggle: jest.fn(),
  onClose: jest.fn(),
  onRetry: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof AnswerBar>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<AnswerBar {...base} {...props} />);
  });
  return tree!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string =>
  tree.root
    .findAllByType(Text)
    .map((n) => flatten(n.props.children))
    .join("");

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAllByProps({ testID: id }).find((n) => typeof n.props.onPress === "function");
}

describe("AnswerBar", () => {
  it("접히면 헤드라인만 보이고 보충은 감춘다", () => {
    const shown = texts(mount());

    expect(shown).toContain("안쪽으로만 골랐어요.");
    expect(shown).not.toContain("제주 동쪽으로 8곳이에요.");
  });

  it("펼치면 보충까지 보인다", () => {
    expect(texts(mount({ expanded: true }))).toContain("제주 동쪽으로 8곳이에요.");
  });

  it("질문은 라벨로만 그린다", () => {
    expect(texts(mount())).toContain("제주에서 한적한 곳");
  });

  it("진행 중에는 답변 대신 단계 한 줄을 든다", () => {
    const shown = texts(mount({ answer: null, step: "질문에서 조건 읽는 중" }));

    expect(shown).toContain("질문에서 조건 읽는 중");
    expect(shown).not.toContain("골랐어요");
  });

  it("실패에는 재시도 버튼이 붙는다", () => {
    const onRetry = jest.fn();
    const tree = mount({ answer: null, errorMessage: "네트워크가 불안정해요", onRetry });

    expect(texts(tree)).toContain("네트워크가 불안정해요");
    act(() => byId(tree, "travel-retry")!.props.onPress());
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("보충이 없으면 펼침 토글을 그리지 않는다", () => {
    const tree = mount({ answer: [{ text: "한 문장뿐이에요.", emphasis: false }] });

    expect(byId(tree, "travel-answer-toggle")).toBeUndefined();
  });

  it("새 대화 버튼은 항상 있다", () => {
    const onClose = jest.fn();
    const tree = mount({ onClose });

    act(() => byId(tree, "travel-new-chat")!.props.onPress());
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/AnswerBar.test.tsx
```

Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현한다**

```tsx
import { Pressable, View, Text, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import { splitAnswer } from "@/features/travel/lib/answer-split";
import type { AnswerPart } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const FAIL_TITLE = "답변을 못 받았어요";
export const RETRY_LABEL = "다시 시도";

interface Props {
  question: string;
  answer: AnswerPart[] | null;
  photoUri: string | null;
  step: string | null;
  errorMessage: string | null;
  expanded: boolean;
  top: number;
  onToggle: () => void;
  onClose: () => void;
  onRetry: () => void;
}

function Sentence({ parts, style }: { parts: AnswerPart[]; style: object }) {
  return (
    <Text style={style} numberOfLines={undefined}>
      {parts.map((part, index) => (
        <Text key={`${index}-${part.text}`} style={part.emphasis ? styles.emphasis : undefined}>
          {part.text}
        </Text>
      ))}
    </Text>
  );
}

export function AnswerBar({
  question,
  answer,
  photoUri,
  step,
  errorMessage,
  expanded,
  top,
  onToggle,
  onClose,
  onRetry,
}: Props) {
  const failed = errorMessage !== null;
  const { lead, rest } = splitAnswer(answer ?? []);
  const toggleable = !failed && step === null && rest.length > 0;

  return (
    <View
      testID="travel-answer-bar"
      style={[styles.root, { top }, failed && styles.failed]}
      pointerEvents="box-none"
    >
      <View style={styles.head}>
        {photoUri ? (
          <Image source={{ uri: photoUri }} style={styles.thumb} contentFit="cover" />
        ) : null}
        <Text style={[styles.question, failed && styles.failTitle]} numberOfLines={1}>
          {failed ? FAIL_TITLE : question}
        </Text>
        <Pressable
          testID="travel-new-chat"
          accessibilityRole="button"
          accessibilityLabel="새 대화"
          hitSlop={8}
          onPress={onClose}
        >
          <Icon name="close" size={16} color={colors.ter} strokeWidth={2} />
        </Pressable>
      </View>

      {step !== null ? (
        <View style={styles.step}>
          <View style={styles.spinner} />
          <Text style={styles.stepText} numberOfLines={1}>
            {step}
          </Text>
        </View>
      ) : failed ? (
        <>
          <Text style={styles.support}>{errorMessage}</Text>
          <View style={styles.retryRow}>
            <Pressable
              testID="travel-retry"
              accessibilityRole="button"
              style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
              onPress={onRetry}
            >
              <Text style={styles.retryText}>{RETRY_LABEL}</Text>
            </Pressable>
          </View>
        </>
      ) : (
        <Pressable
          testID={toggleable ? "travel-answer-toggle" : undefined}
          accessibilityRole={toggleable ? "button" : undefined}
          accessibilityLabel={toggleable ? (expanded ? "답변 접기" : "답변 펼치기") : undefined}
          disabled={!toggleable}
          onPress={onToggle}
          style={styles.body}
        >
          <View style={styles.copy}>
            <Sentence parts={lead} style={styles.lead} />
            {expanded && rest.length > 0 ? (
              <Sentence parts={rest} style={styles.support} />
            ) : null}
          </View>
          {toggleable ? (
            <Icon
              name={expanded ? "chevron-up" : "chevron-down"}
              size={18}
              color={colors.ter}
              strokeWidth={2}
            />
          ) : null}
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: "absolute",
    left: spacing.md,
    right: spacing.md,
    padding: 12,
    paddingLeft: spacing.md,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glassFill,
  },
  failed: { borderLeftWidth: 3, borderLeftColor: colors.accent, paddingLeft: 12 },
  head: { flexDirection: "row", alignItems: "center", gap: 10 },
  thumb: { width: 40, height: 40, borderRadius: 10 },
  question: { flex: 1, minWidth: 0, fontSize: 11, fontWeight: "700", color: colors.ter },
  failTitle: { fontSize: 13.5, letterSpacing: -0.3, color: colors.accentText },
  body: { flexDirection: "row", alignItems: "flex-end", gap: 10, marginTop: 6 },
  copy: { flex: 1, minWidth: 0 },
  lead: {
    fontSize: 14.5,
    fontWeight: "700",
    lineHeight: 21,
    letterSpacing: -0.35,
    color: colors.ink,
  },
  emphasis: { color: colors.accentText },
  support: {
    marginTop: 5,
    fontSize: 13,
    fontWeight: "600",
    lineHeight: 20,
    letterSpacing: -0.2,
    color: colors.sec,
  },
  step: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 7 },
  spinner: {
    width: 13,
    height: 13,
    borderRadius: 7,
    borderWidth: 2,
    borderColor: colors.line,
    borderTopColor: colors.accent,
  },
  stepText: { flex: 1, fontSize: 12.5, letterSpacing: -0.2, color: colors.sec },
  retryRow: { flexDirection: "row", justifyContent: "flex-end", marginTop: 12 },
  retry: {
    height: 34,
    paddingHorizontal: 18,
    borderRadius: radii.lg,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { opacity: 0.7 },
  retryText: { fontSize: 13, fontWeight: "700", color: colors.onImage },
});
```

접힘 상태에서 헤드라인이 2줄을 넘지 않도록 `lead` 에 `numberOfLines={2}` 를 주고 싶겠지만,
`Sentence` 는 강조 조각을 자식으로 들기 때문에 `numberOfLines` 를 걸면 강조가 잘린 줄에서
사라진다. 헤드라인은 한 문장이라 2줄을 거의 넘지 않으므로 제한하지 않는다.

- [ ] **Step 4: `Icon` 에 셰브런이 있는지 확인한다**

```bash
cd mobile && grep -n "chevron-up\|chevron-down" src/components/Icon.tsx
```

없으면 `IconName` 유니온과 path 맵에 추가한다.

```tsx
"chevron-down": <Path d="M6 9.5l6 6 6-6" />,
"chevron-up": <Path d="M6 14.5l6-6 6 6" />,
```

- [ ] **Step 5: 통과를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/AnswerBar.test.tsx && npm run typecheck
```

Expected: PASS (7 tests)

---

### Task 7: `SpotCard` — 정보만 든 카드

**Files:**
- Create: `mobile/src/features/travel/components/SpotCard.tsx`
- Test: `mobile/src/features/travel/components/__tests__/SpotCard.test.tsx`

**Interfaces:**
- Consumes: `metricOf` (Task 4) · `useSaveOptimistic` · `prefetchSpot` · `distanceReading`
- Produces: `SpotCard` with props
  ```ts
  interface Props {
    spot: TravelSpot;
    index: number;
    tagBasis: string | null;
    distanceKm: number | null;
    focused: boolean;
    onDetail: () => void;
    onSaveToggle: (saved: boolean) => void;
    onMetricPress: (tooltip: string) => void;
  }
  ```

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```tsx
import renderer, { act } from "react-test-renderer";
import { Text } from "react-native";
import { SpotCard } from "@/features/travel/components/SpotCard";
import type { TravelSpot } from "@/features/travel/api";

jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({ useSaveOptimistic: jest.fn() }));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const { useSaveOptimistic } = jest.requireMock("@/features/saved/hooks/use-save-optimistic") as {
  useSaveOptimistic: jest.Mock;
};
const toggle = jest.fn();

const spot: TravelSpot = {
  contentId: "126508",
  title: "성산일출봉",
  regionLabel: "서귀포시",
  imageUrl: null,
  tag: "한산",
  lat: 33.4,
  lng: 126.9,
};

const base = {
  spot,
  index: 0,
  tagBasis: "혼잡도 8/3 예측 기준",
  distanceKm: 2.4,
  focused: false,
  onDetail: jest.fn(),
  onSaveToggle: jest.fn(),
  onMetricPress: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof SpotCard>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<SpotCard {...base} {...props} />);
  });
  return tree!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string =>
  tree.root
    .findAllByType(Text)
    .map((n) => flatten(n.props.children))
    .join("");

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAllByProps({ testID: id }).find((n) => typeof n.props.onPress === "function");
}

beforeEach(() => {
  jest.clearAllMocks();
  toggle.mockResolvedValue(true);
  useSaveOptimistic.mockReturnValue({ saved: false, toggle });
});

describe("SpotCard", () => {
  it("지도 핀과 같은 번호를 단다", () => {
    expect(texts(mount({ index: 2 }))).toContain("3");
  });

  it("거리는 칩이 아니라 지역 줄에 붙는다", () => {
    expect(texts(mount())).toContain("서귀포시 · 2.4km");
  });

  it("좌표를 모르면 지역만 적는다", () => {
    const shown = texts(mount({ distanceKm: null }));

    expect(shown).toContain("서귀포시");
    expect(shown).not.toContain("km");
  });

  it("성질 태그는 칩으로 남는다", () => {
    expect(texts(mount())).toContain("한산");
  });

  it("거리 태그는 칩을 만들지 않는다", () => {
    const tree = mount({ spot: { ...spot, tag: "2.4km" }, tagBasis: "직선거리 기준" });

    expect(byId(tree, "travel-metric")).toBeUndefined();
  });

  it("칩을 누르면 근거 문구를 위로 올린다", () => {
    const onMetricPress = jest.fn();
    const tree = mount({ onMetricPress });

    act(() => byId(tree, "travel-metric")!.props.onPress());

    expect(onMetricPress).toHaveBeenCalledWith("혼잡도 8/3 예측 기준");
  });

  it("상세보기 버튼과 카드 본문이 같은 곳으로 간다", () => {
    const onDetail = jest.fn();
    const tree = mount({ onDetail });

    act(() => byId(tree, "travel-card-detail")!.props.onPress());
    act(() => byId(tree, `travel-card-126508`)!.props.onPress());

    expect(onDetail).toHaveBeenCalledTimes(2);
  });

  it("저장 결과를 그대로 알린다", async () => {
    toggle.mockResolvedValueOnce(false);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });

    await act(async () => byId(tree, "travel-card-save-126508")!.props.onPress());

    expect(onSaveToggle).toHaveBeenCalledWith(false);
  });

  it("저장에 실패하면 알리지 않는다", async () => {
    toggle.mockResolvedValueOnce(null);
    const onSaveToggle = jest.fn();
    const tree = mount({ onSaveToggle });

    await act(async () => byId(tree, "travel-card-save-126508")!.props.onPress());

    expect(onSaveToggle).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/SpotCard.test.tsx
```

Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현한다**

```tsx
import { Pressable, View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { prefetchSpot } from "@/features/spots/queries";
import { distanceReading } from "@/features/travel/lib/distance";
import { metricOf } from "@/features/travel/lib/metric";
import type { TravelSpot } from "@/features/travel/api";
import { colors, radii } from "@/constants/theme";

export const CARD_WIDTH = 296;
export const CARD_HEIGHT = 112;
export const CARD_GAP = 10;
export const CARD_STRIDE = CARD_WIDTH + CARD_GAP;

export const DETAIL_LABEL = "상세보기";

interface Props {
  spot: TravelSpot;
  index: number;
  tagBasis: string | null;
  distanceKm: number | null;
  focused: boolean;
  onDetail: () => void;
  onSaveToggle: (saved: boolean) => void;
  onMetricPress: (tooltip: string) => void;
}

export function SpotCard({
  spot,
  index,
  tagBasis,
  distanceKm,
  focused,
  onDetail,
  onSaveToggle,
  onMetricPress,
}: Props) {
  const { saved, toggle } = useSaveOptimistic(spot.contentId);
  const metric = metricOf(spot.tag, tagBasis);
  const reading = distanceKm === null ? null : distanceReading(distanceKm);

  return (
    <View style={styles.card}>
      <Pressable
        testID={`travel-card-${spot.contentId}`}
        accessibilityRole="button"
        accessibilityLabel={`${spot.title} 상세 보기`}
        style={({ pressed }) => [styles.tap, pressed && styles.pressed]}
        onPressIn={() => prefetchSpot(spot)}
        onPress={onDetail}
      >
        <RemoteImage uri={spot.imageUrl} style={styles.thumb} radius={12} />

        <View style={styles.copy}>
          <View style={styles.head}>
            <View style={[styles.badge, focused && styles.badgeFocused]}>
              <Text style={[styles.badgeText, focused && styles.badgeTextFocused]}>{index + 1}</Text>
            </View>
            <Text style={styles.title} numberOfLines={1}>
              {spot.title}
            </Text>
          </View>

          <Text style={styles.region} numberOfLines={1}>
            {spot.regionLabel}
            {reading ? " · " : ""}
            {reading ? (
              <Text style={styles.distance}>{`${reading.value}${reading.unit}`}</Text>
            ) : null}
          </Text>

          <View style={styles.row}>
            {metric ? (
              <Pressable
                testID="travel-metric"
                accessibilityRole="button"
                accessibilityLabel={
                  metric.tooltip ? `${metric.label}, ${metric.tooltip}` : metric.label
                }
                style={styles.metric}
                hitSlop={6}
                onPress={() => onMetricPress(metric.tooltip)}
              >
                <Icon name={metric.icon} size={13} color={colors.ter} strokeWidth={1.9} />
                <Text style={styles.metricText}>{metric.label}</Text>
              </Pressable>
            ) : null}

            <Pressable
              testID="travel-card-detail"
              accessibilityRole="button"
              accessibilityLabel={`${spot.title} ${DETAIL_LABEL}`}
              style={({ pressed }) => [styles.detail, pressed && styles.pressed]}
              hitSlop={6}
              onPress={onDetail}
            >
              <Text style={styles.detailText}>{DETAIL_LABEL}</Text>
              <Icon name="chevron-right" size={12} color={colors.ter} strokeWidth={2} />
            </Pressable>
          </View>
        </View>
      </Pressable>

      <Pressable
        testID={`travel-card-save-${spot.contentId}`}
        accessibilityRole="button"
        accessibilityLabel={saved ? "저장 해제" : "저장"}
        accessibilityState={{ selected: saved }}
        style={styles.fav}
        hitSlop={8}
        onPress={async () => {
          const result = await toggle();
          if (result !== null) onSaveToggle(result);
        }}
      >
        <Icon
          name={saved ? "heart-fill" : "heart"}
          size={17}
          color={saved ? colors.accent : colors.ter}
          strokeWidth={1.9}
        />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glassFill,
  },
  tap: { flex: 1, flexDirection: "row", gap: 12, padding: 10 },
  pressed: { opacity: 0.7 },
  thumb: { width: 92, height: 92 },
  copy: { flex: 1, minWidth: 0, justifyContent: "center" },
  head: { flexDirection: "row", alignItems: "center", gap: 7, paddingRight: 26 },
  badge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  badgeFocused: { backgroundColor: colors.accent },
  badgeText: { fontSize: 11, fontWeight: "800", color: colors.bg },
  badgeTextFocused: { color: colors.onImage },
  title: { flex: 1, minWidth: 0, fontSize: 15, fontWeight: "700", letterSpacing: -0.35, color: colors.ink },
  region: { marginTop: 3, fontSize: 12.5, letterSpacing: -0.2, color: colors.sec },
  distance: { fontWeight: "700", color: colors.ink },
  row: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 7 },
  metric: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    height: 22,
    paddingHorizontal: 8,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.fill,
  },
  metricText: { fontSize: 11.5, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  detail: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    height: 24,
    marginLeft: "auto",
    paddingLeft: 10,
    paddingRight: 8,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
  },
  detailText: { fontSize: 11.5, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  fav: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 26,
    height: 26,
    alignItems: "center",
    justifyContent: "center",
  },
});
```

- [ ] **Step 4: `chevron-right` 아이콘을 확인한다**

```bash
cd mobile && grep -n "chevron-right" src/components/Icon.tsx
```

없으면 추가한다: `"chevron-right": <Path d="M9.5 6l6 6-6 6" />,`

- [ ] **Step 5: 통과를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/SpotCard.test.tsx && npm run typecheck
```

Expected: PASS (9 tests)

---

### Task 8: `SpotCarousel` — 좌우 스냅 + 진행 바

**Files:**
- Create: `mobile/src/features/travel/components/SpotCarousel.tsx`
- Test: `mobile/src/features/travel/components/__tests__/SpotCarousel.test.tsx`

**Interfaces:**
- Consumes: `SpotCard` · `CARD_STRIDE` · `CARD_WIDTH` (Task 7)
- Produces:
  - `SpotCarousel` with props
    ```ts
    interface Props {
      spots: TravelSpot[];
      tagBasis: string | null;
      focusedIndex: number;
      origin: LatLng | null;
      onFocusChange: (index: number) => void;
      onDetail: (spot: TravelSpot) => void;
      onSaveToggle: (saved: boolean) => void;
      onMetricPress: (tooltip: string) => void;
    }
    ```
  - `carouselIndexAt(offsetX: number, count: number): number` — 오프셋을 인덱스로
  - `progressRatio(focusedIndex: number, count: number): number` — 진행 바 폭 퍼센트

두 순수 함수를 밖으로 뺀 이유: 진행 바를 `props.style` 로 단언하면 `StyleSheet.create`
의 반환 형태에 테스트가 묶인다. 계산만 따로 검사하고 스타일은 손대지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```tsx
import renderer, { act } from "react-test-renderer";
import { FlatList } from "react-native";
import {
  SpotCarousel,
  carouselIndexAt,
  progressRatio,
} from "@/features/travel/components/SpotCarousel";
import { CARD_STRIDE } from "@/features/travel/components/SpotCard";
import type { TravelSpot } from "@/features/travel/api";

jest.mock("@/features/saved/hooks/use-save-optimistic", () => ({
  useSaveOptimistic: () => ({ saved: false, toggle: jest.fn() }),
}));
jest.mock("@/features/spots/queries", () => ({ prefetchSpot: jest.fn() }));

const spots: TravelSpot[] = [1, 2, 3].map((n) => ({
  contentId: String(n),
  title: `장소 ${n}`,
  regionLabel: "제주시",
  imageUrl: null,
  tag: "한산",
  lat: 33 + n / 100,
  lng: 126,
}));

const base = {
  spots,
  tagBasis: null,
  focusedIndex: 0,
  origin: null,
  onFocusChange: jest.fn(),
  onDetail: jest.fn(),
  onSaveToggle: jest.fn(),
  onMetricPress: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof SpotCarousel>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<SpotCarousel {...base} {...props} />);
  });
  return tree!;
}

describe("carouselIndexAt", () => {
  it("반 칸을 넘기면 다음 카드로 센다", () => {
    expect(carouselIndexAt(0, 3)).toBe(0);
    expect(carouselIndexAt(CARD_STRIDE * 0.6, 3)).toBe(1);
    expect(carouselIndexAt(CARD_STRIDE * 2, 3)).toBe(2);
  });

  it("목록 밖으로 나가지 않는다", () => {
    expect(carouselIndexAt(-40, 3)).toBe(0);
    expect(carouselIndexAt(CARD_STRIDE * 9, 3)).toBe(2);
    expect(carouselIndexAt(0, 0)).toBe(0);
  });
});

describe("progressRatio", () => {
  it("보고 있는 위치를 퍼센트로 준다", () => {
    expect(progressRatio(0, 8)).toBeCloseTo(12.5);
    expect(progressRatio(7, 8)).toBe(100);
  });

  it("결과가 없으면 0이다", () => {
    expect(progressRatio(0, 0)).toBe(0);
  });
});

describe("SpotCarousel", () => {
  it("카드마다 스냅 오프셋을 준다", () => {
    const list = mount().root.findByType(FlatList);

    expect(list.props.snapToOffsets).toEqual([0, CARD_STRIDE, CARD_STRIDE * 2]);
  });

  it("멈춘 자리를 인덱스로 알린다", () => {
    const onFocusChange = jest.fn();
    const list = mount({ onFocusChange }).root.findByType(FlatList);

    act(() =>
      list.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: CARD_STRIDE } } }),
    );

    expect(onFocusChange).toHaveBeenCalledWith(1);
  });

  it("같은 인덱스로는 다시 알리지 않는다", () => {
    const onFocusChange = jest.fn();
    const list = mount({ onFocusChange }).root.findByType(FlatList);

    act(() => list.props.onMomentumScrollEnd({ nativeEvent: { contentOffset: { x: 4 } } }));

    expect(onFocusChange).not.toHaveBeenCalled();
  });

  it("결과가 있으면 진행 바를 그린다", () => {
    expect(mount().root.findAllByProps({ testID: "travel-progress-fill" }).length).toBeGreaterThan(
      0,
    );
  });

  it("결과가 없으면 아무것도 그리지 않는다", () => {
    expect(mount({ spots: [] }).root.findAllByType(FlatList)).toHaveLength(0);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/SpotCarousel.test.tsx
```

Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현한다**

```tsx
import { useCallback, useMemo, useRef } from "react";
import {
  FlatList,
  View,
  StyleSheet,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { CARD_STRIDE, CARD_WIDTH, SpotCard } from "@/features/travel/components/SpotCard";
import { spotDistanceKm } from "@/features/travel/lib/distance";
import type { LatLng } from "@/features/map/lib/geo";
import type { TravelSpot } from "@/features/travel/api";
import { colors, spacing } from "@/constants/theme";

export const CAROUSEL_BLOCK_PX = 112 + 9 + 3 + 11;

export function carouselIndexAt(offsetX: number, count: number): number {
  if (count <= 0) return 0;
  const raw = Math.round(offsetX / CARD_STRIDE);
  return Math.min(count - 1, Math.max(0, raw));
}

export function progressRatio(focusedIndex: number, count: number): number {
  if (count <= 0) return 0;
  return ((focusedIndex + 1) / count) * 100;
}

interface Props {
  spots: TravelSpot[];
  tagBasis: string | null;
  focusedIndex: number;
  origin: LatLng | null;
  onFocusChange: (index: number) => void;
  onDetail: (spot: TravelSpot) => void;
  onSaveToggle: (saved: boolean) => void;
  onMetricPress: (tooltip: string) => void;
}

export function SpotCarousel({
  spots,
  tagBasis,
  focusedIndex,
  origin,
  onFocusChange,
  onDetail,
  onSaveToggle,
  onMetricPress,
}: Props) {
  const listRef = useRef<FlatList<TravelSpot>>(null);
  const reported = useRef(focusedIndex);

  const offsets = useMemo(() => spots.map((_, index) => index * CARD_STRIDE), [spots]);

  const onMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const next = carouselIndexAt(event.nativeEvent.contentOffset.x, spots.length);
      if (next === reported.current) return;
      reported.current = next;
      onFocusChange(next);
    },
    [spots.length, onFocusChange],
  );

  if (spots.length === 0) return null;

  const ratio = progressRatio(focusedIndex, spots.length);

  return (
    <View testID="travel-carousel">
      <FlatList
        ref={listRef}
        data={spots}
        horizontal
        showsHorizontalScrollIndicator={false}
        decelerationRate="fast"
        snapToOffsets={offsets}
        snapToAlignment="start"
        contentContainerStyle={styles.content}
        keyExtractor={(spot) => spot.contentId}
        getItemLayout={(_, index) => ({
          length: CARD_WIDTH,
          offset: index * CARD_STRIDE,
          index,
        })}
        onMomentumScrollEnd={onMomentumScrollEnd}
        renderItem={({ item, index }) => (
          <SpotCard
            spot={item}
            index={index}
            tagBasis={tagBasis}
            distanceKm={spotDistanceKm(item, origin)}
            focused={index === focusedIndex}
            onDetail={() => onDetail(item)}
            onSaveToggle={onSaveToggle}
            onMetricPress={onMetricPress}
          />
        )}
      />

      <View style={styles.track}>
        <View testID="travel-progress-fill" style={[styles.fill, { width: `${ratio}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: 10, paddingHorizontal: spacing.md },
  track: {
    height: 3,
    marginTop: 9,
    marginHorizontal: spacing.md + 4,
    marginBottom: 11,
    borderRadius: 2,
    backgroundColor: colors.fillStrong,
    overflow: "hidden",
  },
  fill: { height: 3, minWidth: 14, borderRadius: 2, backgroundColor: colors.onDim },
});
```

`listRef` 는 다음 태스크에서 핀 탭에 반응해 스크롤할 때 쓴다. 지금은 잡아만 둔다.

- [ ] **Step 4: 핀 탭으로 스크롤할 수 있게 ref 를 밖으로 연다**

`Props` 에 `scrollToIndex?: number | null` 을 더하고, 값이 바뀌면 그 자리로 옮긴다.
`SpotCarousel` 안의 `import { useCallback, useEffect, useMemo, useRef }` 로 바꾸고
`offsets` 선언 아래에 넣는다.

```tsx
  useEffect(() => {
    if (scrollToIndex === null || scrollToIndex === undefined) return;
    if (scrollToIndex < 0 || scrollToIndex >= spots.length) return;
    reported.current = scrollToIndex;
    listRef.current?.scrollToOffset({ offset: scrollToIndex * CARD_STRIDE, animated: true });
  }, [scrollToIndex, spots.length]);
```

- [ ] **Step 5: 통과를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/SpotCarousel.test.tsx && npm run typecheck
```

Expected: PASS (7 tests)

---

### Task 9: `TravelDock` — 칩 행 + 입력 필드

**Files:**
- Create: `mobile/src/features/travel/components/TravelDock.tsx`
- Test: `mobile/src/features/travel/components/__tests__/TravelDock.test.tsx`

**Interfaces:**
- Consumes: `DockChip` (Task 5)
- Produces: `TravelDock` with props
  ```ts
  interface Props {
    value: string;
    photo: PhotoUpload | null;
    chips: DockChip[];
    disabled: boolean;
    placeholder: string;
    locationAskable: boolean;
    bottom: number;
    onChange: (text: string) => void;
    onChipPress: (chip: DockChip) => void;
    onShoot: () => void;
    onClearAttach: () => void;
    onSubmit: () => void;
    onFocus: () => void;
    onAskLocation: () => void;
  }
  ```

`사진` 칩과 촬영 아이콘의 역할 분담: **칩 = 앨범, 필드 안 아이콘 = 촬영.** 앨범 열기는
`onChipPress({kind:"photo"})` 로 화면이 받는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```tsx
import renderer, { act } from "react-test-renderer";
import { Text, TextInput } from "react-native";
import { TravelDock } from "@/features/travel/components/TravelDock";
import type { DockChip } from "@/features/travel/lib/dock-chips";

const chips: DockChip[] = [
  { kind: "photo" },
  { kind: "context", title: "성산일출봉", expanded: false },
  { kind: "query", chip: { kind: "question", label: "사람 적은 곳만", question: "사람 적은 곳" } },
];

const base = {
  value: "",
  photo: null,
  chips,
  disabled: false,
  placeholder: "어디로 갈지 말해보세요",
  locationAskable: false,
  bottom: 83,
  onChange: jest.fn(),
  onChipPress: jest.fn(),
  onShoot: jest.fn(),
  onClearAttach: jest.fn(),
  onSubmit: jest.fn(),
  onFocus: jest.fn(),
  onAskLocation: jest.fn(),
};

function mount(props: Partial<React.ComponentProps<typeof TravelDock>> = {}) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<TravelDock {...base} {...props} />);
  });
  return tree!;
}

const flatten = (node: unknown): string =>
  Array.isArray(node)
    ? node.map(flatten).join("")
    : typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";

const texts = (tree: renderer.ReactTestRenderer): string =>
  tree.root
    .findAllByType(Text)
    .map((n) => flatten(n.props.children))
    .join("");

function byId(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAllByProps({ testID: id }).find((n) => typeof n.props.onPress === "function");
}

describe("TravelDock", () => {
  it("칩을 순서대로 그린다", () => {
    const shown = texts(mount());

    expect(shown).toContain("사진");
    expect(shown).toContain("성산일출봉");
    expect(shown).toContain("사람 적은 곳만");
  });

  it("칩을 누르면 그 칩을 그대로 올린다", () => {
    const onChipPress = jest.fn();
    const tree = mount({ onChipPress });

    act(() => byId(tree, "travel-chip-0")!.props.onPress());

    expect(onChipPress).toHaveBeenCalledWith({ kind: "photo" });
  });

  it("첨부가 있으면 배너가 칩 행을 대신한다", () => {
    const tree = mount({ photo: { uri: "file://a.jpg", name: "a.jpg", type: "image/jpeg" } });

    expect(texts(tree)).toContain("이 사진 같은 분위기로 찾아요");
    expect(texts(tree)).not.toContain("사람 적은 곳만");
  });

  it("입력이 있으면 전송이 살아난다", () => {
    const onSubmit = jest.fn();
    const tree = mount({ value: "제주" , onSubmit });

    act(() => byId(tree, "travel-send")!.props.onPress());

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("빈 입력에서는 전송을 막는다", () => {
    expect(byId(mount(), "travel-send")!.props.disabled).toBe(true);
  });

  it("응답을 기다리는 동안 입력을 잠근다", () => {
    const input = mount({ disabled: true }).root.findByType(TextInput);

    expect(input.props.editable).toBe(false);
  });

  it("권한을 아직 묻지 않았을 때만 프라이머를 낸다", () => {
    expect(byId(mount(), "travel-ask-location")).toBeUndefined();
    expect(byId(mount({ locationAskable: true }), "travel-ask-location")).toBeDefined();
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/TravelDock.test.tsx
```

Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현한다**

```tsx
import { ScrollView, Pressable, View, Text, TextInput, StyleSheet } from "react-native";
import { Image } from "expo-image";
import { Icon } from "@/components/Icon";
import type { DockChip } from "@/features/travel/lib/dock-chips";
import type { PhotoUpload } from "@/features/travel/api";
import { colors, radii, spacing } from "@/constants/theme";

export const ATTACH_HEADLINE = "이 사진 같은 분위기로 찾아요";
export const ATTACH_NOTICE = "사진은 저장하지 않아요";
export const PHOTO_CHIP_LABEL = "사진";
export const LOCATION_PRIMER_TEXT = "위치를 켜면 내 근처로 물어볼 수 있어요";
export const LOCATION_PRIMER_ACTION = "켜기";

interface Props {
  value: string;
  photo: PhotoUpload | null;
  chips: DockChip[];
  disabled: boolean;
  placeholder: string;
  locationAskable: boolean;
  bottom: number;
  onChange: (text: string) => void;
  onChipPress: (chip: DockChip) => void;
  onShoot: () => void;
  onClearAttach: () => void;
  onSubmit: () => void;
  onFocus: () => void;
  onAskLocation: () => void;
}

function chipLabel(chip: DockChip): string {
  if (chip.kind === "photo") return PHOTO_CHIP_LABEL;
  if (chip.kind === "context") return chip.expanded ? chip.title : `${chip.title} 근처`;
  return chip.chip.label;
}

export function TravelDock({
  value,
  photo,
  chips,
  disabled,
  placeholder,
  locationAskable,
  bottom,
  onChange,
  onChipPress,
  onShoot,
  onClearAttach,
  onSubmit,
  onFocus,
  onAskLocation,
}: Props) {
  const ready = !disabled && (value.trim().length > 0 || photo !== null);

  return (
    <View style={[styles.root, { bottom }]}>
      {locationAskable && photo === null ? (
        <Pressable
          testID="travel-ask-location"
          accessibilityRole="button"
          style={({ pressed }) => [styles.primer, pressed && styles.pressed]}
          onPress={onAskLocation}
        >
          <Icon name="location" size={15} color={colors.sec} strokeWidth={1.9} />
          <Text style={styles.primerText}>{LOCATION_PRIMER_TEXT}</Text>
          <Text style={styles.primerAction}>{LOCATION_PRIMER_ACTION}</Text>
        </Pressable>
      ) : null}

      {photo ? (
        <View style={styles.attach} testID="travel-attach-banner">
          <Image source={{ uri: photo.uri }} style={styles.attachThumb} contentFit="cover" />
          <View style={styles.attachCopy}>
            <Text style={styles.attachTitle}>{ATTACH_HEADLINE}</Text>
            <Text style={styles.attachNote}>{ATTACH_NOTICE}</Text>
          </View>
          <Pressable
            testID="travel-attach-clear"
            accessibilityRole="button"
            accessibilityLabel="첨부 사진 제거"
            hitSlop={8}
            onPress={onClearAttach}
          >
            <Icon name="close" size={16} color={colors.ter} strokeWidth={2} />
          </Pressable>
        </View>
      ) : (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.chips}
        >
          {chips.map((chip, index) => (
            <Pressable
              key={`${chip.kind}-${chipLabel(chip)}`}
              testID={`travel-chip-${index}`}
              accessibilityRole="button"
              accessibilityLabel={chipLabel(chip)}
              style={({ pressed }) => [
                styles.chip,
                chip.kind === "context" && styles.chipContext,
                pressed && styles.pressed,
              ]}
              onPress={() => onChipPress(chip)}
            >
              {chip.kind === "photo" ? (
                <Icon name="image" size={15} color={colors.accentText} strokeWidth={1.9} />
              ) : null}
              {chip.kind === "context" ? (
                <Icon name="target" size={14} color={colors.accentText} strokeWidth={1.9} />
              ) : null}
              <Text style={[styles.chipText, chip.kind === "context" && styles.chipTextContext]}>
                {chipLabel(chip)}
              </Text>
              {chip.kind === "context" && chip.expanded ? (
                <Icon name="close" size={12} color={colors.accentText} strokeWidth={2.4} />
              ) : null}
            </Pressable>
          ))}
        </ScrollView>
      )}

      <View style={styles.field}>
        <Icon name="search" size={17} color={colors.ter} strokeWidth={1.9} />
        <TextInput
          testID="travel-input"
          style={styles.input}
          value={value}
          onChangeText={onChange}
          onFocus={onFocus}
          placeholder={placeholder}
          placeholderTextColor={colors.ter}
          returnKeyType="send"
          onSubmitEditing={onSubmit}
          editable={!disabled}
        />
        <Pressable
          testID="travel-shoot"
          accessibilityRole="button"
          accessibilityLabel="사진 촬영"
          style={styles.iconButton}
          hitSlop={4}
          onPress={onShoot}
          disabled={disabled}
        >
          <Icon name="camera" size={17} color={colors.sec} strokeWidth={1.9} />
        </Pressable>
        <Pressable
          testID="travel-send"
          accessibilityRole="button"
          accessibilityLabel="보내기"
          style={[styles.send, ready && styles.sendReady]}
          onPress={onSubmit}
          disabled={!ready}
        >
          <Icon
            name="arrow-up"
            size={17}
            color={ready ? colors.onImage : colors.ter}
            strokeWidth={2.3}
          />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { position: "absolute", left: 0, right: 0, paddingHorizontal: spacing.md, paddingBottom: 12 },
  pressed: { opacity: 0.7 },
  primer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    height: 38,
    marginBottom: 9,
    paddingHorizontal: spacing.md,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.glassFill,
  },
  primerText: { flex: 1, fontSize: 12.5, fontWeight: "700", letterSpacing: -0.2, color: colors.sec },
  primerAction: { fontSize: 11.5, fontWeight: "800", color: colors.accentText },
  attach: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 9,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: "rgba(255,59,83,0.32)",
    backgroundColor: colors.accentFill,
  },
  attachThumb: { width: 46, height: 46, borderRadius: 11 },
  attachCopy: { flex: 1 },
  attachTitle: { fontSize: 13.5, fontWeight: "700", letterSpacing: -0.2, color: colors.ink },
  attachNote: { marginTop: 3, fontSize: 11.5, color: colors.sec },
  chips: { gap: 7, paddingBottom: 9 },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 33,
    paddingHorizontal: 14,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
  },
  chipContext: { borderColor: "rgba(255,59,83,0.38)", backgroundColor: colors.accentFill },
  chipText: { fontSize: 13, fontWeight: "600", letterSpacing: -0.2, color: colors.ink },
  chipTextContext: { color: colors.accentText, fontWeight: "700" },
  field: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    height: 46,
    paddingLeft: 13,
    paddingRight: 6,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raiseStrong,
  },
  input: {
    flex: 1,
    minWidth: 0,
    padding: 0,
    fontSize: 15,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: colors.ink,
  },
  iconButton: { width: 30, height: 32, alignItems: "center", justifyContent: "center" },
  send: {
    width: 32,
    height: 32,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.fillStrong,
  },
  sendReady: { backgroundColor: colors.accent },
});
```

- [ ] **Step 4: `target` 아이콘을 확인한다**

```bash
cd mobile && grep -n '"target"' src/components/Icon.tsx
```

없으면 추가한다: `target: <><Circle cx="12" cy="12" r="3" /><Circle cx="12" cy="12" r="8" /></>,`

- [ ] **Step 5: 통과를 확인한다**

```bash
cd mobile && npx jest src/features/travel/components/__tests__/TravelDock.test.tsx && npm run typecheck
```

Expected: PASS (7 tests)

---

### Task 10: 화면 재작성 — `travel.tsx`

**Files:**
- Modify: `mobile/src/app/(tabs)/travel.tsx` (전면 재작성)
- Modify: `mobile/src/__tests__/travel-screen.test.tsx` (**전면 재작성** — 64개 테스트, 17 describe)
- Test: `mobile/src/features/travel/lib/__tests__/screen-layout.test.ts` (신규)
- Create: `mobile/src/features/travel/lib/screen-layout.ts`

**⚠️ 계획 정정 (2026-08-08, Task 1 리뷰에서 발견).** 이 계획은 원래 "화면 단위 테스트는
목킹 비용이 커서 쓰지 않는다"고 적었으나, **`mobile/src/__tests__/travel-screen.test.tsx`
가 이미 존재하고 목킹이 전부 풀려 있다** (`KakaoWebMap` · `expo-router` ·
`react-native-safe-area-context` · `askAgent` · `use-save-optimistic` · `prefetchSpot` ·
`pick-travel-photo`). 이 파일을 지우고 넘어가면 화면 회귀 커버리지 64개가 통째로
사라진다. **목킹 블록은 그대로 재사용하고 테스트 본문만 새 구조에 맞춰 다시 쓴다.**

살아남는 describe (새 구조에 맞게 고쳐 쓴다):
`photo attach` · `new chat` · `refine chips` · `zero-result turn` · `photo answer` ·
`follow-up context` · `map` · `retry` · `save toast` · `nearby action` · `starter chips`

없어지는 describe (해당 동작이 폐기됐다):
`empty state`(인사말·마스코트) · `anchored follow-ups`(앵커 모드) ·
`anchor handed over from a spot detail` · `refine chips in scrollback`(이력 없음) ·
`empty-screen start`(퀵액션 그리드)

새로 필요한 describe: `answer bar`(헤드라인/펼침) · `carousel focus`(스와이프 → 문맥 전환) ·
`pin tap`(핀 → 캐러셀 스크롤)

`GREETING`/`TAGLINE`/`DOUBLE_TAP_MS`/`AskComposer` 상수 임포트는 전부 사라진다.
`mobile/src/features/travel/stores/__tests__/conversation-store.test.ts:6` 의
`"4곳 찾았어요"` 픽스처 문구도 새 답변 형태로 갱신한다(단언은 없고 픽스처일 뿐이다).

**Interfaces:**
- Consumes: `AnswerBar` · `SpotCarousel` · `CAROUSEL_BLOCK_PX` · `TravelDock` · `dockChips` · `DockChip`
- Produces:
  - `dockBottomPx(tabBarContentPx: number, safeBottomPx: number): number`
  - `mapFitPadding(input: { safeTop: number; dockHeight: number }): { top: number; right: number; bottom: number; left: number }`

- [ ] **Step 1: 레이아웃 계산의 테스트를 쓴다**

```ts
import { dockBottomPx, mapFitPadding } from "@/features/travel/lib/screen-layout";

describe("dockBottomPx", () => {
  it("탭 바 높이에 하단 인셋을 한 번만 더한다", () => {
    expect(dockBottomPx(49, 34)).toBe(83);
    expect(dockBottomPx(49, 0)).toBe(49);
  });
});

describe("mapFitPadding", () => {
  it("독과 캐러셀이 덮는 만큼 아래를 비운다", () => {
    const pad = mapFitPadding({ safeTop: 59, dockHeight: 220 });

    expect(pad.bottom).toBe(220 + 24);
    expect(pad.top).toBe(59 + 96);
    expect(pad.left).toBe(40);
    expect(pad.right).toBe(40);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

```bash
cd mobile && npx jest src/features/travel/lib/__tests__/screen-layout.test.ts
```

Expected: FAIL — 모듈 없음

- [ ] **Step 3: `screen-layout.ts` 를 만든다**

```ts
export const TAB_BAR_CONTENT_PX = 49;
export const FIT_TOP_PAD = 96;
export const FIT_SIDE_PAD = 40;
export const FIT_BOTTOM_MARGIN = 24;

export function dockBottomPx(tabBarContentPx: number, safeBottomPx: number): number {
  return tabBarContentPx + safeBottomPx;
}

export function mapFitPadding({
  safeTop,
  dockHeight,
}: {
  safeTop: number;
  dockHeight: number;
}): { top: number; right: number; bottom: number; left: number } {
  return {
    top: safeTop + FIT_TOP_PAD,
    right: FIT_SIDE_PAD,
    bottom: dockHeight + FIT_BOTTOM_MARGIN,
    left: FIT_SIDE_PAD,
  };
}
```

- [ ] **Step 4: `travel.tsx` 를 통째로 교체한다**

```tsx
import { useCallback, useMemo, useState } from "react";
import { View, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Toast } from "@/components/Toast";
import { KakaoWebMap } from "@/features/map/components/KakaoWebMap";
import { AnswerBar } from "@/features/travel/components/AnswerBar";
import { SpotCarousel, CAROUSEL_BLOCK_PX } from "@/features/travel/components/SpotCarousel";
import { TravelDock } from "@/features/travel/components/TravelDock";
import { SearchPulse } from "@/features/travel/components/SearchPulse";
import { useNearbyCoords } from "@/features/travel/hooks/use-nearby-coords";
import { useAskAgentMutation } from "@/features/travel/queries";
import { useConversation } from "@/features/travel/stores/conversation-store";
import {
  agentErrorMessage,
  PHOTO_PICK_FAILED,
  PHOTO_SHOOT_FAILED,
} from "@/features/travel/lib/agent-errors";
import { composeQuestion, anchorQuestion, MY_LOCATION } from "@/features/travel/lib/question";
import { contextFrom } from "@/features/travel/lib/conversation-context";
import { dockChips, type DockChip } from "@/features/travel/lib/dock-chips";
import { pendingSteps } from "@/features/travel/lib/pending-steps";
import { coordsOf } from "@/features/travel/lib/distance";
import { bounds, center, pinsFrom, placed } from "@/features/travel/lib/spot-geo";
import {
  dockBottomPx,
  mapFitPadding,
  TAB_BAR_CONTENT_PX,
} from "@/features/travel/lib/screen-layout";
import { pickTravelPhoto, shootTravelPhoto } from "@/features/travel/usecases/pick-travel-photo";
import type { AskInput, PhotoUpload, TravelSpot } from "@/features/travel/api";
import { colors } from "@/constants/theme";

const SAVE_COMPLETE = "여행지를 저장했어요";
const UNSAVE_COMPLETE = "여행지 저장을 해제했어요";
const TOAST_LIFT = 12;
const DOCK_BASE_PX = 46 + 12 + 33 + 9;
const NO_SPOTS: TravelSpot[] = [];

export const ASK_PLACEHOLDER = "어디로 갈지 말해보세요";
export const ATTACHED_PLACEHOLDER = "지역이나 조건을 덧붙여 보세요";

export default function TravelScreen() {
  const insets = useSafeAreaInsets();
  const [draft, setDraft] = useState("");
  const [photo, setPhoto] = useState<PhotoUpload | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [expandedAnswer, setExpandedAnswer] = useState(false);
  const [expandedChips, setExpandedChips] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [scrollTo, setScrollTo] = useState<number | null>(null);

  const turns = useConversation((s) => s.turns);
  const busy = useConversation((s) => s.busy);
  const startTurn = useConversation((s) => s.start);
  const retryTurn = useConversation((s) => s.retry);
  const resolveTurn = useConversation((s) => s.resolve);
  const failTurn = useConversation((s) => s.fail);
  const clearTurns = useConversation((s) => s.clear);
  const nextTurnId = useConversation((s) => s.nextTurnId);

  const { coords, askable: locationAskable, ask: askLocation } = useNearbyCoords();
  const ask = useAskAgentMutation();

  const turn = turns.length > 0 ? turns[turns.length - 1] : null;
  const answer = turn?.status === "done" ? turn.answer : null;
  const spots = answer?.spots ?? NO_SPOTS;
  const focused = spots[focusedIndex] ?? null;

  const mapSpots = useMemo(() => placed(spots), [spots]);
  const pins = useMemo(() => pinsFrom(mapSpots), [mapSpots]);

  const dockHeight =
    dockBottomPx(TAB_BAR_CONTENT_PX, insets.bottom) +
    DOCK_BASE_PX +
    (spots.length > 0 ? CAROUSEL_BLOCK_PX : 0);

  const fit = useMemo(() => {
    const box = bounds(mapSpots);
    if (!box) return null;
    return { ...box, pad: mapFitPadding({ safeTop: insets.top, dockHeight }) };
  }, [mapSpots, insets.top, dockHeight]);

  const focus = useMemo(() => {
    if (focused) return coordsOf(focused) ?? center(mapSpots) ?? coords;
    return center(mapSpots) ?? coords;
  }, [focused, mapSpots, coords]);

  const run = useCallback(
    (id: string, input: Omit<AskInput, "coords">) => {
      ask.mutate(
        { ...input, coords },
        {
          onSuccess: (result) => resolveTurn(id, result),
          onError: (error) => failTurn(id, agentErrorMessage(error)),
        },
      );
    },
    [ask, coords, resolveTurn, failTurn],
  );

  const beginTurn = useCallback(() => {
    setExpandedAnswer(false);
    setExpandedChips(false);
    setFocusedIndex(0);
    setScrollTo(null);
  }, []);

  const submit = useCallback(
    (text: string, attached: PhotoUpload | null) => {
      if (busy) return;
      const question = composeQuestion(text, attached !== null);
      if (!question) return;
      const request = text.trim();
      const id = nextTurnId();
      const context = contextFrom(answer, focused?.contentId ?? null);
      startTurn({ id, question, request, photo: attached, context });
      setDraft("");
      setPhoto(null);
      beginTurn();
      run(id, { question: request, photo: attached, context });
    },
    [busy, nextTurnId, answer, focused, startTurn, beginTurn, run],
  );

  const onChipPress = useCallback(
    async (chip: DockChip) => {
      if (chip.kind === "photo") {
        try {
          const picked = await pickTravelPhoto();
          if (picked) setPhoto(picked);
        } catch {
          setToast(PHOTO_PICK_FAILED);
        }
        return;
      }
      if (chip.kind === "context") {
        setExpandedChips((open) => !open);
        return;
      }
      if (busy) return;
      const inner = chip.chip;
      if (inner.kind === "question") {
        submit(inner.question, null);
        return;
      }
      const id = nextTurnId();
      if (inner.kind === "anchor") {
        if (!focused && !coords) return;
        const anchor = focused
          ? { contentId: focused.contentId, action: inner.action }
          : { action: inner.action };
        startTurn({
          id,
          question: anchorQuestion(focused?.title ?? MY_LOCATION, inner.label),
          request: "",
          photo: null,
          anchor,
        });
        beginTurn();
        run(id, { anchor });
        return;
      }
      if (inner.kind === "intent") {
        startTurn({ id, question: inner.label, request: "", photo: null, intent: inner.intent });
        beginTurn();
        run(id, { intent: inner.intent });
        return;
      }
      const intent = answer?.intent ?? null;
      if (!intent) return;
      const attached = turn?.photo ?? null;
      startTurn({
        id,
        question: inner.label,
        request: "",
        photo: attached,
        intent,
        patch: inner.patch,
      });
      beginTurn();
      run(id, { photo: attached, intent, patch: inner.patch });
    },
    [busy, submit, nextTurnId, focused, answer, turn, startTurn, beginTurn, run],
  );

  const onShoot = useCallback(async () => {
    try {
      const picked = await shootTravelPhoto();
      if (picked) setPhoto(picked);
    } catch {
      setToast(PHOTO_SHOOT_FAILED);
    }
  }, []);

  const onNewChat = useCallback(() => {
    clearTurns();
    setDraft("");
    setPhoto(null);
    beginTurn();
  }, [clearTurns, beginTurn]);

  const onRetry = useCallback(() => {
    if (busy || !turn) return;
    retryTurn(turn.id);
    beginTurn();
    run(turn.id, {
      question: turn.request,
      photo: turn.photo,
      intent: turn.intent,
      patch: turn.patch,
      anchor: turn.anchor,
      context: turn.context,
    });
  }, [busy, turn, retryTurn, beginTurn, run]);

  const onPinTap = useCallback(
    (contentId: string) => {
      const at = spots.findIndex((s) => s.contentId === contentId);
      if (at < 0) return;
      setFocusedIndex(at);
      setScrollTo(at);
    },
    [spots],
  );

  const onFocusChange = useCallback((index: number) => {
    setFocusedIndex(index);
    setExpandedChips(false);
    setScrollTo(null);
  }, []);

  const chips = dockChips({
    answer,
    focused,
    expanded: expandedChips,
    hasCoords: coords !== null,
    hasCrowd: focused?.hasCrowd === true,
  });

  const placeholder = photo
    ? ATTACHED_PLACEHOLDER
    : focused
      ? `${focused.title}에 대해 물어보기`
      : ASK_PLACEHOLDER;

  const step = turn?.status === "pending" ? (pendingSteps(turn)[0]?.label ?? null) : null;

  return (
    <View style={styles.root}>
      <KakaoWebMap
        center={focus}
        fit={fit}
        pins={pins}
        anchorId={focused?.contentId ?? null}
        userLocation={coords}
        onPinTap={onPinTap}
      />

      <SearchPulse active={busy} bottom={dockHeight} />

      {turn ? (
        <AnswerBar
          question={turn.question}
          answer={answer?.answer ?? null}
          photoUri={turn.photo?.uri ?? null}
          step={step}
          errorMessage={turn.status === "failed" ? turn.errorMessage : null}
          expanded={expandedAnswer || spots.length === 0}
          top={insets.top + 7}
          onToggle={() => setExpandedAnswer((open) => !open)}
          onClose={onNewChat}
          onRetry={onRetry}
        />
      ) : null}

      <View
        style={[
          styles.stack,
          { bottom: dockBottomPx(TAB_BAR_CONTENT_PX, insets.bottom) + DOCK_BASE_PX },
        ]}
        pointerEvents="box-none"
      >
        <SpotCarousel
          spots={spots}
          tagBasis={answer?.tagBasis ?? null}
          focusedIndex={focusedIndex}
          scrollToIndex={scrollTo}
          origin={coords}
          onFocusChange={onFocusChange}
          onDetail={(spot: TravelSpot) => router.push(`/spots/${spot.contentId}`)}
          onSaveToggle={(saved) => setToast(saved ? SAVE_COMPLETE : UNSAVE_COMPLETE)}
          onMetricPress={(tooltip) => {
            if (tooltip) setToast(tooltip);
          }}
        />
      </View>

      <TravelDock
        value={draft}
        photo={photo}
        chips={chips}
        disabled={busy}
        placeholder={placeholder}
        locationAskable={locationAskable}
        bottom={dockBottomPx(TAB_BAR_CONTENT_PX, insets.bottom)}
        onChange={setDraft}
        onChipPress={(chip) => void onChipPress(chip)}
        onShoot={() => void onShoot()}
        onClearAttach={() => setPhoto(null)}
        onSubmit={() => submit(draft, photo)}
        onFocus={() => setExpandedChips(false)}
        onAskLocation={() => void askLocation()}
      />

      <Toast
        testID="travel-toast"
        message={toast}
        bottom={dockHeight + TOAST_LIFT}
        onHide={() => setToast(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  stack: { position: "absolute", left: 0, right: 0 },
});
```

캐러셀 블록은 독 **위**에 떠야 하므로 `bottom` 에 독 높이(`DOCK_BASE_PX`)를 더한다.
절대 배치에 `marginBottom` 을 얹지 않는다 — `bottom` 과 마진이 함께 걸리면 어느 쪽이
움직인 건지 읽히지 않는다.

- [ ] **Step 5: 검증**

```bash
cd mobile && npm run lint && npm run typecheck && npm test
```

Expected: 타입·린트 통과. 폐기 대상 컴포넌트의 기존 테스트가 아직 남아 있어 실패할 수
있다 — 다음 태스크에서 지운다. 여기서는 **새 테스트가 전부 통과하고 타입 오류가 없는 것**만
확인한다.

---

### Task 11: 죽은 코드를 지운다

**Files:**
- Delete: `mobile/src/features/travel/components/{StartActions,Mascot,AnchorPreview,PhotoCompare,StepList,ConversationTurn,AnswerBlock,ResultRow,AskComposer}.tsx`
- Delete: `mobile/src/features/travel/components/__tests__/{ConversationTurn,ResultRow}.test.tsx`
- Delete: `mobile/src/features/travel/hooks/use-card-tap.ts`
- Delete: `mobile/src/features/travel/lib/sheet-snap.ts` + `__tests__/sheet-snap.test.ts`
- Delete: `mobile/src/features/travel/stores/anchor-store.ts`

**Interfaces:**
- Consumes: Task 10 이 새 컴포넌트로 전부 갈아탄 상태
- Produces: 없음

- [ ] **Step 1: 아직 참조가 남았는지 확인한다**

```bash
cd mobile && grep -rn "StartActions\|Mascot\|AnchorPreview\|PhotoCompare\|StepList\|ConversationTurn\|AnswerBlock\|ResultRow\|AskComposer\|use-card-tap\|useCardTap\|travel/lib/sheet-snap\|anchor-store\|useTravelAnchor" src | grep -v "^src/features/travel/components/\(StartActions\|Mascot\|AnchorPreview\|PhotoCompare\|StepList\|ConversationTurn\|AnswerBlock\|ResultRow\|AskComposer\)\.tsx"
```

Expected: 지울 파일들 자신과 지울 테스트 말고는 결과가 없다. 남은 게 있으면 그 자리를 먼저 고친다.

- [ ] **Step 2: 지운다**

```bash
cd mobile && git rm -f \
  src/features/travel/components/StartActions.tsx \
  src/features/travel/components/Mascot.tsx \
  src/features/travel/components/AnchorPreview.tsx \
  src/features/travel/components/PhotoCompare.tsx \
  src/features/travel/components/StepList.tsx \
  src/features/travel/components/ConversationTurn.tsx \
  src/features/travel/components/AnswerBlock.tsx \
  src/features/travel/components/ResultRow.tsx \
  src/features/travel/components/AskComposer.tsx \
  src/features/travel/components/__tests__/ConversationTurn.test.tsx \
  src/features/travel/components/__tests__/ResultRow.test.tsx \
  src/features/travel/hooks/use-card-tap.ts \
  src/features/travel/lib/sheet-snap.ts \
  src/features/travel/lib/__tests__/sheet-snap.test.ts \
  src/features/travel/stores/anchor-store.ts
```

`hooks/__tests__/` 에 `use-card-tap` 테스트가 있으면 같이 지운다.

- [ ] **Step 3: 여행 탭이 유일한 소비자였던 공유 모듈 3개를 확인하고 지운다**

2026-08-08 컨트롤러 확인 — 아래 셋은 **`travel.tsx` 가 유일한 소비자**다.
Task 10 이 그 임포트를 걷어냈으므로 전부 죽는다.

```bash
cd mobile
grep -rn "GlassSheet" src | grep -v "components/GlassSheet.tsx"
grep -rn "mapListPaddingBottom\|list-padding" src | grep -v "lib/list-padding"
grep -rn "@/lib/sheet-snap" src
```

세 명령 모두 **테스트 파일 말고는 결과가 없어야** 한다. 그러면:

```bash
git rm -f \
  src/components/GlassSheet.tsx \
  src/lib/sheet-snap.ts \
  src/features/map/lib/list-padding.ts \
  src/features/map/lib/__tests__/list-padding.test.ts
```

`src/lib/__tests__/sheet-snap.test.ts` 가 있으면 같이 지운다.

**결과가 남으면 그 파일은 지우지 말고 보고한다** — 지도 탭이 나중에 시트를 다시
쓰게 됐을 수 있다. 확인은 `grep` 결과가 정본이고 이 문단이 아니다.

- [ ] **Step 4: 전체 검증**

```bash
cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test
```

Expected: 4종 전부 통과.

- [ ] **Step 5: 실기기에서 11개 상태를 확인한다**

```bash
cd mobile && npx expo start
```

프로토타입(`travel-tab-v2.html`)과 나란히 놓고 확인한다:
빈 상태 · 좌표 없음 · 사진 첨부 · 질의 중 · 결과 · 답변 펼침 · 문맥 칩 펼침 ·
사진 턴 · 카드 없는 턴 · 0곳 · 실패.

특히 확인할 것 — 캐러셀을 넘기면 지도가 그 핀으로 팬하는지, 핀을 탭하면 캐러셀이
그 장으로 가는지, 카드가 탭바에 가리지 않는지(`dockBottomPx`), 키보드가 올라와도
필드가 가리지 않는지.

---

### Task 12: 문서 · ADR · PR

**Files:**
- Rewrite: `docs/reference/travel-tab.md`
- Create: `docs/adr/0016-travel-tab-goes-map-first.md`
- Modify: `docs/adr/README.md` 또는 인덱스가 있으면 거기

**Interfaces:**
- Consumes: 앞의 모든 태스크
- Produces: PR

- [ ] **Step 1: ADR 을 쓴다**

`docs/adr/` 의 기존 파일 하나를 열어 형식을 그대로 따른다. 담을 내용:
- 뒤집는 결정: ADR 0012(카드 탭 두 뜻) · ADR 0015(상시 지도 + 글래스 시트)
- 결정: 시트를 없애고 결과를 지도 위 좌우 캐러셀로, 대화 이력과 앵커 모드를 폐기
- 근거: 시트가 지도를 배경으로 만들었다 · 세로 대화가 3턴이면 스크롤이 길었다 ·
  앵커는 별도 모드일 필요가 없다(보고 있는 카드가 곧 기준점)
- 트레이드오프: 확정 동작 없이 문맥이 따라온다 · 대화 이력이 사라진다

- [ ] **Step 2: `docs/reference/travel-tab.md` 를 새 구조로 다시 쓴다**

스펙(`docs/superpowers/specs/2026-08-08-travel-tab-map-first-design.md`)의 3층 구조 ·
수치 표 · 11개 상태 표를 옮기고, 폐기된 시트/앵커/턴 서술을 전부 걷어낸다.
문서 맨 위 참조 ADR 목록에 0016 을 더한다. **현행만 적고 히스토리는 ADR 이 맡는다.**

- [ ] **Step 3: 백엔드 문서를 맞춘다**

```bash
grep -n "찾았어요\|추렸어요\|answer" docs/reference/api.md | head -20
```

`POST /agent/ask` 절의 답변 문장 예시가 옛 문장이면 새 문장으로 바꾼다.

- [ ] **Step 4: 전체 검증을 한 번 더 돌린다**

```bash
cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test
cd ../backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest
```

Expected: 전부 통과. **여기까지 통과해야 커밋한다.**

- [ ] **Step 5: 브랜치 · 커밋 · PR**

```bash
git checkout -b feat/travel-map-first
git add -A
git commit -m "feat(travel): 여행 탭을 지도 우선 + 좌우 캐러셀로 다시 짠다"
git push -u origin feat/travel-map-first
```

PR 은 `dev` 로 열고 `.github/pull_request_template.md` 의 4개 절을 채운다
(`## 요약` / `## 변경 단위` / `## 핵심 결정` / `## 검증`, 변경 단위·검증에 체크 ≥1).
요약은 불릿 2~4개, 각 1~2줄, 사실 하나씩. 핵심 결정은 **볼드 1줄 + 근거 1~2문장**.
🤖 푸터·세션 링크는 넣지 않는다. push 는 `seeeeeeong` 계정으로 한다.

핵심 결정에 반드시 담을 것:
- **시트를 없애고 지도를 상시 주인공으로 둔다** — 결과를 읽으려 올리고 지도를 보려 내리는 왕복이 사라진다.
- **앵커는 모드가 아니라 보고 있는 카드다** — 잡기/해제 동작과 필드 토큰이 통째로 없어진다.
- **답변은 구체적 사실을 앞세운다** — `8곳 추렸어요` 가 아니라 `혼잡도 하위 20% 안쪽으로만 골랐어요`.

---

## Self-Review

**스펙 커버리지**

| 스펙 절 | 태스크 |
|---|---|
| 3층 구조 · 세로 예산 | 10 |
| 답변 바 (위계 뒤집기 · 펼침 · 사진 썸네일 · 진행 · 실패) | 3, 6 |
| 카드 (버튼 없음 · 상세보기 · 배지 = 핀) | 7 |
| 진행 바가 `추천 N곳` 대체 | 8 |
| 성질 칩 · 거리는 지역 줄로 · 툴팁 | 4, 7 |
| 독 · 고정 사진 칩 · 문맥 칩 펼침 | 5, 9 |
| 앵커 모드 폐기 | 5, 10, 11 |
| 지도 연동 (캐러셀↔핀 양방향) | 8, 10 |
| 11개 상태 | 10 (Step 5 에서 실기기 확인) |
| 폐기 12개 / 신규 4개 | 11 |
| 백엔드 답변 순서 · emphasis 대상 | 1, 2 |
| 문서 · ADR | 12 |

**타입 일관성** — `CARD_STRIDE`/`CARD_WIDTH`/`CARD_HEIGHT` 는 `SpotCard.tsx` 가 유일한
출처이고 `SpotCarousel` 이 임포트한다. `DockChip` 은 `dock-chips.ts` 가 정의하고
`TravelDock` 과 `travel.tsx` 가 같은 이름으로 쓴다. `Metric.icon` 은 `IconName` 이라
Task 4·6·7·9 의 아이콘 추가 스텝이 전부 `Icon.tsx` 를 늘린다.

**알려진 미해결**

- `SpotCarousel` 의 `scrollToIndex` prop 은 Task 8 Step 4 에서 추가되므로 Step 1 의
  테스트 `base` 에는 없다. Step 4 이후 `Props` 에 optional 로 들어가 기존 테스트가 그대로 통과한다.
- ~~Task 10 은 화면 단위 테스트를 쓰지 않는다~~ — **정정됨.** `travel-screen.test.tsx` 가
  이미 존재하고 목킹이 다 풀려 있다. Task 10 이 그 파일을 재작성한다(위 정정 블록 참조).
  `screen-layout.ts` 순수 함수 테스트는 그대로 두되, 화면 동작은 재작성한 화면 테스트가 맡는다.
- Task 11 Step 5 의 실기기 확인(`npx expo start`)은 **서브에이전트가 할 수 없다.**
  구현자는 이 스텝을 건너뛰고, 컨트롤러가 사람에게 넘긴다.

---

## 실행 순서

1 → 2 (백엔드, 독립) → 3 → 4 → 5 (모바일 순수 로직) → 6 → 7 → 8 → 9 (컴포넌트) → 10 (화면) → 11 (정리) → 12 (문서 · PR)

3·4·5 는 서로 의존하지 않으므로 병렬로 돌려도 된다. 6·7 도 마찬가지다.
8 은 7 을, 9 는 5 를, 10 은 6·7·8·9 를 필요로 한다.
