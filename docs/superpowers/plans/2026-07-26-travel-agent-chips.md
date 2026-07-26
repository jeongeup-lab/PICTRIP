# 여행 탭 칩 재설계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 여행 탭의 조건 시트를 없애고, 사진 진입구를 노출하고, 초기·후속 칩을 실측으로 모수가 확인된 축에만 걸리게 바꾼다.

**Architecture:** 백엔드는 `agent` 모듈 안에서 (1) 지도용 카테고리 술어 대신 전시·공연시설을 포함한 여행 탭 전용 술어를 쓰고, (2) `spot_moods`를 조회 축으로 올리고, (3) 정형 조건 3종을 지우고 그 자리에 `intent` 왕복 refine을 넣는다. 축제는 `feed` 모듈의 KTO 캐시를 `services.py` 경유로 읽는다. 모바일은 조건 시트를 삭제하고 사진 진입 카드와 patch 기반 칩을 붙인다.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL + pgvector · Redis · Gemini Flash · Expo SDK 56 · RN 0.85 · TypeScript strict · Zustand · TanStack Query

## Global Constraints

- 설계 근거는 `docs/superpowers/specs/2026-07-26-travel-agent-chips-design.md`. 수치는 전부 `agent-axis-probe` 실측(2026-07-26)에서 나왔다.
- **코드에 주석을 달지 않는다.** 의도는 이름과 구조로 드러낸다 (`CLAUDE.md` 금지 조항).
- **모바일에 이모지·신규 네이티브 모듈 금지.** 아이콘은 line-SVG `<Icon>`.
- 모든 API 응답은 JSend 봉투 `ok()`/`err()`. 에러는 `AppError` 서브클래스.
- `routes.py`는 HTTP I/O만 — DB·모델·sqlalchemy import 금지. 교차 모듈 접근은 상대 모듈의 `services.py` 경유.
- 모바일 테스트는 `src/app` 밖에 둔다 (Expo Router가 라우트로 스캔).
- 백엔드 검증: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest`. 커밋 전 `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports`.
- 모바일 검증: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`.
- 브랜치는 `feat/travel-agent-chips` (이미 `dev`에서 분기됨). **중간 PR을 만들지 않는다** — 전체 구현 후 PR 1개.

---

### Task 1: 여행 탭 전용 카테고리 술어

지도 "주변 관광지"용 `attraction_category_sql()`이 VE06(공연시설) 335곳 · VE07(전시시설) 1,571곳을 통째로 잘라내고 있다. 여행 탭 전용 술어를 새로 만들고 지도용은 건드리지 않는다.

**Files:**
- Modify: `backend/app/modules/spots/services/nearby.py`
- Modify: `backend/app/modules/spots/services/__init__.py`
- Test: `backend/tests/test_map_categories.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces: `travel_category_sql() -> str` — `app.modules.spots.services`에서 import 가능. `spots.` 접두사가 붙은 WHERE 절 문자열을 돌려준다. Task 2가 raw SQL 템플릿에 끼워 넣는다.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_map_categories.py` 끝에 추가:

```python
def test_travel_predicate_keeps_exhibition_and_performance_venues() -> None:
    from app.modules.spots.services import attraction_category_sql, travel_category_sql

    travel = travel_category_sql()
    nearby = attraction_category_sql()

    assert "'VE06'" in nearby
    assert "'VE07'" in nearby
    assert "'VE06'" not in travel
    assert "'VE07'" not in travel
    assert "'VE08', 'VE09', 'VE10', 'VE11'" in travel
    assert "spots.content_type_id != 32" in travel
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_map_categories.py::test_travel_predicate_keeps_exhibition_and_performance_venues -v`
Expected: FAIL with `ImportError: cannot import name 'travel_category_sql'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/spots/services/nearby.py` — `_VE_EXCLUDE` 아래에 추가:

```python
_TRAVEL_VE_EXCLUDE = ("VE08", "VE09", "VE10", "VE11")
```

`attraction_category_sql()` 바로 아래에 추가:

```python
def travel_category_predicate() -> ColumnElement[bool]:
    return and_(
        Spot.content_type_id != _LODGING_CONTENT_TYPE,
        or_(
            Spot.lcls_systm1.in_(("HS", "NA", "EX")),
            and_(
                Spot.lcls_systm1 == "VE",
                or_(
                    Spot.lcls_systm2.is_(None),
                    Spot.lcls_systm2.notin_(_TRAVEL_VE_EXCLUDE),
                ),
            ),
        ),
    )


def travel_category_sql() -> str:
    return _predicate_sql(travel_category_predicate())
```

`backend/app/modules/spots/services/__init__.py` — `attraction_category_sql` import 줄 근처에 `travel_category_sql`을 추가하고 `__all__`에도 알파벳 순으로 넣는다.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_map_categories.py -v`
Expected: PASS (기존 테스트 포함 전부)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/spots/services/nearby.py backend/app/modules/spots/services/__init__.py backend/tests/test_map_categories.py
git commit -m "feat(spots): 전시·공연시설을 포함하는 여행 탭 전용 카테고리 술어를 추가한다"
```

---

### Task 2: agent가 새 술어를 쓰고 실내를 코드로 지정한다

`INDOOR_KEYWORDS`의 `체험관`이 `lcls_systm1_nm ILIKE '%체험관%'`으로 **`체험관광` 대분류**에 매칭돼 야외 1,629곳을 끌어온다. 이름 매칭을 버리고 코드 절로 바꾼다.

**Files:**
- Modify: `backend/app/modules/agent/repositories.py`
- Modify: `backend/app/modules/agent/services/retrieve.py`
- Modify: `backend/app/modules/agent/services/ask.py`
- Test: `backend/tests/test_agent_ask.py`

**Interfaces:**
- Consumes: `travel_category_sql()` (Task 1)
- Produces:
  - `repositories.find_candidates(..., indoor_only: bool = False)` — 실내 절을 AND로 건다
  - `retrieve.search_candidates(..., indoor_only: bool = False)`
  - `retrieve.INDOOR_L2 = ("VE06", "VE07")` · `retrieve.INDOOR_L3 = ("VE020400", "VE120300")`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_agent_ask.py`의 `_seed()` 안, `j1` INSERT 뒤에 실내 스팟 시드를 추가한다:

```python
    await session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('VE070100', 'VE07', 'VE', '박물관', '전시시설', '문화관광') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO lcls_systm_codes "
            "(lcls_systm3_cd, lcls_systm2_cd, lcls_systm1_cd, lcls_systm3_nm, "
            "lcls_systm2_nm, lcls_systm1_nm) "
            "VALUES ('EX070100', 'EX07', 'EX', '기타체험관광', '기타체험', '체험관광') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES ('m1', 14, '부산박물관', '부산광역시 사하구 2', "
            "'http://kto/i.jpg', 1, :lng, :lat, 'VE', 'VE07', 'VE070100', '26', '26380')"
        ),
        {"lng": LNG, "lat": LAT},
    )
    await session.execute(
        text(
            "INSERT INTO spots (content_id, content_type_id, title, addr1, "
            "first_image_url, show_flag, mapx, mapy, lcls_systm1, lcls_systm2, "
            "lcls_systm3, ldong_regn_cd, ldong_signgu_cd) "
            "VALUES ('e1', 12, '갯벌체험마을', '부산광역시 사하구 3', "
            "'http://kto/i.jpg', 1, :lng, :lat, 'EX', 'EX07', 'EX070100', '26', '26380')"
        ),
        {"lng": LNG, "lat": LAT},
    )
```

같은 파일 끝에 테스트 2개를 추가:

```python
@pytest.mark.integration
async def test_travel_predicate_surfaces_museums_that_the_map_predicate_drops(
    db_session, seeded
) -> None:
    rows = await repositories.find_candidates(
        db_session, codes=["VE070100"], region_prefixes=None, limit=50
    )

    assert [row.content_id for row in rows] == ["m1"]


@pytest.mark.integration
async def test_indoor_only_excludes_outdoor_experience_tourism(db_session, seeded) -> None:
    rows = await repositories.find_candidates(
        db_session, codes=None, region_prefixes=None, limit=50, indoor_only=True
    )

    ids = {row.content_id for row in rows}
    assert "m1" in ids
    assert "e1" not in ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -k "travel_predicate or indoor_only" -v`
Expected: 첫 테스트는 FAIL (빈 목록 — 지도 술어가 VE07을 자른다), 둘째는 `TypeError: find_candidates() got an unexpected keyword argument 'indoor_only'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/agent/repositories.py`:

1. import 교체 — `from app.modules.spots.services import attraction_category_sql` → `from app.modules.spots.services import travel_category_sql`
2. `_VECTOR_MATCH_SQL`을 쓰는 `match_spots_by_vector`의 `sql = _VECTOR_MATCH_SQL.format(attraction=attraction_category_sql(), ...)` → `travel_category_sql()`
3. `_CANDIDATE_SQL`의 `{attraction}`을 채우는 `find_candidates` 안 `.format(attraction=attraction_category_sql(), ...)` → `travel_category_sql()`
4. `_TITLE_CANDIDATE_SQL`은 `attraction` 자리표시자가 없으므로 그대로 둔다
5. 실내 절 상수와 파라미터 추가:

```python
_INDOOR_CLAUSE = (
    "AND (spots.lcls_systm2 = ANY(CAST(:indoor_l2 AS text[])) "
    "OR spots.lcls_systm3 = ANY(CAST(:indoor_l3 AS text[])))"
)
```

`_CANDIDATE_SQL`의 `{region_clause}` 다음 줄에 `{indoor_clause}`를 넣고, `find_candidates` 시그니처에 `indoor_only: bool = False`를 추가한 뒤:

```python
    indoor_clause = ""
    if indoor_only:
        indoor_clause = _INDOOR_CLAUSE
        params["indoor_l2"] = list(INDOOR_L2)
        params["indoor_l3"] = list(INDOOR_L3)
```

`.format(...)`에 `indoor_clause=indoor_clause`를 추가한다.

`INDOOR_L2`/`INDOOR_L3`는 `repositories.py` 상단에 둔다 (retrieve가 재수출한다):

```python
INDOOR_L2 = ("VE06", "VE07")
INDOOR_L3 = ("VE020400", "VE120300")
```

`backend/app/modules/agent/services/retrieve.py`:

- `INDOOR_KEYWORDS = (...)` 줄을 삭제
- `from app.modules.agent.repositories import CandidateOrder, CandidateRow` 를 `..., INDOOR_L2, INDOOR_L3` 까지 확장하고 모듈 상수로 재수출
- `search_candidates`에 `indoor_only: bool = False`를 추가하고 내부 `query()`가 `find_candidates(..., indoor_only=indoor_only)`를 넘기게 한다

`backend/app/modules/agent/services/ask.py`:

- `_keywords()`에서 `extra = retrieve.INDOOR_KEYWORDS if intent.indoorOnly else ()` 줄과 그 사용을 제거해 `WHO_KEYWORDS`만 남긴다 (조건 삭제는 Task 4)
- `retrieve.search_candidates(...)` 호출에 `indoor_only=intent.indoorOnly` 추가
- `_search_label()`이 실내일 때 라벨을 바꾸도록 `indoor: bool` 인자를 받고, `if indoor: head = "실내"` 를 `keywords` 분기보다 먼저 둔다

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent backend/tests/test_agent_ask.py
git commit -m "fix(agent): 실내를 이름 매칭에서 코드 절로 바꾸고 전시·공연시설을 조회 대상에 넣는다"
```

---

### Task 3: mood를 조회 축으로 올린다

`spot_moods` 4,677행이 서빙에 쓰이지 않고 있다. `섬`(1글자라 `find_category_codes`가 `len < 2`로 컷) · `야경`(카테고리 부재)처럼 코드 매칭이 실패하는 축을 잡는다.

**Files:**
- Modify: `backend/app/modules/agent/repositories.py`
- Modify: `backend/app/modules/agent/services/retrieve.py`
- Test: `backend/tests/test_agent_ask.py`

**Interfaces:**
- Consumes: `repositories.find_candidates` (Task 2에서 `indoor_only` 추가됨)
- Produces:
  - `repositories.find_mood_ids(session, codes: list[str]) -> list[int]`
  - `repositories.find_candidates(..., mood_ids: list[int] | None = None)`
  - `retrieve.search_candidates(..., mood_ids: list[int] | None = None)`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_agent_ask.py` `_seed()`에 mood 시드를 추가 (실내 스팟 시드 뒤):

```python
    await session.execute(
        text(
            "INSERT INTO moods (id, code, name, emoji, sort_order) "
            "VALUES (1, 'night', '야경', 'x', 1) ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO spot_moods (content_id, mood_id, confidence, source) "
            "VALUES ('v1', 1, 1.0, 'code') ON CONFLICT DO NOTHING"
        )
    )
```

테스트 2개 추가:

```python
@pytest.mark.integration
async def test_mood_codes_resolve_to_ids(db_session, seeded) -> None:
    assert await repositories.find_mood_ids(db_session, ["night"]) == [1]
    assert await repositories.find_mood_ids(db_session, []) == []
    assert await repositories.find_mood_ids(db_session, ["nope"]) == []


@pytest.mark.integration
async def test_mood_filter_narrows_candidates(db_session, seeded) -> None:
    rows = await repositories.find_candidates(
        db_session, codes=None, region_prefixes=None, limit=50, mood_ids=[1]
    )

    assert [row.content_id for row in rows] == ["v1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -k mood -v`
Expected: FAIL — `AttributeError: module 'app.modules.agent.repositories' has no attribute 'find_mood_ids'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/agent/repositories.py`:

```python
_MOOD_ID_SQL = "SELECT id FROM moods WHERE code = ANY(CAST(:codes AS text[])) ORDER BY id"


async def find_mood_ids(session: AsyncSession, codes: list[str]) -> list[int]:
    if not codes:
        return []
    result = await session.execute(text(_MOOD_ID_SQL), {"codes": codes})
    return [int(row.id) for row in result]
```

```python
_MOOD_CLAUSE = (
    "AND EXISTS (SELECT 1 FROM spot_moods sm "
    "WHERE sm.content_id = spots.content_id "
    "AND sm.mood_id = ANY(CAST(:mood_ids AS int[])))"
)
```

`_CANDIDATE_SQL`의 `{indoor_clause}` 다음 줄에 `{mood_clause}`를 넣고, `find_candidates`에 `mood_ids: list[int] | None = None` 파라미터를 추가한다:

```python
    mood_clause = ""
    if mood_ids:
        mood_clause = _MOOD_CLAUSE
        params["mood_ids"] = mood_ids
```

`.format(...)`에 `mood_clause=mood_clause`를 추가한다.

`backend/app/modules/agent/services/retrieve.py` — `search_candidates`에 `mood_ids: list[int] | None = None`을 추가하고 내부 `query()`가 그대로 넘기게 한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent backend/tests/test_agent_ask.py
git commit -m "feat(agent): spot_moods를 조회 축으로 올린다"
```

---

### Task 4: 조건 3종을 삭제한다

`when`은 답변 문구에만 실리고, `who`의 `solo`/`duo`는 무동작이며, `region`은 질문에 지역이 나오면 침묵 무시된다.

**Files:**
- Modify: `backend/app/modules/agent/schemas.py`
- Modify: `backend/app/modules/agent/services/ask.py`
- Modify: `backend/app/modules/agent/services/retrieve.py`
- Modify: `backend/app/modules/agent/routes.py`
- Test: `backend/tests/test_agent_ask.py`

**Interfaces:**
- Consumes: Task 2·3의 `retrieve.search_candidates` 시그니처
- Produces:
  - `retrieve.resolve_region_prefixes(session, *, hints: list[str]) -> list[str]` — `region` 파라미터 제거
  - `AskRequest`에서 `region`/`when`/`who`/`filters` 삭제
  - `ask.ask(session, kto, *, question, lat, lng, image_bytes, image_mime)` — `filters` 인자 삭제

- [ ] **Step 1: Write the failing test**

`backend/tests/test_agent_ask.py`에서:

- `test_every_region_option_has_prefixes_except_all` 를 **삭제**한다
- `test_answer_emphasises_the_result_count` 를 아래로 교체한다:

```python
def test_answer_emphasises_the_result_count() -> None:
    segments = ask_service._answer(
        _pool()[:4],
        intent=QueryIntent(),
        near=False,
        lat=None,
        lng=None,
    )

    assert [s.text for s in segments if s.emphasis] == ["4곳"]
    assert "이번 주말" not in "".join(s.text for s in segments)
```

- import 줄에서 `AskFilters` 를 뺀다
- 파일 끝에 추가:

```python
@pytest.mark.integration
async def test_legacy_condition_fields_are_ignored_not_rejected(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(categoryKeywords=["계곡"])),
    )

    response = await client.post(
        "/v1/agent/ask",
        json={"question": "계곡", "region": "jeju", "when": "weekend", "who": "pets"},
    )

    assert response.status_code == 200
```

> `_fake_intent`는 이 파일에 이미 있는 헬퍼 패턴을 따른다. 없으면 아래를 파일 상단 헬퍼 구역에 추가한다:
>
> ```python
> def _fake_intent(intent: QueryIntent):
>     async def _run(question: str) -> QueryIntent:
>         return intent
>
>     return _run
> ```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -k "answer_emphasises or legacy_condition" -v`
Expected: FAIL — `_answer() missing 1 required keyword-only argument: 'filters'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/agent/schemas.py`:
- `Region` · `When` · `Who` 타입 별칭 삭제
- `AskFilters` 클래스 삭제
- `AskRequest`에서 `region`/`when`/`who` 필드와 `filters` 프로퍼티 삭제

`backend/app/modules/agent/services/retrieve.py`:
- `REGION_PREFIXES` · `REGION_LABELS` · `WHO_KEYWORDS` 삭제
- import에서 `Region`, `Who` 제거
- `resolve_region_prefixes(session, *, region, hints)` → `resolve_region_prefixes(session, *, hints)`. 힌트가 없거나 매핑이 비면 `return []`

```python
async def resolve_region_prefixes(session: AsyncSession, *, hints: list[str]) -> list[str]:
    if not hints:
        return []
    tokens = {token for hint in hints for token in _hint_tokens(hint)}
    mapping = await map_region_tokens_to_sido(session, tokens)
    return sorted(set(mapping.values())) if mapping else []
```

`backend/app/modules/agent/services/ask.py`:
- `WHEN_LABELS` 삭제
- `AskFilters` import 삭제
- `ask()` · `_ask_with_photo()` · `_ask_with_question()` · `_answer()` 에서 `filters` 파라미터 삭제
- `_keywords(intent, filters)` → `_keywords(intent)` 로 바꾸고 본문을 `return list(intent.categoryKeywords)` 로 축소
- `_search_label(keywords, prefixes, filters, indoor)` → `_search_label(keywords, prefixes, indoor)` 로 바꾸고 마지막 폴백을 `head = "전국"` 으로
- `resolve_region_prefixes(session, region=..., hints=...)` 호출을 `hints=` 만 남긴다
- `_answer()`의 `when_label` 블록 3줄을 삭제

`backend/app/modules/agent/routes.py` — `filters=payload.filters,` 줄 삭제

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -v && uv run mypy app && uv run lint-imports`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent backend/tests/test_agent_ask.py
git commit -m "refactor(agent): 동작하지 않던 지역·언제·누구와 조건을 제거한다"
```

---

### Task 5: intent에 mood·축제 축을 추가한다

**Files:**
- Modify: `backend/app/modules/agent/schemas.py`
- Modify: `backend/app/modules/agent/services/intent.py`
- Modify: `backend/app/modules/agent/services/ask.py`
- Test: `backend/tests/test_agent_ask.py`

**Interfaces:**
- Consumes: `repositories.find_mood_ids` (Task 3), `QueryIntent` (Task 4에서 조건 제거됨)
- Produces:
  - `Mood = Literal["sea", "mountain", "lake", "island", "hanok", "night", "street"]`
  - `QueryIntent.moodHints: list[Mood]` · `QueryIntent.festivalOnly: bool`
  - `ToolName`에 `"mood_search"` · `"festival"` 추가

- [ ] **Step 1: Write the failing test**

```python
def test_intent_parses_mood_hints_and_drops_unknown_codes() -> None:
    parsed = intent_service._moods(["night", "sea", "market", 7, "night"])

    assert parsed == ["night", "sea"]


@pytest.mark.integration
async def test_mood_hint_filters_the_candidate_pool(
    db_session, client, seeded, monkeypatch
) -> None:
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(moodHints=["night"])),
    )

    response = await client.post("/v1/agent/ask", json={"question": "야경 좋은 곳"})

    body = response.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["v1"]
    assert any(step["tool"] == "mood_search" for step in body["steps"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -k mood -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_moods'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/agent/schemas.py`:

```python
Mood = Literal["sea", "mountain", "lake", "island", "hanok", "night", "street"]
```

`ToolName` 리터럴에 `"mood_search"`, `"festival"` 추가. `QueryIntent`에 두 필드 추가:

```python
    moodHints: list[Mood] = Field(default_factory=list)
    festivalOnly: bool = False
```

`backend/app/modules/agent/services/intent.py`:

- `_SYSTEM_PROMPT`의 `- nearMe:` 규칙 아래에 두 줄 삽입:

```
- moodHints: 분위기를 지목하면 아래 코드 중에서만 고른다 — sea(바다), mountain(산·숲),
  lake(호수), island(섬), hanok(한옥·고궁), night(야경), street(도시 골목). 없으면 빈 배열.
- festivalOnly: 축제·행사·페스티벌을 찾는 질문이면 true, 아니면 false.
```

- `_RESPONSE_SCHEMA["properties"]`에 추가:

```python
        "moodHints": {
            "type": "ARRAY",
            "items": {
                "type": "STRING",
                "enum": ["sea", "mountain", "lake", "island", "hanok", "night", "street"],
            },
        },
        "festivalOnly": {"type": "BOOLEAN"},
```

`"required"` 리스트에 `"moodHints"`, `"festivalOnly"` 추가.

- 파서 추가:

```python
_MOOD_CODES = ("sea", "mountain", "lake", "island", "hanok", "night", "street")


def _moods(raw: Any) -> list[Mood]:
    if not isinstance(raw, list):
        return []
    picked: list[Mood] = []
    for item in raw:
        if item in _MOOD_CODES and item not in picked:
            picked.append(item)
    return picked
```

`Mood`를 import하고 `QueryIntent(...)` 생성에 `moodHints=_moods(data.get("moodHints"))`, `festivalOnly=bool(data.get("festivalOnly"))` 추가. `logger.info` 에 `moods=len(intent.moodHints)` 추가.

`backend/app/modules/agent/services/ask.py` — `_ask_with_question()` 안 `codes` 계산 직후:

```python
    mood_ids = await repositories.find_mood_ids(session, list(intent.moodHints))
```

`retrieve.search_candidates(...)` 호출에 `mood_ids=mood_ids` 추가. 그리고 `category_search` 스텝 뒤에:

```python
        if mood_ids:
            steps.append(
                AskStep(tool="mood_search", label="분위기로 추림", badge=_count(candidates))
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent backend/tests/test_agent_ask.py
git commit -m "feat(agent): 의도 추출에 분위기·축제 축을 추가한다"
```

---

### Task 6: intent 왕복 refine

후속 칩이 이전 턴을 잃고 전국 재검색으로 새어나가는 문제를 고친다. 응답에 적용된 `intent`를 싣고, 후속 요청은 `intent + patch`만 보내며 Gemini를 건너뛴다.

**Files:**
- Modify: `backend/app/modules/agent/schemas.py`
- Create: `backend/app/modules/agent/services/refine.py`
- Modify: `backend/app/modules/agent/services/ask.py`
- Modify: `backend/app/modules/agent/routes.py`
- Test: `backend/tests/test_agent_ask.py`

**Interfaces:**
- Consumes: `QueryIntent` (Task 5 확장판)
- Produces:
  - `RefinePatch(crowdPreference, indoorOnly, nearMe, drop)`
  - `refine.apply_patch(intent: QueryIntent, patch: RefinePatch | None) -> QueryIntent`
  - `AskRequest.intent` · `AskRequest.patch`
  - `AskResponse.intent`

- [ ] **Step 1: Write the failing test**

```python
def test_apply_patch_sets_only_the_named_axes() -> None:
    base = QueryIntent(categoryKeywords=["계곡"], regionHints=["제주"])

    result = refine_service.apply_patch(base, RefinePatch(crowdPreference="quiet"))

    assert result.crowdPreference == "quiet"
    assert result.categoryKeywords == ["계곡"]
    assert result.regionHints == ["제주"]


def test_apply_patch_drop_clears_the_named_axis() -> None:
    base = QueryIntent(categoryKeywords=["계곡"], regionHints=["제주"], crowdPreference="quiet")

    assert refine_service.apply_patch(base, RefinePatch(drop="crowd")).crowdPreference == "any"
    assert refine_service.apply_patch(base, RefinePatch(drop="region")).regionHints == []
    assert refine_service.apply_patch(base, RefinePatch(drop="category")).categoryKeywords == []


def test_apply_patch_with_no_patch_returns_the_intent_unchanged() -> None:
    base = QueryIntent(categoryKeywords=["계곡"])

    assert refine_service.apply_patch(base, None) == base


@pytest.mark.integration
async def test_refine_request_skips_the_llm_and_keeps_prior_axes(
    db_session, client, seeded, monkeypatch
) -> None:
    calls: list[str] = []

    async def _boom(question: str) -> QueryIntent:
        calls.append(question)
        raise AssertionError("LLM must not be called on a refine request")

    monkeypatch.setattr(intent_service, "extract_intent", _boom)

    response = await client.post(
        "/v1/agent/ask",
        json={
            "intent": {"categoryKeywords": ["계곡"], "regionHints": ["부산"]},
            "patch": {"crowdPreference": "quiet"},
        },
    )

    body = response.json()["data"]
    assert calls == []
    assert body["intent"]["crowdPreference"] == "quiet"
    assert body["intent"]["categoryKeywords"] == ["계곡"]
    assert body["intent"]["regionHints"] == ["부산"]
```

import 줄에 `from app.modules.agent.schemas import RefinePatch` 와 `from app.modules.agent.services import refine as refine_service` 를 추가한다.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -k "apply_patch or refine_request" -v`
Expected: FAIL — `ImportError: cannot import name 'refine'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/agent/schemas.py`:

```python
DropAxis = Literal["crowd", "indoor", "near", "region", "category"]


class RefinePatch(BaseModel):
    crowdPreference: CrowdPreference | None = None
    indoorOnly: bool | None = None
    nearMe: bool | None = None
    drop: DropAxis | None = None


class Suggestion(BaseModel):
    label: str
    patch: RefinePatch
```

`AskRequest`에 추가:

```python
    intent: QueryIntent | None = None
    patch: RefinePatch | None = None
```

`AskResponse`:

```python
    intent: QueryIntent
    suggestions: list[Suggestion]
```

`backend/app/modules/agent/services/refine.py` (신규):

```python
from __future__ import annotations

from app.modules.agent.schemas import QueryIntent, RefinePatch

_DROP_FIELDS = {
    "crowd": {"crowdPreference": "any"},
    "indoor": {"indoorOnly": False},
    "near": {"nearMe": False},
    "region": {"regionHints": []},
    "category": {"categoryKeywords": [], "moodHints": []},
}


def apply_patch(intent: QueryIntent, patch: RefinePatch | None) -> QueryIntent:
    if patch is None:
        return intent
    changes: dict[str, object] = {}
    if patch.crowdPreference is not None:
        changes["crowdPreference"] = patch.crowdPreference
    if patch.indoorOnly is not None:
        changes["indoorOnly"] = patch.indoorOnly
    if patch.nearMe is not None:
        changes["nearMe"] = patch.nearMe
    if patch.drop is not None:
        changes.update(_DROP_FIELDS[patch.drop])
    return intent.model_copy(update=changes)
```

`backend/app/modules/agent/services/ask.py`:

- `ask()` 시그니처에 `intent: QueryIntent | None`, `patch: RefinePatch | None` 추가
- 필수 입력 검증을 `if image_bytes is None and not cleaned and intent is None: raise ValidationFailed("question, photo or intent is required")` 로 바꾼다
- `_ask_with_question()`이 `intent`/`patch`를 받아, 있으면 `intent = refine_service.apply_patch(intent, patch)` 로 시작하고 `extract_intent`를 건너뛰며 `AskStep(tool="intent", ...)`도 넣지 않는다. 없을 때만 기존 경로
- `_ask_with_photo()`도 같은 방식으로 `intent`가 실려 오면 Gemini를 건너뛴다
- 두 응답 생성부의 `AskResponse(...)`에 `intent=intent` 추가

`backend/app/modules/agent/routes.py`:

- `ask_service.ask(...)` 호출에 `intent=payload.intent, patch=payload.patch` 추가
- multipart 경로에서 `intent`/`patch`는 JSON 문자열로 온다. `_read_payload`의 `fields` 구성 뒤에 디코드를 넣는다:

```python
        for key in ("intent", "patch"):
            raw = fields.get(key)
            if isinstance(raw, str):
                try:
                    fields[key] = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValidationFailed(f"invalid {key} json") from exc
```

`fields` 의 타입 주석을 `dict[str, Any]` 로 넓힌다.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -v && uv run mypy app`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent backend/tests/test_agent_ask.py
git commit -m "feat(agent): 후속 질의를 intent 왕복 refine으로 바꾼다"
```

---

### Task 7: 후속 칩을 상태에서 파생시킨다

`BASE_SUGGESTIONS`/`NEAR_SUGGESTIONS` 고정 3개를 버리고, 켜지지 않은 축만 칩으로 내보낸다.

**Files:**
- Create: `backend/app/modules/agent/services/suggest.py`
- Modify: `backend/app/modules/agent/services/ask.py`
- Test: `backend/tests/test_agent_ask.py`

**Interfaces:**
- Consumes: `QueryIntent`, `RefinePatch`, `Suggestion` (Task 6)
- Produces: `suggest.derive(intent: QueryIntent, *, has_coords: bool, result_count: int) -> list[Suggestion]`

- [ ] **Step 1: Write the failing test**

```python
def test_suggestions_offer_only_axes_that_are_not_already_on() -> None:
    chips = suggest_service.derive(
        QueryIntent(crowdPreference="quiet", indoorOnly=True),
        has_coords=False,
        result_count=20,
    )

    assert [c.label for c in chips] == ["유명한 곳으로"]


def test_suggestions_offer_distance_only_when_coords_are_present() -> None:
    without = suggest_service.derive(QueryIntent(), has_coords=False, result_count=20)
    with_coords = suggest_service.derive(QueryIntent(), has_coords=True, result_count=20)

    assert "가까운 순으로" not in [c.label for c in without]
    assert "가까운 순으로" in [c.label for c in with_coords]


def test_thin_results_lead_with_a_release_chip_on_the_narrowest_axis() -> None:
    chips = suggest_service.derive(
        QueryIntent(crowdPreference="quiet", regionHints=["제주"]),
        has_coords=False,
        result_count=2,
    )

    assert chips[0].label == "조건 하나 풀기"
    assert chips[0].patch.drop == "crowd"


def test_festival_turns_get_no_follow_up_chips() -> None:
    chips = suggest_service.derive(
        QueryIntent(festivalOnly=True), has_coords=True, result_count=10
    )

    assert chips == []


def test_suggestions_are_capped_at_three() -> None:
    chips = suggest_service.derive(
        QueryIntent(regionHints=["제주"]), has_coords=True, result_count=2
    )

    assert len(chips) == 3
```

import에 `from app.modules.agent.services import suggest as suggest_service` 추가.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -k suggest -v`
Expected: FAIL — `ImportError: cannot import name 'suggest'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/agent/services/suggest.py` (신규):

```python
from __future__ import annotations

from app.modules.agent.schemas import DropAxis, QueryIntent, RefinePatch, Suggestion

MAX_SUGGESTIONS = 3
THIN_RESULT_COUNT = 5
_DROP_ORDER: tuple[DropAxis, ...] = ("crowd", "indoor", "category", "near", "region")


def derive(intent: QueryIntent, *, has_coords: bool, result_count: int) -> list[Suggestion]:
    if intent.festivalOnly:
        return []
    chips: list[Suggestion] = []
    if intent.crowdPreference == "any":
        chips.append(Suggestion(label="사람 적은 곳만", patch=RefinePatch(crowdPreference="quiet")))
    elif intent.crowdPreference == "quiet":
        chips.append(Suggestion(label="유명한 곳으로", patch=RefinePatch(crowdPreference="popular")))
    if not intent.indoorOnly:
        chips.append(Suggestion(label="실내만", patch=RefinePatch(indoorOnly=True)))
    if has_coords and not intent.nearMe:
        chips.append(Suggestion(label="가까운 순으로", patch=RefinePatch(nearMe=True)))
    if result_count < THIN_RESULT_COUNT and (axis := _narrowest_axis(intent)) is not None:
        chips.insert(0, Suggestion(label="조건 하나 풀기", patch=RefinePatch(drop=axis)))
    return chips[:MAX_SUGGESTIONS]


def _narrowest_axis(intent: QueryIntent) -> DropAxis | None:
    engaged: dict[DropAxis, bool] = {
        "crowd": intent.crowdPreference != "any",
        "indoor": intent.indoorOnly,
        "category": bool(intent.categoryKeywords or intent.moodHints),
        "near": intent.nearMe,
        "region": bool(intent.regionHints),
    }
    return next((axis for axis in _DROP_ORDER if engaged[axis]), None)
```

`backend/app/modules/agent/services/ask.py`:

- `BASE_SUGGESTIONS` · `NEAR_SUGGESTIONS` 상수 삭제
- 두 `AskResponse(...)` 의 `suggestions=` 를 아래로 교체

```python
        suggestions=suggest_service.derive(
            intent,
            has_coords=lat is not None and lng is not None,
            result_count=len(spots),
        ),
```

- `from app.modules.agent.services import suggest as suggest_service` import 추가

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_agent_ask.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent backend/tests/test_agent_ask.py
git commit -m "feat(agent): 후속 칩을 적용된 의도에서 파생시킨다"
```

---

### Task 8: 축제 축

실측상 오늘 진행 중 축제 57건(이미지 56건)이 있고 D-0~D-7이 고르다. `feed`가 이미 `searchFestival2`를 캐시하고 있으니 풀만 넓혀 재사용한다.

**Files:**
- Modify: `backend/app/modules/feed/services/kto_channels.py`
- Modify: `backend/app/modules/feed/services/__init__.py`
- Modify: `backend/app/modules/agent/services/ask.py`
- Test: `backend/tests/test_kto_channels.py`
- Test: `backend/tests/test_agent_ask.py`

**Interfaces:**
- Consumes: `ChannelCardRow` (`app.modules.feed.services`)
- Produces: `feed_services.load_festival_pool(redis: Redis, kto: KtoClient) -> list[ChannelCardRow]` — 오늘 진행 중 축제 최대 60건, 캐시 키 `festival:pool:v1`, TTL 3600s

- [ ] **Step 1: Write the failing test**

`backend/tests/test_kto_channels.py` 끝에:

```python
@pytest.mark.asyncio
async def test_festival_pool_returns_more_than_the_channel_and_caches_separately(
    monkeypatch,
) -> None:
    from fakeredis.aioredis import FakeRedis

    from app.modules.feed.services import kto_channels

    today = date(2026, 7, 26)
    items = [
        {
            "contentid": str(i),
            "title": f"축제{i}",
            "addr1": "제주특별자치도 서귀포시 1" if i == 0 else "서울특별시 종로구 1",
            "firstimage": "https://kto/i.jpg",
            "eventstartdate": "20260701",
            "eventenddate": "20260810",
        }
        for i in range(30)
    ]

    class _Kto:
        async def call(self, service, operation, **params):
            return items if params["pageNo"] == 1 else []

    redis = FakeRedis(decode_responses=True)
    monkeypatch.setattr(kto_channels, "_today", lambda: today)

    pool = await kto_channels.load_festival_pool(redis, _Kto())

    assert len(pool) == 30
    assert await redis.get("festival:pool:v1") is not None
```

`backend/tests/test_agent_ask.py` 끝에:

```python
@pytest.mark.integration
async def test_festival_intent_returns_festival_cards_with_dday_tags(
    db_session, client, seeded, monkeypatch
) -> None:
    from app.modules.agent.services import ask as ask_module
    from app.modules.feed.services.channels import ChannelCardRow

    async def _pool(redis, kto):
        return [
            ChannelCardRow(
                content_id="f1",
                title="봉화은어축제",
                region_label="경상북도 봉화군",
                image_url="https://kto/f.jpg",
                dday="D-7",
                line="8월 2일까지",
            )
        ]

    monkeypatch.setattr(ask_module.feed_services, "load_festival_pool", _pool)
    monkeypatch.setattr(
        intent_service, "extract_intent", _fake_intent(QueryIntent(festivalOnly=True))
    )

    response = await client.post("/v1/agent/ask", json={"question": "지금 열리는 축제"})

    body = response.json()["data"]
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    assert body["spots"][0]["tag"] == "D-7"
    assert body["suggestions"] == []
    assert any(step["tool"] == "festival" for step in body["steps"])


@pytest.mark.integration
async def test_festival_region_miss_falls_back_nationwide_and_says_so(
    db_session, client, seeded, monkeypatch
) -> None:
    from app.modules.agent.services import ask as ask_module
    from app.modules.feed.services.channels import ChannelCardRow

    async def _pool(redis, kto):
        return [
            ChannelCardRow(
                content_id="f1",
                title="봉화은어축제",
                region_label="경상북도 봉화군",
                image_url="https://kto/f.jpg",
                dday="D-7",
            )
        ]

    monkeypatch.setattr(ask_module.feed_services, "load_festival_pool", _pool)
    monkeypatch.setattr(
        intent_service,
        "extract_intent",
        _fake_intent(QueryIntent(festivalOnly=True, regionHints=["제주"])),
    )

    response = await client.post("/v1/agent/ask", json={"question": "제주 축제"})

    body = response.json()["data"]
    sentence = "".join(part["text"] for part in body["answer"])
    assert [s["contentId"] for s in body["spots"]] == ["f1"]
    assert "제주에는 오늘 열리는 축제가 없어 전국에서 골랐어요" in sentence
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest tests/test_kto_channels.py -k festival_pool tests/test_agent_ask.py -k festival_intent -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'load_festival_pool'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/modules/feed/services/kto_channels.py`:

- `fetch_festa_cards` 시그니처를 `async def fetch_festa_cards(kto: KtoClient, *, today: date | None = None, limit: int = _CARD_COUNT) -> list[ChannelCardRow]:` 로 바꾸고 마지막 줄을 `return cards[:limit]` 로
- 파일 끝에 추가:

```python
_FESTIVAL_POOL_LIMIT = 60
_FESTIVAL_POOL_KEY = "festival:pool:v1"
_FESTIVAL_POOL_TTL = 3600


async def load_festival_pool(redis: Redis, kto: KtoClient) -> list[ChannelCardRow]:
    try:
        cached = await redis.get(_FESTIVAL_POOL_KEY)
    except Exception as exc:
        logger.warning("feed.festival.cache_get_failed", error=str(exc))
        cached = None
    if cached:
        payload = json.loads(cached)
        if payload.get("date") == _today().isoformat():
            return [ChannelCardRow(**row) for row in payload["cards"]]
    cards = await fetch_festa_cards(kto, limit=_FESTIVAL_POOL_LIMIT)
    try:
        await redis.set(
            _FESTIVAL_POOL_KEY,
            json.dumps(
                {"date": _today().isoformat(), "cards": [asdict(c) for c in cards]},
                ensure_ascii=False,
            ),
            ex=_FESTIVAL_POOL_TTL,
        )
    except Exception as exc:
        logger.warning("feed.festival.cache_set_failed", error=str(exc))
    return cards
```

`backend/app/modules/feed/services/__init__.py` — `load_festival_pool`을 `kto_channels`에서 import 해 `__all__`에 넣는다:

```python
from app.modules.feed.services.kto_channels import load_festival_pool
```

`backend/app/modules/agent/services/ask.py`:

- import 추가: `from app.modules.feed import services as feed_services`, `from app.core.redis import Redis`
- `ask()` · `_ask_with_question()` 이 `redis: Redis` 를 받도록 시그니처를 넓힌다 (routes에서 `RedisDep` 주입)
- `_ask_with_question()`의 intent 확정 직후:

```python
    if intent.festivalOnly:
        return await _ask_festivals(session, redis, kto, intent=intent, steps=steps)
```

- 새 함수:

```python
async def _ask_festivals(
    session: AsyncSession,
    redis: Redis,
    kto: KtoClient | None,
    *,
    intent: QueryIntent,
    steps: list[AskStep],
) -> AskResponse:
    if kto is None:
        raise AgentNoResults()
    pool = await feed_services.load_festival_pool(redis, kto)
    scoped = _match_region(pool, intent.regionHints)
    fell_back = bool(intent.regionHints) and not scoped
    cards = scoped or pool
    if not cards:
        raise AgentNoResults()
    steps.append(AskStep(tool="festival", label="오늘 열리는 축제 조회", badge=f"{len(cards)}곳"))
    top = cards[: retrieve.RESULT_LIMIT]
    spots = [
        AgentSpotCard(
            contentId=card.content_id or "",
            title=card.title,
            regionLabel=card.region_label,
            imageUrl=t1_display_url(card.image_url, card.cpyrht_div_cd),
            tag=card.dday,
        )
        for card in top
        if card.content_id
    ]
    answer = [
        AnswerSegment(text="오늘 열리는 축제로 "),
        AnswerSegment(text=f"{len(spots)}곳", emphasis=True),
        AnswerSegment(text=" 찾았어요."),
    ]
    if fell_back:
        answer.append(
            AnswerSegment(
                text=f" {intent.regionHints[0]}에는 오늘 열리는 축제가 없어 전국에서 골랐어요."
            )
        )
    return AskResponse(
        steps=steps,
        answer=answer,
        spots=spots,
        totalCount=len(spots),
        intent=intent,
        suggestions=[],
    )


def _match_region(
    cards: list[feed_services.ChannelCardRow], hints: list[str]
) -> list[feed_services.ChannelCardRow]:
    if not hints:
        return []
    return [card for card in cards if any(hint in card.region_label for hint in hints)]
```

`t1_display_url`은 `app.kto.display`에서 import한다.

`backend/app/modules/agent/routes.py` — `RedisDep`를 주입해 `ask_service.ask(session, redis, kto, ...)` 로 넘긴다. `from app.core.redis import RedisDep` 는 다른 라우터의 사용 형태를 그대로 따른다.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest -v && uv run mypy app && uv run lint-imports`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules backend/tests
git commit -m "feat(agent): 오늘 열리는 축제를 조회 축으로 추가한다"
```

---

### Task 9: 모바일 — 조건 삭제와 API 타입 재정의

**Files:**
- Modify: `mobile/src/features/travel/api.ts`
- Delete: `mobile/src/features/travel/components/ConditionSheet.tsx`
- Delete: `mobile/src/features/travel/stores/conditions-store.ts`
- Delete: `mobile/src/features/travel/lib/condition-labels.ts`
- Delete: `mobile/src/features/travel/lib/__tests__/condition-labels.test.ts`
- Modify: `mobile/src/features/travel/components/AskComposer.tsx`
- Modify: `mobile/src/app/(tabs)/travel.tsx`
- Test: `mobile/src/features/travel/__tests__/api.test.ts`

**Interfaces:**
- Consumes: Task 6·7의 백엔드 계약
- Produces:
  - `RefinePatch` · `QueryIntent` · `Suggestion` 타입
  - `AskInput = { question?, photo?, intent?, patch?, coords? }`
  - `AgentAnswer.intent: QueryIntent` · `AgentAnswer.suggestions: Suggestion[]`

- [ ] **Step 1: Write the failing test**

`mobile/src/features/travel/__tests__/api.test.ts` 에서 `conditions`를 쓰는 기존 케이스를 지우고 추가:

```ts
it("refine 요청은 intent와 patch를 함께 보낸다", async () => {
  const post = jest.spyOn(api, "post").mockResolvedValue({} as never);

  await askAgent({
    intent: { categoryKeywords: ["계곡"], regionHints: ["부산"] },
    patch: { crowdPreference: "quiet" },
  });

  expect(post).toHaveBeenCalledWith(
    "/agent/ask",
    expect.objectContaining({
      intent: { categoryKeywords: ["계곡"], regionHints: ["부산"] },
      patch: { crowdPreference: "quiet" },
    }),
    expect.anything(),
  );
});

it("사진 refine은 intent와 patch를 JSON 문자열로 폼에 담는다", async () => {
  const post = jest.spyOn(api, "post").mockResolvedValue({} as never);

  await askAgent({
    photo: { uri: "file://a.jpg", name: "a.jpg", type: "image/jpeg" },
    intent: { categoryKeywords: [] },
    patch: { nearMe: true },
  });

  const form = post.mock.calls[0][1] as FormData;
  expect(form.get("patch")).toBe(JSON.stringify({ nearMe: true }));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npm test -- api.test`
Expected: FAIL — `conditions` 필수 인자 누락 타입 에러 / `patch` 미전송

- [ ] **Step 3: Write minimal implementation**

`mobile/src/features/travel/api.ts`:

```ts
export type CrowdPreference = "quiet" | "any" | "popular";
export type Mood = "sea" | "mountain" | "lake" | "island" | "hanok" | "night" | "street";
export type DropAxis = "crowd" | "indoor" | "near" | "region" | "category";

export interface ExtractedPlace {
  name: string;
  nameKo?: string | null;
  placeType?: string;
  regionHint?: string | null;
}

export interface QueryIntent {
  categoryKeywords: string[];
  regionHints: string[];
  namedPlaces?: ExtractedPlace[];
  moodHints?: Mood[];
  crowdPreference?: CrowdPreference;
  indoorOnly?: boolean;
  nearMe?: boolean;
  festivalOnly?: boolean;
  outOfScope?: boolean;
}

export interface RefinePatch {
  crowdPreference?: CrowdPreference;
  indoorOnly?: boolean;
  nearMe?: boolean;
  drop?: DropAxis;
}

export interface Suggestion {
  label: string;
  patch: RefinePatch;
}
```

- `RegionFilter` · `WhenFilter` · `WhoFilter` · `Conditions` · `DEFAULT_CONDITIONS` 삭제
- `AgentAnswer`의 `suggestions: string[]` → `suggestions: Suggestion[]`, `intent: QueryIntent` 추가
- `AskInput` 교체:

```ts
export interface AskInput {
  question?: string;
  photo?: PhotoUpload | null;
  intent?: QueryIntent | null;
  patch?: RefinePatch | null;
  coords?: Coords | null;
}
```

- `askForm` / `askBody`에서 `region`/`when`/`who` append를 지우고 `intent`·`patch`를 넣는다. multipart는 `JSON.stringify`, JSON 바디는 객체 그대로:

```ts
function askForm(input: AskInput, photo: PhotoUpload): FormData {
  const form = new FormData();
  form.append("photo", photo as unknown as Blob);
  if (input.question) form.append("question", input.question);
  if (input.intent) form.append("intent", JSON.stringify(input.intent));
  if (input.patch) form.append("patch", JSON.stringify(input.patch));
  if (input.coords) {
    form.append("lat", String(input.coords.lat));
    form.append("lng", String(input.coords.lng));
  }
  return form;
}

function askBody(input: AskInput): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (input.question) body.question = input.question;
  if (input.intent) body.intent = input.intent;
  if (input.patch) body.patch = input.patch;
  if (input.coords) {
    body.lat = input.coords.lat;
    body.lng = input.coords.lng;
  }
  return body;
}
```

`ConditionSheet.tsx` · `conditions-store.ts` · `condition-labels.ts` · `condition-labels.test.ts` 를 `git rm` 한다.

`AskComposer.tsx` — `conditionLabel` · `conditionActive` · `onOpenConditions` props와 조건 칩 `<Pressable>` 블록을 삭제한다. `suggestions: string[]` 는 Task 11에서 바꾸므로 지금은 그대로 둔다.

`(tabs)/travel.tsx` — `ConditionSheet` import·렌더, `useConditions`, `conditionChipLabel`/`isNeutral` import, `sheetOpen` 상태, `run()`의 `conditions` 전달을 모두 제거한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mobile && npm run typecheck && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A mobile/src/features/travel mobile/src/app/\(tabs\)/travel.tsx
git commit -m "refactor(travel): 조건 시트를 삭제하고 refine 계약으로 API 타입을 바꾼다"
```

---

### Task 10: 모바일 — 사진 진입 카드

`+` 아이콘 뒤에 숨어 있던 CLIP 매칭을 채널 레일 위 전폭 카드로 올린다. 레일이 아니라 액션 카드다 — `ChannelRail`을 재사용하면 스팟 카드처럼 보여 눌리지 않는다.

**Files:**
- Create: `mobile/src/features/travel/components/PhotoStartCard.tsx`
- Create: `mobile/src/features/travel/components/__tests__/PhotoStartCard.test.tsx`
- Modify: `mobile/src/app/(tabs)/travel.tsx`

**Interfaces:**
- Consumes: `pickTravelPhoto()` (`@/features/travel/usecases/pick-travel-photo`)
- Produces: `<PhotoStartCard onPress={() => void} />` — testID `travel-photo-start`

- [ ] **Step 1: Write the failing test**

`mobile/src/features/travel/components/__tests__/PhotoStartCard.test.tsx`:

```tsx
import renderer, { act } from "react-test-renderer";
import { PhotoStartCard } from "@/features/travel/components/PhotoStartCard";

function findByTestID(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAll((n) => n.props?.testID === id)[0];
}

it("설명과 폐기 고지를 함께 보여준다", () => {
  const tree = renderer.create(<PhotoStartCard onPress={jest.fn()} />);

  const text = JSON.stringify(tree.toJSON());
  expect(text).toContain("사진으로 찾기");
  expect(text).toContain("마음에 든 사진을 올리면 닮은 국내 여행지를 찾아드려요");
  expect(text).toContain("원본은 비교 후 바로 폐기해요");
});

it("탭하면 onPress를 부른다", () => {
  const onPress = jest.fn();
  const tree = renderer.create(<PhotoStartCard onPress={onPress} />);

  act(() => {
    findByTestID(tree, "travel-photo-start").props.onPress();
  });

  expect(onPress).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npm test -- PhotoStartCard`
Expected: FAIL — `Cannot find module '@/features/travel/components/PhotoStartCard'`

- [ ] **Step 3: Write minimal implementation**

`mobile/src/features/travel/components/PhotoStartCard.tsx`:

```tsx
import { Pressable, View, Text, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { ATTACH_NOTICE } from "@/features/travel/components/AskComposer";
import { colors, radii, spacing } from "@/constants/theme";

export const PHOTO_START_TITLE = "사진으로 찾기";
export const PHOTO_START_BODY = "마음에 든 사진을 올리면 닮은 국내 여행지를 찾아드려요";

interface Props {
  onPress: () => void;
}

export function PhotoStartCard({ onPress }: Props) {
  return (
    <Pressable
      testID="travel-photo-start"
      accessibilityRole="button"
      accessibilityLabel={PHOTO_START_TITLE}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={onPress}
    >
      <View style={styles.badge}>
        <Icon name="plus" size={18} color={colors.onImage} strokeWidth={2.2} />
      </View>
      <View style={styles.copy}>
        <Text style={styles.title}>{PHOTO_START_TITLE}</Text>
        <Text style={styles.body}>{PHOTO_START_BODY}</Text>
        <Text style={styles.note}>{ATTACH_NOTICE}</Text>
      </View>
      <Icon name="chevron-right" size={16} color={colors.ter} strokeWidth={2} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: spacing.lg,
    marginHorizontal: spacing.lg,
    padding: spacing.md + 2,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.inset,
  },
  pressed: { backgroundColor: colors.fill },
  badge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
  },
  copy: { flex: 1 },
  title: { fontSize: 15, fontWeight: "800", letterSpacing: -0.3, color: colors.ink },
  body: { marginTop: 3, fontSize: 12.5, lineHeight: 18, color: colors.sec },
  note: { marginTop: 4, fontSize: 11.5, color: colors.ter },
});
```

`(tabs)/travel.tsx` — `lede` 뷰 바로 아래, `SECTIONS.map` 위에 렌더하고 즉시 제출로 연결한다:

```tsx
  const onPhotoStart = useCallback(async () => {
    if (busy) return;
    try {
      const picked = await pickTravelPhoto();
      if (picked) submit("", picked);
    } catch {
      setToast(PHOTO_PICK_FAILED);
    }
  }, [busy, submit]);
```

```tsx
        <PhotoStartCard onPress={() => void onPhotoStart()} />
```

`submit`이 `onPhotoStart`보다 먼저 선언되도록 순서를 맞춘다.

> `travel.tsx` 화면 자체를 렌더하는 테스트 하네스는 이 리포에 없다. 카드 →
> picker → 즉시 제출 배선은 컴포넌트 테스트 + `npm run typecheck` 로만
> 검증된다. 새 화면 테스트를 이번 범위에서 만들지 않는다.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mobile && npm run typecheck && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mobile/src/features/travel/components mobile/src/app/\(tabs\)/travel.tsx
git commit -m "feat(travel): 사진으로 시작하는 진입 카드를 채널 위에 올린다"
```

---

### Task 11: 모바일 — 초기 칩과 refine 배선

**Files:**
- Modify: `mobile/src/features/travel/lib/question.ts`
- Create: `mobile/src/features/travel/lib/chips.ts`
- Create: `mobile/src/features/travel/lib/__tests__/chips.test.ts`
- Modify: `mobile/src/features/travel/components/AskComposer.tsx`
- Modify: `mobile/src/features/travel/components/AnswerBlock.tsx`
- Modify: `mobile/src/features/travel/components/ConversationTurn.tsx`
- Modify: `mobile/src/features/travel/stores/conversation-store.ts`
- Modify: `mobile/src/app/(tabs)/travel.tsx`
- Test: `mobile/src/features/travel/components/__tests__/ConversationTurn.test.tsx`

**Interfaces:**
- Consumes: `Suggestion` · `RefinePatch` · `QueryIntent` (Task 9)
- Produces:
  - `type Chip = { kind: "question"; label: string; question: string } | { kind: "refine"; label: string; patch: RefinePatch }`
  - `idleChips(hasCoords: boolean): Chip[]`
  - `refineChips(suggestions: Suggestion[]): Chip[]`
  - `Turn.intent: QueryIntent | null` — refine 요청이 되돌려 보낼 의도

- [ ] **Step 1: Write the failing test**

`mobile/src/features/travel/lib/__tests__/chips.test.ts`:

```ts
import { idleChips, refineChips } from "@/features/travel/lib/chips";

it("좌표가 없으면 거리 칩을 내지 않는다", () => {
  const labels = idleChips(false).map((c) => c.label);

  expect(labels).not.toContain("여기서 가까운 순");
  expect(labels).toContain("지금 열리는 축제");
});

it("좌표가 있으면 거리 칩이 맨 앞에 온다", () => {
  expect(idleChips(true)[0].label).toBe("여기서 가까운 순");
});

it("초기 칩은 전부 질문형이다", () => {
  expect(idleChips(true).every((c) => c.kind === "question")).toBe(true);
});

it("서버 제안은 patch 칩으로 바뀐다", () => {
  const chips = refineChips([{ label: "실내만", patch: { indoorOnly: true } }]);

  expect(chips).toEqual([{ kind: "refine", label: "실내만", patch: { indoorOnly: true } }]);
});
```

`ConversationTurn.test.tsx`의 `answer` 픽스처에서 `suggestions: ["더 가까운 곳"]` 을 `suggestions: [{ label: "실내만", patch: { indoorOnly: true } }]` 로, `intent: { categoryKeywords: [], regionHints: [] }` 추가로 바꾼다.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && npm test -- chips`
Expected: FAIL — `Cannot find module '@/features/travel/lib/chips'`

- [ ] **Step 3: Write minimal implementation**

`mobile/src/features/travel/lib/chips.ts`:

```ts
import type { RefinePatch, Suggestion } from "@/features/travel/api";

export type Chip =
  | { kind: "question"; label: string; question: string }
  | { kind: "refine"; label: string; patch: RefinePatch };

const NEARBY_CHIP: Chip = {
  kind: "question",
  label: "여기서 가까운 순",
  question: "여기서 가까운 곳",
};

const BASE_CHIPS: Chip[] = [
  { kind: "question", label: "지금 열리는 축제", question: "지금 열리는 축제" },
  { kind: "question", label: "사람 적은 바닷가", question: "사람 적은 바닷가" },
  { kind: "question", label: "비 와도 갈 만한 실내", question: "비 와도 갈 만한 실내" },
  { kind: "question", label: "제주에서 한적한 곳", question: "제주에서 한적한 곳" },
];

export function idleChips(hasCoords: boolean): Chip[] {
  return hasCoords ? [NEARBY_CHIP, ...BASE_CHIPS] : BASE_CHIPS;
}

export function refineChips(suggestions: Suggestion[]): Chip[] {
  return suggestions.map((s) => ({ kind: "refine", label: s.label, patch: s.patch }));
}
```

`question.ts` — `IDLE_SUGGESTIONS` 삭제 (`PHOTO_ONLY_QUESTION` · `RETRY_SUGGESTION` · `composeQuestion` · `resultsTitle` 는 유지).

`conversation-store.ts` — `Turn`에 `intent: QueryIntent | null` 과 `patch: RefinePatch | null` 을 추가하고 `start()`가 받아 저장한다. `retry`는 그대로 두되 `run()`이 저장된 값을 다시 쓴다.

`AnswerBlock.tsx` · `AskComposer.tsx` — `suggestions: string[]` prop을 `chips: Chip[]` 로 바꾸고 `onSuggest: (chip: Chip) => void` 로 바꾼다. `key`와 `testID`는 `chip.label` 기준.

`ConversationTurn.tsx` — `onSuggest` 타입을 `(chip: Chip) => void` 로 바꾸고 `AnswerBlock`에 `chips={refineChips(answer.suggestions)}` 를 넘긴다.

`(tabs)/travel.tsx` — `const lastAnswered = ...` 줄을 **콜백들보다 위로** 올린다
(`submitChip`이 참조한다). 그 다음:

```tsx
  const submitChip = useCallback(
    (chip: Chip) => {
      if (busy) return;
      if (chip.kind === "question") {
        submit(chip.question, null);
        return;
      }
      const base = lastAnswered?.answer?.intent ?? null;
      if (!base) return;
      nextId.current += 1;
      const id = `turn-${nextId.current}`;
      const photo = lastAnswered?.photo ?? null;
      startTurn({ id, question: chip.label, request: "", photo, intent: base, patch: chip.patch });
      scrollToEnd();
      ask.mutate(
        { photo, intent: base, patch: chip.patch, coords },
        {
          onSuccess: (answer) => resolveTurn(id, answer),
          onError: (error) => failTurn(id, agentErrorMessage(error)),
        },
      );
    },
    [busy, submit, lastAnswered, startTurn, scrollToEnd, ask, coords, resolveTurn, failTurn],
  );
```

`chips` 계산을 `const chips = lastAnswered?.answer ? refineChips(lastAnswered.answer.suggestions) : idleChips(coords !== null);` 로 바꾸고, `AskComposer`·`ConversationTurn` 의 `onSuggest`를 `submitChip` 으로 연결한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mobile && npm run lint && npm run typecheck && npm run format:check && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mobile/src
git commit -m "feat(travel): 초기 칩을 실측 축으로 바꾸고 후속 칩을 refine으로 배선한다"
```

---

### Task 12: 문서

**Files:**
- Create: `docs/adr/0010-travel-tab-drops-condition-sheet.md`
- Modify: `docs/reference/api.md`
- Modify: `docs/reference/travel-tab.md`
- Modify: `docs/reference/database-schema.md`

**Interfaces:**
- Consumes: Task 1~11의 최종 계약
- Produces: 없음 (문서)

- [ ] **Step 1: ADR 0010 작성**

`docs/adr/0010-travel-tab-drops-condition-sheet.md` — 기존 ADR 형식(`상태` · `날짜` · `관련` · `맥락` · `결정` · `고려한 대안` · `결과`)을 따른다. 담을 내용:

- 맥락: 조건 3축 중 2축 무동작 + 1축 침묵 무시. `attraction_category_sql()` 재사용으로 전시·공연시설 1,906곳이 여행 탭에서 비가시. 후속 칩이 이전 턴을 잃음. 근거 수치는 스펙 문서의 실측 표를 인용한다
- 결정: 조건 시트 폐기 · 여행 탭 전용 카테고리 술어 분기 · mood 조회 축 승격 · intent 왕복 refine · 축제 축 추가
- 고려한 대안: 클라이언트 문자열 합성 refine(기각 — LLM 재추출이 불안정), `attraction_category_sql()` 자체를 넓히기(기각 — 지도 "주변 관광지"의 의미가 바뀐다)
- 결과: ADR 0009의 "조건 시트의 `언제`는 아직 필터가 아니다" 후속을 닫는다. 범위 밖 항목(pets 채널 · 시장 · 도서관 · 요일별 혼잡도 · 일정 조립)을 명시

- [ ] **Step 2: `docs/reference/api.md` 갱신**

`## POST /agent/ask` 절에서:

- 요청 표의 `region`/`when`/`who` 행을 삭제하고 `intent`(`QueryIntent`, 있으면 Gemini 스킵) · `patch`(`RefinePatch`) 행을 추가
- "세 조건이 실제로 하는 일은 다르다" 표 전체를 삭제
- 응답 표의 `suggestions[]` 를 `{label, patch}` 로 고치고 `intent` 행을 추가
- 필수 입력이 `question` · `photo` · `intent` 셋 중 하나임을 한 줄로 적는다

- [ ] **Step 3: `docs/reference/travel-tab.md` 갱신**

화면 구성(사진 카드 → 채널 3단 → 대화)과 초기 칩 5종·후속 칩 파생 규칙 표를 현재 구현에 맞춘다. 조건 시트 서술을 삭제한다.

- [ ] **Step 4: `docs/reference/database-schema.md` 갱신**

`moods` · `spot_moods` 를 "시드/pipeline 마스터 코드" 행에서 떼어내 **서빙 표면 있음**(agent `mood_search` 축)으로 별도 행에 적는다. `spot_concentration` 행에 실측 커버리지 46%를 덧붙인다.

- [ ] **Step 5: 전체 검증 후 커밋**

```bash
cd backend && NO_COLOR=1 POSTGRES_DB=pictrip_test uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports
cd ../mobile && npm run lint && npm run typecheck && npm run format:check && npm test
cd .. && git add docs && git commit -m "docs: 여행 탭 조건 폐기와 새 조회 축을 기록한다"
```

---

## 완료 후

전체 검증이 green이면 `dev` 대상 PR 1개를 연다. PR 본문은
`.github/pull_request_template.md` 형식(`## 요약` / `## 변경 단위` /
`## 핵심 결정` / `## 검증`)을 따르고, 요약은 불릿 2~4개로 사실 하나씩 적는다.
실측 수치(`박물관 543곳이 0곳으로 잘리고 있었다`, `오늘 열리는 축제 56건`)를
근거로 인용한다.
