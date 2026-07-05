# Pipeline `sync-daily` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the `pictrip-data` pipeline stubs so `sync-daily` actually mirrors KTO `areaBasedSyncList2` into the `spots` table (incremental + soft-delete) and records every run in `sync_runs`.

**Architecture:** Keep the EL thin and category-agnostic — ingest *all* KTO categories as-is; the backend already filters categories at query time. Daily run pulls the `modifiedtime`-since delta (omitting `showflag` so hidden items arrive too), upserts each record with a newer-wins guard, maps `show_flag` from the response `showflag`, and writes counters to `sync_runs`. A weekly `sync-full` (no `modifiedtime`) reconciles anything the delta missed. Enrichment (CLIP embeddings, concentration, detail cache) stays in `backend/scripts/` and is out of scope.

**Tech Stack:** Python 3.12 · Typer (CLI) · httpx (KTO calls) · psycopg[binary] (DB, raw SQL) · pydantic-settings · structlog · pytest. Streamlit for the read-only dashboard.

## Global Constraints

- **Separate Python project** — `pipeline/` has its own `uv` env; **never import `backend/` code**. Only coupling = CT110 tables `spots` + `sync_runs`.
- **`sync_runs` is owned here** — `CREATE TABLE IF NOT EXISTS`. **DO NOT** add it to backend Alembic.
- **DO NOT download/store KTO images** — store `firstimage`/`firstimage2` URLs only.
- **DO NOT modify KTO text** — store verbatim.
- **`serviceKey` is stored URL-decoded** in `.env`; httpx re-encodes it via `params=`. (The prod key on CT112 is the 88-char decoded form.)
- **Run DB tests with `POSTGRES_DB=pictrip_test`** — never the live `pictrip` DB (live rows break count asserts).
- **Base URL** = `http://apis.data.go.kr/B551011/KorService2` (keep configurable — KTO deprecates versioned URLs after 90 days).
- **KTO dev quota = 1,000 calls/day.** Daily delta is cheap; full reconcile (~685 pages) must be infrequent / run on an operating account.
- Files: runtime modules kebab-case is a mobile rule; **pipeline keeps `snake_case` Python module names** (existing convention).

## Confirmed KTO → `spots` field mapping (live-verified 2026-06-28)

| KTO response field | `spots` column | Transform |
|---|---|---|
| `contentid` | `content_id` (PK) | str |
| `contenttypeid` | `content_type_id` | int |
| `title` | `title` | str |
| `addr1` / `addr2` / `zipcode` | same | str, `""` → None |
| `mapx` / `mapy` | `mapx` / `mapy` | str → Decimal, `""` → None |
| `lDongRegnCd` | `ldong_regn_cd` | str; None if unknown code (FK) |
| `lDongRegnCd` **+** `lDongSignguCd` | `ldong_signgu_cd` | **concatenate** to 5-digit; None if unknown code (FK) |
| `lclsSystm1` / `lclsSystm2` / `lclsSystm3` | `lcls_systm1/2/3` | raw; `lcls_systm3` None if unknown code (FK) |
| `cpyrhtDivCd` | `cpyrht_div_cd` | str (`Type1`/`Type3`) |
| `firstimage` / `firstimage2` | `first_image_url` / `first_image2_url` | str, `""` → None |
| `showflag` | `show_flag` | `"0"`/`"1"` → int |
| `modifiedtime` | `modified_time` | `"YYYYMMDDHHMMSS"` → KST tz-aware datetime |
| (server) | `synced_at` | DB `now()` default |

**Gotcha locked in:** response `lDongSignguCd` is the **3-digit** district part only; our FK key is the **5-digit composite** (`43`+`800`=`43800`=단양군). Always concatenate.

---

## File Structure

| File | Responsibility |
|---|---|
| `pipeline/src/pictrip_data/config.py` | `Settings` (database_url, kto_api_key, kto_base_url_kor, kto_mobile_app) |
| `pipeline/src/pictrip_data/db.py` | `connect()` psycopg connection context manager |
| `pipeline/src/pictrip_data/kto/schemas.py` | `KtoSpot` dataclass + `from_kto()` mapping + datetime/Decimal parsers |
| `pipeline/src/pictrip_data/kto/client.py` | `KtoClient.area_based_sync_list()` — paged fetch + retry/backoff |
| `pipeline/src/pictrip_data/sync/refcodes.py` | `load_ref_codes()` — known regn/signgu/lcls3 sets for FK null-out |
| `pipeline/src/pictrip_data/sync/upsert.py` | `upsert_spots()` — ON CONFLICT + newer-wins + FK null-out + counters |
| `pipeline/src/pictrip_data/sync/audit.py` | `record_run()` lifecycle + `last_success_watermark()` (DDL already present) |
| `pipeline/src/pictrip_data/sync/daily.py` | `sync_daily()` / `sync_full()` orchestration |
| `pipeline/src/pictrip_data/cli.py` | Typer commands `sync-daily`, `sync-full`, `load-codes` |
| `pipeline/src/pictrip_data/dashboard/app.py` | Streamlit read-only `sync_runs` view |
| `pipeline/tests/fixtures/sync_list_response.json` | Real `areaBasedSyncList2` payload (2 items) |
| `pipeline/tests/conftest.py` | `db_conn` fixture: connect `pictrip_test`, transaction rollback |
| `pipeline/tests/test_*.py` | Per-module tests |

---

## Task 1: Config + DB connection

**Files:**
- Modify: `pipeline/src/pictrip_data/config.py`
- Modify: `pipeline/src/pictrip_data/db.py`
- Modify: `pipeline/pyproject.toml` (ensure deps)
- Test: `pipeline/tests/test_config.py`

**Interfaces:**
- Produces: `settings` singleton with `.database_url: str`, `.kto_api_key: str`, `.kto_base_url_kor: str`, `.kto_mobile_app: str`.
- Produces: `connect() -> ContextManager[psycopg.Connection]` (autocommit off).

- [ ] **Step 1: Write the failing test**

```python
# pipeline/tests/test_config.py
from pictrip_data.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.kto_base_url_kor == "http://apis.data.go.kr/B551011/KorService2"
    assert s.kto_mobile_app == "PicTrip"


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("KTO_API_KEY", "decoded-key-123")
    s = Settings(_env_file=None)
    assert s.kto_api_key == "decoded-key-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && uv run pytest tests/test_config.py -v`
Expected: FAIL — `kto_base_url_kor` / `kto_mobile_app` attributes missing.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/src/pictrip_data/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://pictrip:pictrip_dev_only@localhost:5432/pictrip"
    # Stored URL-DECODED; httpx re-encodes via params=.
    kto_api_key: str = ""
    kto_base_url_kor: str = "http://apis.data.go.kr/B551011/KorService2"
    kto_mobile_app: str = "PicTrip"


settings = Settings()
```

```python
# pipeline/src/pictrip_data/db.py
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from pictrip_data.config import settings


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """One psycopg connection, autocommit off (caller commits per page)."""
    conn = psycopg.connect(settings.database_url, autocommit=False)
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline && uv run pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/pictrip_data/config.py pipeline/src/pictrip_data/db.py pipeline/tests/test_config.py pipeline/pyproject.toml
git commit -m "feat(pipeline): config settings + db connection helper"
```

---

## Task 2: `KtoSpot` schema + mapping (pure functions, real fixture)

**Files:**
- Create: `pipeline/tests/fixtures/sync_list_response.json`
- Modify: `pipeline/src/pictrip_data/kto/schemas.py`
- Test: `pipeline/tests/test_schemas.py`

**Interfaces:**
- Produces: `@dataclass KtoSpot` with fields: `content_id: str`, `content_type_id: int`, `title: str`, `addr1/addr2/zipcode: str | None`, `mapx/mapy: Decimal | None`, `ldong_regn_cd: str | None`, `ldong_signgu_cd: str | None`, `lcls_systm1/2/3: str | None`, `cpyrht_div_cd: str | None`, `first_image_url/first_image2_url: str | None`, `show_flag: int`, `modified_time: datetime | None`.
- Produces: `KtoSpot.from_kto(raw: dict) -> KtoSpot` classmethod.
- Produces helpers: `_blank_to_none(v: str | None) -> str | None`, `_to_decimal(v) -> Decimal | None`, `parse_modifiedtime(v: str | None) -> datetime | None`.

- [ ] **Step 1: Create the fixture from the live CT112 response**

```json
{
  "response": {
    "header": { "resultCode": "0000", "resultMsg": "OK" },
    "body": {
      "items": { "item": [
        {
          "addr1": "충청북도 단양군 단양읍 상진리", "addr2": "122-1", "areacode": "33",
          "cat1": "A02", "cat2": "A0208", "cat3": "A02081200",
          "contentid": "2865520", "contenttypeid": "15", "createdtime": "20221011175314",
          "firstimage": "http://tong.visitkorea.or.kr/cms/resource/60/3501060_image2_1.jpeg",
          "firstimage2": "http://tong.visitkorea.or.kr/cms/resource/60/3501060_image3_1.jpeg",
          "cpyrhtDivCd": "Type3", "mapx": "128.3514221857", "mapy": "36.9799499876",
          "mlevel": "6", "modifiedtime": "20260627043000", "sigungucode": "2",
          "tel": "043-421-7330", "title": "2025 단양레이크파크 수상페스티벌", "zipcode": "27027",
          "showflag": "0", "lDongRegnCd": "43", "lDongSignguCd": "800",
          "lclsSystm1": "EV", "lclsSystm2": "EV03", "lclsSystm3": "EV030300"
        },
        {
          "addr1": "서울특별시 종로구 세종대로 175 (세종로)", "addr2": "", "areacode": "",
          "cat1": "", "cat2": "", "cat3": "",
          "contentid": "3509884", "contenttypeid": "15", "createdtime": "20250718170529",
          "firstimage": "https://tong.visitkorea.or.kr/cms/resource/04/4079504_image2_1.png",
          "firstimage2": "https://tong.visitkorea.or.kr/cms/resource/04/4079504_image3_1.png",
          "cpyrhtDivCd": "Type3", "mapx": "126.9761682759", "mapy": "37.5718478585",
          "mlevel": "6", "modifiedtime": "20260626183808", "sigungucode": "",
          "tel": "02-6941-0645", "title": "서울썸머비치", "zipcode": "03172",
          "showflag": "1", "lDongRegnCd": "11", "lDongSignguCd": "110",
          "lclsSystm1": "EV", "lclsSystm2": "EV01", "lclsSystm3": "EV010600"
        }
      ] },
      "numOfRows": 2, "pageNo": 1, "totalCount": 68433
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# pipeline/tests/test_schemas.py
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from pictrip_data.kto.schemas import KtoSpot, parse_modifiedtime

FIXTURE = Path(__file__).parent / "fixtures" / "sync_list_response.json"


def _items():
    return json.loads(FIXTURE.read_text())["response"]["body"]["items"]["item"]


def test_from_kto_maps_core_fields():
    spot = KtoSpot.from_kto(_items()[0])
    assert spot.content_id == "2865520"
    assert spot.content_type_id == 15
    assert spot.mapx == Decimal("128.3514221857")
    assert spot.first_image_url.startswith("http://tong.visitkorea")
    assert spot.cpyrht_div_cd == "Type3"


def test_signgu_code_is_composite():
    # lDongRegnCd 43 + lDongSignguCd 800 -> 43800 (단양군)
    assert KtoSpot.from_kto(_items()[0]).ldong_signgu_cd == "43800"
    assert KtoSpot.from_kto(_items()[1]).ldong_signgu_cd == "11110"


def test_showflag_to_int():
    assert KtoSpot.from_kto(_items()[0]).show_flag == 0
    assert KtoSpot.from_kto(_items()[1]).show_flag == 1


def test_blank_strings_become_none():
    spot = KtoSpot.from_kto(_items()[1])
    assert spot.addr2 is None


def test_parse_modifiedtime_kst():
    dt = parse_modifiedtime("20260627043000")
    assert dt == datetime(2026, 6, 27, 4, 30, 0, tzinfo=ZoneInfo("Asia/Seoul"))


def test_missing_signgu_part_yields_none():
    raw = dict(_items()[0])
    raw["lDongSignguCd"] = ""
    assert KtoSpot.from_kto(raw).ldong_signgu_cd is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd pipeline && uv run pytest tests/test_schemas.py -v`
Expected: FAIL — `KtoSpot.from_kto` / `parse_modifiedtime` not defined.

- [ ] **Step 4: Write minimal implementation**

```python
# pipeline/src/pictrip_data/kto/schemas.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")


def _blank_to_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_decimal(v: Any) -> Decimal | None:
    s = _blank_to_none(v)
    if s is None:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def parse_modifiedtime(v: Any) -> datetime | None:
    s = _blank_to_none(v)
    if s is None or len(s) != 14:
        return None
    return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=_KST)


def _signgu_composite(raw: dict[str, Any]) -> str | None:
    regn = _blank_to_none(raw.get("lDongRegnCd"))
    signgu = _blank_to_none(raw.get("lDongSignguCd"))
    if regn is None or signgu is None:
        return None
    return f"{regn}{signgu}"


@dataclass
class KtoSpot:
    content_id: str
    content_type_id: int
    title: str
    addr1: str | None
    addr2: str | None
    zipcode: str | None
    mapx: Decimal | None
    mapy: Decimal | None
    ldong_regn_cd: str | None
    ldong_signgu_cd: str | None
    lcls_systm1: str | None
    lcls_systm2: str | None
    lcls_systm3: str | None
    cpyrht_div_cd: str | None
    first_image_url: str | None
    first_image2_url: str | None
    show_flag: int
    modified_time: datetime | None

    @classmethod
    def from_kto(cls, raw: dict[str, Any]) -> KtoSpot:
        return cls(
            content_id=str(raw["contentid"]),
            content_type_id=int(raw["contenttypeid"]),
            title=str(raw.get("title", "")).strip(),
            addr1=_blank_to_none(raw.get("addr1")),
            addr2=_blank_to_none(raw.get("addr2")),
            zipcode=_blank_to_none(raw.get("zipcode")),
            mapx=_to_decimal(raw.get("mapx")),
            mapy=_to_decimal(raw.get("mapy")),
            ldong_regn_cd=_blank_to_none(raw.get("lDongRegnCd")),
            ldong_signgu_cd=_signgu_composite(raw),
            lcls_systm1=_blank_to_none(raw.get("lclsSystm1")),
            lcls_systm2=_blank_to_none(raw.get("lclsSystm2")),
            lcls_systm3=_blank_to_none(raw.get("lclsSystm3")),
            cpyrht_div_cd=_blank_to_none(raw.get("cpyrhtDivCd")),
            first_image_url=_blank_to_none(raw.get("firstimage")),
            first_image2_url=_blank_to_none(raw.get("firstimage2")),
            show_flag=int(str(raw.get("showflag", "1")).strip() or "1"),
            modified_time=parse_modifiedtime(raw.get("modifiedtime")),
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pipeline && uv run pytest tests/test_schemas.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add pipeline/src/pictrip_data/kto/schemas.py pipeline/tests/test_schemas.py pipeline/tests/fixtures/sync_list_response.json
git commit -m "feat(pipeline): KtoSpot mapping with composite signgu + KST modifiedtime"
```

---

## Task 3: `KtoClient.area_based_sync_list` — paging + retry

**Files:**
- Modify: `pipeline/src/pictrip_data/kto/client.py`
- Test: `pipeline/tests/test_client.py`

**Interfaces:**
- Consumes: `settings` (Task 1).
- Produces: `KtoClient(client: httpx.Client | None = None)`; method `area_based_sync_list(self, *, page: int, rows: int = 100, modifiedtime: str | None = None) -> tuple[list[dict], int]` returning `(items, total_count)`. Omits `showflag` so hidden items are included. Retries on transient errors.

- [ ] **Step 1: Write the failing test**

```python
# pipeline/tests/test_client.py
import json
from pathlib import Path

import httpx

from pictrip_data.kto.client import KtoClient

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sync_list_response.json").read_text())


def _client(handler):
    transport = httpx.MockTransport(handler)
    return KtoClient(client=httpx.Client(transport=transport))


def test_returns_items_and_total():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "areaBasedSyncList2" in str(request.url)
        assert request.url.params.get("_type") == "json"
        assert request.url.params.get("showflag") is None  # omitted to receive hidden
        assert request.url.params.get("arrange") == "C"
        return httpx.Response(200, json=FIXTURE)

    items, total = _client(handler).area_based_sync_list(page=1)
    assert total == 68433
    assert len(items) == 2
    assert items[0]["contentid"] == "2865520"


def test_passes_modifiedtime_when_given():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["mt"] = request.url.params.get("modifiedtime")
        return httpx.Response(200, json=FIXTURE)

    _client(handler).area_based_sync_list(page=1, modifiedtime="20260627")
    assert seen["mt"] == "20260627"


def test_empty_body_returns_empty_list():
    empty = {"response": {"header": {"resultCode": "0000"}, "body": {"items": "", "totalCount": 0}}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=empty)

    items, total = _client(handler).area_based_sync_list(page=99)
    assert items == []
    assert total == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && uv run pytest tests/test_client.py -v`
Expected: FAIL — `area_based_sync_list` returns `[]` (current stub) / signature mismatch.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/src/pictrip_data/kto/client.py
from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pictrip_data.config import settings

_OPERATION = "areaBasedSyncList2"


class KtoClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=settings.kto_base_url_kor,
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    def close(self) -> None:
        self._client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def area_based_sync_list(
        self, *, page: int, rows: int = 100, modifiedtime: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """One page of the sync list. showflag omitted on purpose so hidden
        (showflag=0) items arrive and can be soft-deleted."""
        params = {
            "serviceKey": settings.kto_api_key,
            "MobileOS": "ETC",
            "MobileApp": settings.kto_mobile_app,
            "_type": "json",
            "arrange": "C",  # by modified date
            "numOfRows": rows,
            "pageNo": page,
        }
        if modifiedtime is not None:
            params["modifiedtime"] = modifiedtime

        url = f"{settings.kto_base_url_kor}/{_OPERATION}"
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        body = resp.json().get("response", {}).get("body", {})
        total = int(body.get("totalCount") or 0)
        items = body.get("items")
        if not items or items == "":
            return [], total
        item = items.get("item", [])
        return (item if isinstance(item, list) else [item]), total
```

> Note: when constructed with a `MockTransport` client, `base_url` is unset; the absolute `url` passed to `.get()` keeps requests routable in tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline && uv run pytest tests/test_client.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/pictrip_data/kto/client.py pipeline/tests/test_client.py
git commit -m "feat(pipeline): areaBasedSyncList2 paged client with retry"
```

---

## Task 4: Reference codes + `upsert_spots`

**Files:**
- Create: `pipeline/src/pictrip_data/sync/refcodes.py`
- Modify: `pipeline/src/pictrip_data/sync/upsert.py`
- Create: `pipeline/tests/conftest.py`
- Test: `pipeline/tests/test_upsert.py`

**Interfaces:**
- Consumes: `KtoSpot` (Task 2), `psycopg.Connection`.
- Produces: `@dataclass RefCodes(regn: set[str], signgu: set[str], lcls3: set[str])`; `load_ref_codes(conn) -> RefCodes`.
- Produces: `upsert_spots(conn, spots: list[KtoSpot], refs: RefCodes, counters: dict[str, int]) -> None` — mutates `counters` keys `inserted`/`updated`/`soft_deleted`/`skipped`. Applies FK null-out (unknown regn/signgu/lcls3 → NULL) and the newer-wins guard.

- [ ] **Step 1: Write the conftest DB fixture**

> **Isolation note (verified 2026-06-28):** `record_run` (Task 5) and `sync_daily` (Task 6) call `conn.commit()` internally, so a transaction-rollback fixture does NOT isolate them — committed `sync_runs`/`spots` rows survive. We use **explicit cleanup** instead: truncate `sync_runs` and delete test `content_id`s before and after each test. Verified NOT NULL columns: `regions(ldong_regn_cd, ldong_regn_nm)`, `sigungus(ldong_regn_cd, ldong_signgu_cd, ldong_signgu_nm)`, `lcls_systm_codes(lcls_systm3_cd, lcls_systm3_nm)` — the seed below satisfies all. `pictrip_test` is at alembic head `0016` with `regions` pre-seeded (17 rows); `sigungus`/`lcls_systm_codes` are empty, which is why `seed_refs` inserts its own FK targets.

```python
# pipeline/tests/conftest.py
import os

import psycopg
import pytest

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://pictrip:pictrip_dev_only@localhost:5432/pictrip_test",
)

# Every test content_id starts with this prefix so cleanup is targeted.
TEST_PREFIX = "T"
# Real fixture ids used by sync_daily test (not prefixed) — clean these too.
FIXTURE_IDS = ("2865520", "3509884")


def _cleanup(conn: psycopg.Connection) -> None:
    cur = conn.cursor()
    # sync_runs may not exist yet on a fresh DB; ignore if missing.
    cur.execute(
        "DELETE FROM spots WHERE content_id LIKE %s OR content_id = ANY(%s)",
        (TEST_PREFIX + "%", list(FIXTURE_IDS)),
    )
    cur.execute("TRUNCATE sync_runs RESTART IDENTITY")
    conn.commit()


@pytest.fixture
def db_conn():
    """Connect to pictrip_test (schema = backend Alembic head). Explicit cleanup
    before and after, because record_run/sync_daily commit mid-test."""
    conn = psycopg.connect(TEST_DSN, autocommit=False)
    # Ensure sync_runs exists so TRUNCATE/DELETE never error.
    from pictrip_data.sync.audit import ensure_table

    ensure_table(conn)
    conn.commit()
    _cleanup(conn)
    try:
        yield conn
    finally:
        _cleanup(conn)
        conn.close()


@pytest.fixture
def seed_refs(db_conn):
    """Insert one region/sigungu/lcls code so FK targets exist, then COMMIT
    (so commits inside record_run/upsert can see them)."""
    cur = db_conn.cursor()
    cur.execute("INSERT INTO regions (ldong_regn_cd, ldong_regn_nm) VALUES ('11','서울특별시') ON CONFLICT DO NOTHING")
    cur.execute(
        "INSERT INTO sigungus (ldong_regn_cd, ldong_signgu_cd, ldong_signgu_nm) "
        "VALUES ('11','11110','종로구') ON CONFLICT DO NOTHING"
    )
    cur.execute(
        "INSERT INTO lcls_systm_codes (lcls_systm3_cd, lcls_systm3_nm) "
        "VALUES ('EV010600','문화행사') ON CONFLICT DO NOTHING"
    )
    db_conn.commit()
    return db_conn
```

> **Ordering caveat:** Task 4's `test_upsert.py` is written assuming a rollback fixture but now runs against explicit-cleanup. That's fine — its assertions read rows it just wrote, and cleanup runs between tests. No test asserts a globally-empty `spots`. The only emptiness assertion, `test_last_success_watermark_none_when_empty` (Task 5), is satisfied because `_cleanup` truncates `sync_runs` before each test.

- [ ] **Step 2: Write the failing test**

```python
# pipeline/tests/test_upsert.py
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from pictrip_data.kto.schemas import KtoSpot
from pictrip_data.sync.refcodes import RefCodes, load_ref_codes
from pictrip_data.sync.upsert import upsert_spots

KST = ZoneInfo("Asia/Seoul")


def _spot(**over):
    base = dict(
        content_id="T1", content_type_id=15, title="t", addr1=None, addr2=None,
        zipcode=None, mapx=Decimal("126.9"), mapy=Decimal("37.5"),
        ldong_regn_cd="11", ldong_signgu_cd="11110", lcls_systm1="EV",
        lcls_systm2="EV01", lcls_systm3="EV010600", cpyrht_div_cd="Type3",
        first_image_url="http://img", first_image2_url=None, show_flag=1,
        modified_time=datetime(2026, 6, 27, 4, 30, tzinfo=KST),
    )
    base.update(over)
    return KtoSpot(**base)


def _read(conn, cid):
    cur = conn.cursor()
    cur.execute("SELECT show_flag, modified_time, ldong_signgu_cd FROM spots WHERE content_id=%s", (cid,))
    return cur.fetchone()


def test_insert_then_idempotent_update(seed_refs):
    conn = seed_refs
    refs = load_ref_codes(conn)
    c = {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0}
    upsert_spots(conn, [_spot()], refs, c)
    assert c["inserted"] == 1
    assert _read(conn, "T1")[0] == 1

    c2 = {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0}
    newer = _spot(show_flag=0, modified_time=datetime(2026, 6, 28, 1, 0, tzinfo=KST))
    upsert_spots(conn, [newer], refs, c2)
    assert c2["soft_deleted"] == 1
    assert _read(conn, "T1")[0] == 0  # hidden


def test_newer_wins_guard_blocks_stale(seed_refs):
    conn = seed_refs
    refs = load_ref_codes(conn)
    upsert_spots(conn, [_spot(title="new", modified_time=datetime(2026, 6, 27, 4, 30, tzinfo=KST))],
                 refs, {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0})
    # older modified_time must NOT overwrite
    upsert_spots(conn, [_spot(title="stale", modified_time=datetime(2020, 1, 1, tzinfo=KST))],
                 refs, {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0})
    cur = conn.cursor()
    cur.execute("SELECT title FROM spots WHERE content_id='T1'")
    assert cur.fetchone()[0] == "new"


def test_unknown_fk_codes_nulled(seed_refs):
    conn = seed_refs
    refs = load_ref_codes(conn)
    spot = _spot(content_id="T2", ldong_signgu_cd="99999", lcls_systm3="ZZ999999")
    upsert_spots(conn, [spot], refs, {"inserted": 0, "updated": 0, "soft_deleted": 0, "skipped": 0})
    cur = conn.cursor()
    cur.execute("SELECT ldong_signgu_cd, lcls_systm3 FROM spots WHERE content_id='T2'")
    assert cur.fetchone() == (None, None)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_upsert.py -v`
Expected: FAIL — `refcodes` / `upsert_spots` not implemented.

- [ ] **Step 4: Write minimal implementation**

```python
# pipeline/src/pictrip_data/sync/refcodes.py
from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass
class RefCodes:
    regn: set[str]
    signgu: set[str]
    lcls3: set[str]


def load_ref_codes(conn: psycopg.Connection) -> RefCodes:
    cur = conn.cursor()
    cur.execute("SELECT ldong_regn_cd FROM regions")
    regn = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT ldong_signgu_cd FROM sigungus")
    signgu = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT lcls_systm3_cd FROM lcls_systm_codes")
    lcls3 = {r[0] for r in cur.fetchall()}
    return RefCodes(regn=regn, signgu=signgu, lcls3=lcls3)
```

```python
# pipeline/src/pictrip_data/sync/upsert.py
from __future__ import annotations

import psycopg

from pictrip_data.kto.schemas import KtoSpot
from pictrip_data.sync.refcodes import RefCodes

_COLS = (
    "content_id", "content_type_id", "title", "addr1", "addr2", "zipcode",
    "mapx", "mapy", "ldong_regn_cd", "ldong_signgu_cd", "lcls_systm1",
    "lcls_systm2", "lcls_systm3", "cpyrht_div_cd", "first_image_url",
    "first_image2_url", "show_flag", "modified_time",
)

_UPDATE = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLS if c != "content_id")

_SQL = f"""
INSERT INTO spots ({", ".join(_COLS)})
VALUES ({", ".join("%s" for _ in _COLS)})
ON CONFLICT (content_id) DO UPDATE SET {_UPDATE}, synced_at = now()
WHERE spots.modified_time IS NULL OR spots.modified_time < EXCLUDED.modified_time
RETURNING (xmax = 0) AS inserted, show_flag
"""


def _row(spot: KtoSpot, refs: RefCodes) -> tuple:
    regn = spot.ldong_regn_cd if spot.ldong_regn_cd in refs.regn else None
    signgu = spot.ldong_signgu_cd if spot.ldong_signgu_cd in refs.signgu else None
    lcls3 = spot.lcls_systm3 if spot.lcls_systm3 in refs.lcls3 else None
    return (
        spot.content_id, spot.content_type_id, spot.title, spot.addr1, spot.addr2,
        spot.zipcode, spot.mapx, spot.mapy, regn, signgu, spot.lcls_systm1,
        spot.lcls_systm2, lcls3, spot.cpyrht_div_cd, spot.first_image_url,
        spot.first_image2_url, spot.show_flag, spot.modified_time,
    )


def upsert_spots(
    conn: psycopg.Connection, spots: list[KtoSpot], refs: RefCodes, counters: dict[str, int]
) -> None:
    cur = conn.cursor()
    for spot in spots:
        cur.execute(_SQL, _row(spot, refs))
        result = cur.fetchone()
        if result is None:
            counters["skipped"] += 1  # newer-wins guard blocked a stale row
            continue
        inserted, show_flag = result
        if show_flag == 0:
            counters["soft_deleted"] += 1
        elif inserted:
            counters["inserted"] += 1
        else:
            counters["updated"] += 1
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_upsert.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add pipeline/src/pictrip_data/sync/refcodes.py pipeline/src/pictrip_data/sync/upsert.py pipeline/tests/conftest.py pipeline/tests/test_upsert.py
git commit -m "feat(pipeline): spots upsert with newer-wins guard + FK null-out"
```

---

## Task 5: Audit `record_run` + `last_success_watermark`

**Files:**
- Modify: `pipeline/src/pictrip_data/sync/audit.py`
- Test: `pipeline/tests/test_audit.py`

**Interfaces:**
- Consumes: `psycopg.Connection`.
- Produces: `ensure_table(conn) -> None` (keep existing DDL).
- Produces: `record_run(conn, mode: str) -> ContextManager[dict[str, int]]` — INSERTs a `running` row, yields a counters dict (keys `api_calls, fetched, inserted, updated, soft_deleted, skipped`, plus `watermark_from`/`watermark_to` set by caller), finalizes to `success`/`error` with `finished_at`, `duration_sec`.
- Produces: `last_success_watermark(conn) -> datetime | None` — newest `watermark_to` among `status='success'` runs.

- [ ] **Step 1: Write the failing test**

```python
# pipeline/tests/test_audit.py
import pytest

from pictrip_data.sync.audit import ensure_table, last_success_watermark, record_run


def _latest(conn):
    cur = conn.cursor()
    cur.execute("SELECT status, fetched, inserted, duration_sec FROM sync_runs ORDER BY id DESC LIMIT 1")
    return cur.fetchone()


def test_record_run_success(db_conn):
    ensure_table(db_conn)
    with record_run(db_conn, "daily") as c:
        c["fetched"] = 5
        c["inserted"] = 5
    status, fetched, inserted, duration = _latest(db_conn)
    assert status == "success"
    assert (fetched, inserted) == (5, 5)
    assert duration is not None and duration >= 0


def test_record_run_error_reraises(db_conn):
    ensure_table(db_conn)
    with pytest.raises(ValueError):
        with record_run(db_conn, "daily"):
            raise ValueError("boom")
    assert _latest(db_conn)[0] == "error"


def test_last_success_watermark_none_when_empty(db_conn):
    ensure_table(db_conn)
    assert last_success_watermark(db_conn) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_audit.py -v`
Expected: FAIL — `record_run` yields counters but never writes the row; `last_success_watermark` undefined.

- [ ] **Step 3: Write minimal implementation** (replace the stub body; keep `ensure_table` DDL)

```python
# pipeline/src/pictrip_data/sync/audit.py  (record_run + new helper)
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

import psycopg


@contextmanager
def record_run(conn: psycopg.Connection, mode: str) -> Iterator[dict]:
    ensure_table(conn)
    counters: dict = {
        "api_calls": 0, "fetched": 0, "inserted": 0, "updated": 0,
        "soft_deleted": 0, "skipped": 0, "watermark_from": None, "watermark_to": None,
    }
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sync_runs (status, mode) VALUES ('running', %s) RETURNING id", (mode,)
    )
    run_id = cur.fetchone()[0]
    conn.commit()
    start = time.monotonic()
    try:
        yield counters
    except Exception as exc:
        conn.rollback()
        cur.execute(
            "UPDATE sync_runs SET status='error', finished_at=now(), "
            "duration_sec=%s, error=%s WHERE id=%s",
            (time.monotonic() - start, str(exc)[:2000], run_id),
        )
        conn.commit()
        raise
    else:
        cur.execute(
            "UPDATE sync_runs SET status='success', finished_at=now(), duration_sec=%s, "
            "watermark_from=%s, watermark_to=%s, api_calls=%s, fetched=%s, inserted=%s, "
            "updated=%s, soft_deleted=%s, skipped=%s WHERE id=%s",
            (
                time.monotonic() - start, counters["watermark_from"], counters["watermark_to"],
                counters["api_calls"], counters["fetched"], counters["inserted"],
                counters["updated"], counters["soft_deleted"], counters["skipped"], run_id,
            ),
        )
        conn.commit()


def last_success_watermark(conn: psycopg.Connection) -> datetime | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT watermark_to FROM sync_runs WHERE status='success' AND watermark_to IS NOT NULL "
        "ORDER BY watermark_to DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row[0] if row else None
```

> The error path commits an `error` row even though the run's data writes were rolled back — the audit row itself is committed separately right after INSERT, so the `UPDATE` targets an existing row.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_audit.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/pictrip_data/sync/audit.py pipeline/tests/test_audit.py
git commit -m "feat(pipeline): record_run lifecycle + watermark resolution"
```

---

## Task 6: `sync_daily` / `sync_full` orchestration

**Files:**
- Modify: `pipeline/src/pictrip_data/sync/daily.py`
- Test: `pipeline/tests/test_sync_daily.py`

**Interfaces:**
- Consumes: `KtoClient` (Task 3), `upsert_spots`/`load_ref_codes` (Task 4), `record_run`/`last_success_watermark` (Task 5).
- Produces: `sync_daily(mode: str = "daily", client: KtoClient | None = None, conn=None) -> None` and `sync_full(client=None, conn=None) -> None`. `client`/`conn` params exist for test injection; production path builds them from `settings`.
- Produces helper: `watermark_param(wm: datetime | None) -> str | None` → `wm.strftime("%Y%m%d")` or None.

- [ ] **Step 1: Write the failing test**

```python
# pipeline/tests/test_sync_daily.py
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pictrip_data.sync import daily as daily_mod
from pictrip_data.sync.audit import ensure_table
from pictrip_data.sync.daily import sync_daily, watermark_param

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sync_list_response.json").read_text())
ITEMS = FIXTURE["response"]["body"]["items"]["item"]


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def area_based_sync_list(self, *, page, rows=100, modifiedtime=None):
        self.calls.append((page, modifiedtime))
        return self.pages.get(page, ([], 2))


def test_watermark_param_formats_date():
    assert watermark_param(datetime(2026, 6, 27, 4, 30, tzinfo=ZoneInfo("Asia/Seoul"))) == "20260627"
    assert watermark_param(None) is None


def test_sync_daily_pages_until_empty_and_records(seed_refs):
    conn = seed_refs
    ensure_table(conn)
    # page 1 returns the 2 fixture items (content T uses real ids), page 2 empty
    client = FakeClient({1: (ITEMS, 2)})
    sync_daily(mode="daily", client=client, conn=conn)

    cur = conn.cursor()
    cur.execute("SELECT status, fetched FROM sync_runs ORDER BY id DESC LIMIT 1")
    status, fetched = cur.fetchone()
    assert status == "success"
    assert fetched == 2
    # second item (showflag=1) is visible, first (showflag=0) hidden
    cur.execute("SELECT show_flag FROM spots WHERE content_id='3509884'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT show_flag FROM spots WHERE content_id='2865520'")
    assert cur.fetchone()[0] == 0
```

> The seed fixture only inserts region `11`/sigungu `11110`; item `2865520` (regn 43) will FK-null its codes, which is fine — the test asserts `show_flag`, not codes.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_sync_daily.py -v`
Expected: FAIL — `sync_daily` / `watermark_param` not implemented.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/src/pictrip_data/sync/daily.py
from __future__ import annotations

from datetime import datetime

from pictrip_data.db import connect
from pictrip_data.kto.client import KtoClient
from pictrip_data.kto.schemas import KtoSpot
from pictrip_data.sync.audit import last_success_watermark, record_run
from pictrip_data.sync.refcodes import load_ref_codes
from pictrip_data.sync.upsert import upsert_spots


def watermark_param(wm: datetime | None) -> str | None:
    return wm.strftime("%Y%m%d") if wm is not None else None


def _run(mode: str, modifiedtime: str | None, client: KtoClient, conn) -> None:
    refs = load_ref_codes(conn)
    with record_run(conn, mode) as c:
        c["watermark_from"] = None  # set below from prior success if daily
        max_seen: datetime | None = None
        page = 1
        while True:
            items, _total = client.area_based_sync_list(page=page, modifiedtime=modifiedtime)
            c["api_calls"] += 1
            if not items:
                break
            spots = [KtoSpot.from_kto(x) for x in items]
            c["fetched"] += len(spots)
            upsert_spots(conn, spots, refs, c)
            conn.commit()
            for s in spots:
                if s.modified_time and (max_seen is None or s.modified_time > max_seen):
                    max_seen = s.modified_time
            page += 1
        c["watermark_to"] = max_seen


def sync_daily(mode: str = "daily", client: KtoClient | None = None, conn=None) -> None:
    owns_client = client is None
    owns_conn = conn is None
    client = client or KtoClient()
    if owns_conn:
        with connect() as conn:
            wm = last_success_watermark(conn)
            _run(mode, watermark_param(wm), client, conn)
    else:
        wm = last_success_watermark(conn)
        _run(mode, watermark_param(wm), client, conn)
    if owns_client:
        client.close()


def sync_full(client: KtoClient | None = None, conn=None) -> None:
    """Full reconcile — no modifiedtime filter (~685 pages; quota-aware, weekly)."""
    owns_client = client is None
    client = client or KtoClient()
    if conn is None:
        with connect() as conn:
            _run("full", None, client, conn)
    else:
        _run("full", None, client, conn)
    if owns_client:
        client.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_sync_daily.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/pictrip_data/sync/daily.py pipeline/tests/test_sync_daily.py
git commit -m "feat(pipeline): sync_daily/sync_full orchestration with watermark"
```

---

## Task 7: CLI wiring

**Files:**
- Modify: `pipeline/src/pictrip_data/cli.py`
- Test: `pipeline/tests/test_cli.py`

**Interfaces:**
- Consumes: `sync_daily`, `sync_full` (Task 6), `load_codes` (existing stub — left as-is, see note).
- Produces: Typer app with commands `sync-daily`, `sync-full`, `load-codes`.

- [ ] **Step 1: Write the failing test**

```python
# pipeline/tests/test_cli.py
from unittest.mock import patch

from typer.testing import CliRunner

from pictrip_data.cli import app

runner = CliRunner()


def test_sync_daily_command_invokes_sync():
    with patch("pictrip_data.cli.sync_daily") as m:
        result = runner.invoke(app, ["sync-daily"])
    assert result.exit_code == 0
    m.assert_called_once()


def test_sync_full_command_invokes_full():
    with patch("pictrip_data.cli.sync_full") as m:
        result = runner.invoke(app, ["sync-full"])
    assert result.exit_code == 0
    m.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && uv run pytest tests/test_cli.py -v`
Expected: FAIL — no `sync-full` command; `sync_daily` import path differs.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/src/pictrip_data/cli.py
import typer

from pictrip_data.master.load_codes import load_codes
from pictrip_data.sync.daily import sync_daily, sync_full

app = typer.Typer(help="pictrip-data — KTO ETL CLI")


@app.command("sync-daily")
def sync_daily_cmd() -> None:
    """Daily incremental sync of spots from areaBasedSyncList2 (cron 04:00 KST)."""
    sync_daily()


@app.command("sync-full")
def sync_full_cmd() -> None:
    """Full reconcile — no modifiedtime filter (weekly; quota-aware)."""
    sync_full()


@app.command("load-codes")
def load_codes_cmd() -> None:
    """One-shot load of region/classification master codes."""
    load_codes()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline && uv run pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/pictrip_data/cli.py pipeline/tests/test_cli.py
git commit -m "feat(pipeline): wire sync-daily/sync-full/load-codes CLI"
```

> **`load-codes` note:** reference tables (regions 17 / sigungus 268 / lcls_systm_codes 245) are already populated on CT110, and Task 4's FK null-out tolerates gaps, so implementing `load_codes()` against `ldongCode2`/`lclsSystmCode2` is **not on the critical path**. Leave the stub callable; fill it in a follow-up if KTO adds codes. Tracked as Appendix A.

---

## Task 8: Streamlit dashboard (read-only)

**Files:**
- Modify: `pipeline/src/pictrip_data/dashboard/app.py`
- Test: `pipeline/tests/test_dashboard.py` (logic only)

**Interfaces:**
- Consumes: `psycopg` + `settings`.
- Produces: `recent_runs(conn, limit: int = 50) -> list[dict]` (pure query helper, unit-tested); the Streamlit page renders it.

- [ ] **Step 1: Write the failing test**

```python
# pipeline/tests/test_dashboard.py
from pictrip_data.dashboard.app import recent_runs
from pictrip_data.sync.audit import ensure_table, record_run


def test_recent_runs_returns_rows(db_conn):
    ensure_table(db_conn)
    with record_run(db_conn, "daily") as c:
        c["fetched"] = 3
    rows = recent_runs(db_conn, limit=10)
    assert rows and rows[0]["status"] == "success"
    assert rows[0]["fetched"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_dashboard.py -v`
Expected: FAIL — `recent_runs` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/src/pictrip_data/dashboard/app.py
import psycopg

from pictrip_data.config import settings

_COLS = ["id", "status", "mode", "started_at", "finished_at", "api_calls",
         "fetched", "inserted", "updated", "soft_deleted", "skipped", "duration_sec", "error"]


def recent_runs(conn: psycopg.Connection, limit: int = 50) -> list[dict]:
    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(_COLS)} FROM sync_runs ORDER BY id DESC LIMIT %s", (limit,))
    return [dict(zip(_COLS, row)) for row in cur.fetchall()]


def main() -> None:  # pragma: no cover - Streamlit entrypoint
    import streamlit as st

    st.title("pictrip-data — pipeline dashboard")
    st.caption("KTO collection runs (sync_runs). Internal / tailnet only.")
    with psycopg.connect(settings.database_url) as conn:
        rows = recent_runs(conn)
    st.dataframe(rows)
    errors = [r for r in rows if r["status"] == "error"]
    if errors:
        st.subheader("Recent errors")
        for r in errors:
            st.error(f"run {r['id']}: {r['error']}")


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline && POSTGRES_DB=pictrip_test uv run pytest tests/test_dashboard.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the full gate**

Run: `cd pipeline && uv run ruff check . && uv run ruff format --check . && POSTGRES_DB=pictrip_test uv run pytest`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add pipeline/src/pictrip_data/dashboard/app.py pipeline/tests/test_dashboard.py
git commit -m "feat(pipeline): read-only sync_runs dashboard"
```

---

## Post-implementation: live smoke (manual, on CT112)

Not a unit test — verify against the real API + DB once, after merge:

1. On CT112: `docker compose run --rm pipeline uv run pictrip-data sync-daily` (or the cron container).
2. Check `sync_runs`: `SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1;` → `status='success'`, sane counters.
3. Spot-check a known recently-modified `content_id` reflects the new `modified_time`.
4. Confirm a `showflag=0` item (e.g. an ended festival) landed with `show_flag=0` and dropped out of the app's nearby query.
5. Watch dev-quota usage — daily delta should be a handful of calls, not hundreds.

---

## Appendix A: `load-codes` (deferred, optional)

Fill `master/load_codes.py` to refresh reference tables from `ldongCode2` (regions/sigungus) and `lclsSystmCode2` (classification), idempotent upsert keyed on the code columns. Not required for `sync-daily` because tables are pre-populated and FK null-out tolerates gaps. Implement only if KTO introduces new codes that start appearing as NULLs in `spots`.

---

## Self-Review

- **Spec coverage:** config/db (T1), KTO mapping incl. composite signgu + KST time (T2), paged client omitting showflag + modifiedtime filter (T3), upsert with newer-wins + soft-delete + FK null-out (T4), audit lifecycle + watermark (T5), daily/full orchestration (T6), CLI incl. sync-full (T7), dashboard (T8). Soft-delete reconciliation = `sync-full` (T6/T7). Quota-awareness documented in Global Constraints + smoke. ✅
- **Type consistency:** `KtoSpot` fields identical across T2/T4/T6; `upsert_spots(conn, spots, refs, counters)`, `load_ref_codes(conn)->RefCodes`, `record_run(conn, mode)`, `last_success_watermark(conn)`, `area_based_sync_list(*, page, rows, modifiedtime)->(items,total)`, `watermark_param(wm)->str|None` all consistent. ✅
- **Placeholders:** none — every code step is complete. Two honest deferrals (`load-codes` Appendix A; `seed_refs` schema caveat) are flagged, not hidden. ✅
