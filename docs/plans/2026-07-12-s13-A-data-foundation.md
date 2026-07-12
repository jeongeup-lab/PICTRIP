# S13 Plan A — 데이터 기반 (overseas_spots · Wikidata ETL · 매칭 · 피드/탐색 API · 어드민)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 해외 스팟 명부(`overseas_spots`)를 구축하고, 해외→국내 실시간 매칭·피드·탐색
API와 어드민 숨김 관리를 라이브에 올린다. 전부 additive — 기존 화면·API 불변.

**Architecture:** 백엔드 신규 `feed` 모듈(모델·서빙·매칭·임베딩 잡) + 파이프라인
`sync-overseas` 서브커맨드(SPARQL→Commons→upsert). 스키마는 백엔드 Alembic 소유,
파이프라인은 행 적재만. CLIP은 백엔드 소유이므로 임베딩 배치도 백엔드 스크립트.

**Tech Stack:** SQLAlchemy 2.0 async + pgvector halfvec + Redis(캐시) /
psycopg3 + httpx + tenacity + typer(pipeline).

**Global Constraints:** `2026-07-12-s13-00-overview.md`의 Global Constraints +
공유 계약(스키마·페이로드·Redis 키) 절을 그대로 따른다. 브랜치 `feat/s13-a-data-foundation`.

**공통 검증 명령:**
```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run lint-imports && POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest
cd pipeline && uv run ruff check . && TEST_DATABASE_URL=postgresql://pictrip:pictrip_dev_only@localhost:5432/pictrip_test uv run pytest
```

---

### Task A0: 사전 검증 — Wikidata SPARQL · Commons 메타데이터 · 핫링크 정책 (스펙 §10.2·§10.5)

**Files:**
- Create: `docs/plans/s13-a0-probe-results.md` (조사 결과 기록 — 커밋 대상)

코드를 만들지 않는 조사 태스크. 이후 태스크의 쿼리·URL 포맷이 여기서 확정된다.

- [ ] **Step 1: SPARQL 프로브 — 일본 1개국으로 커버리지·성능 확인**

```bash
cat > /tmp/probe.sparql <<'EOF'
SELECT DISTINCT ?item ?ko ?desc ?img ?links WHERE {
  ?item wdt:P17 wd:Q17 ; wdt:P18 ?img ; wikibase:sitelinks ?links ; rdfs:label ?ko .
  FILTER(LANG(?ko) = "ko") FILTER(?links >= 10)
  { ?item wdt:P31/wdt:P279* wd:Q570116 . }
  UNION { ?item wdt:P31/wdt:P279* wd:Q33506 . }
  UNION { ?item wdt:P31/wdt:P279* wd:Q16560 . }
  OPTIONAL { ?item schema:description ?desc . FILTER(LANG(?desc) = "ko") }
} LIMIT 500
EOF
curl -sG "https://query.wikidata.org/sparql" \
  --data-urlencode "query@/tmp/probe.sparql" --data-urlencode "format=json" \
  -H "User-Agent: PicTripDataBot/1.0 (https://pictrip.org; dev@pictrip.org)" \
  | python3 -c "import json,sys; b=json.load(sys.stdin)['results']['bindings']; \
print('rows:', len(b)); print('desc coverage:', sum(1 for r in b if 'desc' in r)/max(len(b),1))"
```
확인: (a) 타임아웃 없이 응답하는가 (60s 제한). 타임아웃 시 UNION을 클래스별 개별 쿼리로
분할하는 것으로 A2의 쿼리 전략을 바꾼다. (b) `desc` 커버리지 — 0.5 미만이면 스펙 §10.2의
위키백과 요약 보강을 백로그로 기록(이번 범위 아님, `description_ko` nullable로 흡수).

- [ ] **Step 2: Commons extmetadata 배치 API 확인**

```bash
curl -s "https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=extmetadata&titles=File:Tokyo%20Tower%202023.jpg" \
  -H "User-Agent: PicTripDataBot/1.0 (https://pictrip.org; dev@pictrip.org)" | python3 -m json.tool | head -60
```
확인: `extmetadata.Artist.value`(HTML 포함), `LicenseShortName.value`, `LicenseUrl.value`
경로가 존재하는지. 50개 title 배치(`titles=A|B|...`)가 동작하는지 임의 3개 파일로 재확인.

- [ ] **Step 3: 핫링크(Special:FilePath 리다이렉트) 정책 확인**

```bash
curl -sI "https://commons.wikimedia.org/wiki/Special:FilePath/Tokyo%20Tower%202023.jpg?width=800" | head -5
```
확인: 302 → `upload.wikimedia.org/...thumb...800px...`. 최종 URL을 앱이 직접 로드
가능한지(200, image/*) 재확인. Wikimedia는 핫링크 허용이나 UA 차단 사례가 있으므로
RN 기본 UA로도 200이 오는지 `curl -A "okhttp/4.9" -sI <최종URL>`로 본다.

- [ ] **Step 4: 결과 기록 + 커밋**

`docs/plans/s13-a0-probe-results.md`에 세 프로브의 실제 응답 요약(행 수·커버리지·필드
경로·최종 이미지 URL 형태)과 "A2 쿼리 전략: UNION 유지/분할" 결정을 기록.

```bash
git add docs/plans/s13-a0-probe-results.md && git commit -m "docs(s13): Wikidata·Commons 프로브 결과"
```

---

### Task A1: `overseas_spots` 마이그레이션 + feed 모듈 골격

**Files:**
- Create: `backend/app/modules/feed/__init__.py`, `backend/app/modules/feed/models.py`
- Create: `backend/alembic/versions/20260712_0018_overseas_spots.py`
- Modify: `backend/alembic/env.py` (models import 추가)

**Interfaces:**
- Produces: ORM `OverseasSpot` (테이블 계약은 개요 문서 §공유 계약 그대로),
  이후 모든 백엔드 태스크가 이 모델/테이블을 사용.

- [ ] **Step 1: ORM 모델 작성**

`app/modules/feed/models.py` — `images/models.py`의 HALFVEC 패턴을 따른다:

```python
from datetime import datetime

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import BigInteger, Boolean, Float, Identity, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.embedding import EMBEDDING_DIM


class OverseasSpot(Base):
    __tablename__ = "overseas_spots"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    wikidata_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name_ko: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    country_name_ko: Mapped[str] = mapped_column(String(80), nullable=False)
    description_ko: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_author: Mapped[str | None] = mapped_column(Text)
    image_license: Mapped[str | None] = mapped_column(String(80))
    image_license_url: Mapped[str | None] = mapped_column(Text)
    image_source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fame_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    category: Mapped[str | None] = mapped_column(String(40))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    embedding: Mapped[list[float] | None] = mapped_column(HALFVEC(EMBEDDING_DIM))
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "idx_overseas_spots_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 128},
        ),
        Index("idx_overseas_spots_visible", "is_hidden", "fame_score"),
    )
```

`app/modules/feed/__init__.py`는 일단 빈 파일 (router export는 A4에서).
`Base`/타입 매핑 스타일(`Mapped`, `mapped_column`, timestamptz 처리)은 반드시
`spots/models.py`의 기존 컬럼 선언을 열어 그대로 맞춘다 — 특히 `created_at`/`updated_at`이
기존 모델에서 `DateTime(timezone=True)`를 명시한다면 동일하게.

- [ ] **Step 2: env.py에 모델 import 추가**

`backend/alembic/env.py`의 기존 모듈 models import 블록(23-29행 부근)에 추가:

```python
import app.modules.feed.models  # noqa: F401
```
(기존 블록의 import 스타일과 동일하게 — `from app.modules import ...` 형이면 그에 맞춘다.)

- [ ] **Step 3: 마이그레이션 autogenerate + SQL 리뷰 + 수동 보정**

```bash
cd backend && POSTGRES_DB=pictrip_test uv run alembic upgrade head
POSTGRES_DB=pictrip_test uv run alembic revision --autogenerate -m "overseas_spots"
```
생성 파일을 `20260712_0018_overseas_spots.py`로 정리: `revision = "0018_overseas_spots"`,
`down_revision = "0017_embedding_failures"`. **autogenerate는 halfvec 컬럼·hnsw 인덱스를
제대로 못 만든다** — 마이그레이션 0005·0009 패턴대로 수동 보정:

```python
def upgrade() -> None:
    op.create_table(
        "overseas_spots",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("wikidata_id", sa.String(32), nullable=False),
        sa.Column("name_ko", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("country_name_ko", sa.String(80), nullable=False),
        sa.Column("description_ko", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_author", sa.Text(), nullable=True),
        sa.Column("image_license", sa.String(80), nullable=True),
        sa.Column("image_license_url", sa.Text(), nullable=True),
        sa.Column("image_source_url", sa.Text(), nullable=False),
        sa.Column("fame_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("category", sa.String(40), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wikidata_id", name="uq_overseas_spots_wikidata_id"),
    )
    op.execute("ALTER TABLE overseas_spots ADD COLUMN embedding halfvec(512)")
    op.execute(
        "CREATE INDEX idx_overseas_spots_hnsw ON overseas_spots "
        "USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 128)"
    )
    op.execute("CREATE INDEX idx_overseas_spots_visible ON overseas_spots (is_hidden, fame_score DESC)")


def downgrade() -> None:
    op.drop_table("overseas_spots")
```

- [ ] **Step 4: 적용·검증**

```bash
POSTGRES_DB=pictrip_test uv run alembic upgrade head
POSTGRES_DB=pictrip_test uv run alembic downgrade -1 && POSTGRES_DB=pictrip_test uv run alembic upgrade head
```
Expected: 오류 없이 왕복. `psql`로 `\d overseas_spots` 확인 시 hnsw 인덱스 존재.

- [ ] **Step 5: 게이트 + 커밋**

```bash
uv run ruff check . && uv run mypy app && POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest
git add app/modules/feed alembic && git commit -m "feat(backend): overseas_spots 테이블 + feed 모듈 골격 (0018)"
```

---

### Task A2: 파이프라인 — Wikidata SPARQL 클라이언트 + 파싱

**Files:**
- Create: `pipeline/src/pictrip_data/overseas/__init__.py`, `overseas/countries.py`,
  `overseas/wikidata.py`
- Test: `pipeline/tests/test_overseas_wikidata.py`, `pipeline/tests/fixtures/sparql_bindings.json`

**Interfaces:**
- Produces: `WikidataClient.fetch_country(country: Country) -> list[RawSpot]`,
  `RawSpot` dataclass `{wikidata_id, name_ko, name_en, description_ko, image_filename,
  fame_score, lat, lng, country: Country}`, `Country = (qid, code, name_ko)` NamedTuple,
  `COUNTRIES: list[Country]` (~30개국). A3이 소비.

- [ ] **Step 1: 실패 테스트 작성**

`tests/fixtures/sparql_bindings.json` — A0 프로브의 실제 응답에서 바인딩 2개를 추려 저장
(하나는 desc·coord 있음, 하나는 OPTIONAL 필드 없음). 테스트:

```python
import json
from pathlib import Path

from pictrip_data.overseas.countries import COUNTRIES, Country
from pictrip_data.overseas.wikidata import RawSpot, parse_bindings

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sparql_bindings.json").read_text())
JP = Country(qid="Q17", code="JP", name_ko="일본")


def test_parse_bindings_full_row():
    spots = parse_bindings(FIXTURE, JP)
    s = spots[0]
    assert s.wikidata_id.startswith("Q")
    assert s.name_ko and s.image_filename and s.fame_score > 0
    assert s.country.code == "JP"


def test_parse_bindings_optional_fields_absent():
    spots = parse_bindings(FIXTURE, JP)
    assert any(s.description_ko is None for s in spots)


def test_parse_bindings_dedupes_by_qid():
    doubled = FIXTURE + FIXTURE
    assert len(parse_bindings(doubled, JP)) == len(parse_bindings(FIXTURE, JP))


def test_countries_shape():
    assert len(COUNTRIES) >= 25
    assert all(len(c.code) == 2 for c in COUNTRIES)
```

- [ ] **Step 2: 실패 확인**

```bash
cd pipeline && uv run pytest tests/test_overseas_wikidata.py -v
```
Expected: FAIL — `ModuleNotFoundError: pictrip_data.overseas`.

- [ ] **Step 3: 구현**

`overseas/countries.py`:

```python
from typing import NamedTuple


class Country(NamedTuple):
    qid: str
    code: str
    name_ko: str


COUNTRIES = [
    Country("Q17", "JP", "일본"), Country("Q148", "CN", "중국"), Country("Q865", "TW", "대만"),
    Country("Q869", "TH", "태국"), Country("Q881", "VN", "베트남"), Country("Q928", "PH", "필리핀"),
    Country("Q252", "ID", "인도네시아"), Country("Q833", "MY", "말레이시아"), Country("Q334", "SG", "싱가포르"),
    Country("Q668", "IN", "인도"), Country("Q30", "US", "미국"), Country("Q16", "CA", "캐나다"),
    Country("Q96", "MX", "멕시코"), Country("Q155", "BR", "브라질"), Country("Q414", "AR", "아르헨티나"),
    Country("Q142", "FR", "프랑스"), Country("Q38", "IT", "이탈리아"), Country("Q29", "ES", "스페인"),
    Country("Q145", "GB", "영국"), Country("Q183", "DE", "독일"), Country("Q39", "CH", "스위스"),
    Country("Q40", "AT", "오스트리아"), Country("Q55", "NL", "네덜란드"), Country("Q31", "BE", "벨기에"),
    Country("Q41", "GR", "그리스"), Country("Q45", "PT", "포르투갈"), Country("Q34", "SE", "스웨덴"),
    Country("Q20", "NO", "노르웨이"), Country("Q189", "IS", "아이슬란드"), Country("Q213", "CZ", "체코"),
    Country("Q43", "TR", "튀르키예"), Country("Q79", "EG", "이집트"), Country("Q408", "AU", "호주"),
    Country("Q664", "NZ", "뉴질랜드"), Country("Q878", "AE", "아랍에미리트"),
]
```

`overseas/wikidata.py` — `kto/client.py`의 tenacity 패턴을 미러:

```python
from dataclasses import dataclass
from urllib.parse import unquote

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pictrip_data.overseas.countries import Country

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "PicTripDataBot/1.0 (https://pictrip.org; dev@pictrip.org)"
MIN_SITELINKS = 10
_CLASS_QIDS = ["Q570116", "Q33506", "Q16560", "Q23413", "Q4989906", "Q839954", "Q8502"]

_QUERY_TMPL = """SELECT DISTINCT ?item ?ko ?en ?desc ?img ?links ?lat ?lng WHERE {{
  ?item wdt:P17 wd:{country} ; wdt:P18 ?img ; wikibase:sitelinks ?links ; rdfs:label ?ko .
  FILTER(LANG(?ko) = "ko") FILTER(?links >= {min_links})
  {class_union}
  OPTIONAL {{ ?item schema:description ?desc . FILTER(LANG(?desc) = "ko") }}
  OPTIONAL {{ ?item rdfs:label ?en . FILTER(LANG(?en) = "en") }}
  OPTIONAL {{ ?item p:P625/psv:P625 [ wikibase:geoLatitude ?lat ; wikibase:geoLongitude ?lng ] . }}
}}"""


@dataclass(frozen=True)
class RawSpot:
    wikidata_id: str
    name_ko: str
    name_en: str | None
    description_ko: str | None
    image_filename: str
    fame_score: int
    lat: float | None
    lng: float | None
    country: Country


def build_query(country: Country) -> str:
    union = "\n  UNION ".join(f"{{ ?item wdt:P31/wdt:P279* wd:{q} . }}" for q in _CLASS_QIDS)
    return _QUERY_TMPL.format(country=country.qid, min_links=MIN_SITELINKS, class_union=union)


def _filename_from_image_url(url: str) -> str:
    return unquote(url.rsplit("/", 1)[-1])


def parse_bindings(bindings: list[dict], country: Country) -> list[RawSpot]:
    seen: dict[str, RawSpot] = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        if qid in seen:
            continue
        seen[qid] = RawSpot(
            wikidata_id=qid,
            name_ko=b["ko"]["value"],
            name_en=b.get("en", {}).get("value"),
            description_ko=b.get("desc", {}).get("value"),
            image_filename=_filename_from_image_url(b["img"]["value"]),
            fame_score=int(b["links"]["value"]),
            lat=float(b["lat"]["value"]) if "lat" in b else None,
            lng=float(b["lng"]["value"]) if "lng" in b else None,
            country=country,
        )
    return list(seen.values())


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and (
        exc.response.status_code == 429 or exc.response.status_code >= 500
    )


class WikidataClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(90.0, connect=5.0), headers={"User-Agent": USER_AGENT}
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30),
           retry=retry_if_exception(_is_transient), reraise=True)
    def fetch_country(self, country: Country) -> list[RawSpot]:
        resp = self._client.post(
            SPARQL_ENDPOINT, data={"query": build_query(country), "format": "json"}
        )
        resp.raise_for_status()
        return parse_bindings(resp.json()["results"]["bindings"], country)
```
A0에서 UNION 분할 결정이 났다면 `fetch_country`를 클래스별 쿼리 루프+병합으로 바꾼다
(인터페이스는 동일).

- [ ] **Step 4: 통과 확인 + 커밋**

```bash
uv run pytest tests/test_overseas_wikidata.py -v && uv run ruff check .
git add src/pictrip_data/overseas tests && git commit -m "feat(pipeline): Wikidata SPARQL 클라이언트 + 국가 명부"
```

---

### Task A3: 파이프라인 — Commons 출처 조회 + upsert + `sync-overseas` CLI

**Files:**
- Create: `pipeline/src/pictrip_data/overseas/commons.py`, `overseas/upsert.py`, `overseas/sync.py`
- Modify: `pipeline/src/pictrip_data/cli.py`, `pipeline/tests/conftest.py` (스키마 미러 추가)
- Test: `pipeline/tests/test_overseas_sync.py`, `tests/test_overseas_commons.py`

**Interfaces:**
- Consumes: `WikidataClient.fetch_country`, `RawSpot`, `COUNTRIES` (A2),
  `record_run(conn, mode)` (기존 audit), `connect()` (기존 db).
- Produces: CLI `pictrip-data sync-overseas [--limit] [--country CC] [--dry-run]`,
  `CommonsClient.fetch_credits(filenames) -> dict[str, Credit]`,
  `Credit{author, license, license_url}`, `upsert_overseas(cur, spot, credit) -> bool`.

- [ ] **Step 1: conftest에 overseas_spots 미러 DDL 추가**

`tests/conftest.py`의 `_SCHEMA`에 추가 (백엔드 0018과 동일 컬럼, embedding은 테스트에
불필요하므로 제외 가능하지만 upsert의 embedding-reset CASE가 참조하므로 포함 —
pictrip_test에는 pgvector 확장이 이미 있다):

```python
CREATE TABLE IF NOT EXISTS overseas_spots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wikidata_id VARCHAR(32) UNIQUE NOT NULL,
    name_ko VARCHAR(255) NOT NULL, name_en VARCHAR(255),
    country_code VARCHAR(2) NOT NULL, country_name_ko VARCHAR(80) NOT NULL,
    description_ko TEXT, image_url TEXT NOT NULL,
    image_author TEXT, image_license VARCHAR(80), image_license_url TEXT,
    image_source_url TEXT NOT NULL,
    fame_score INTEGER NOT NULL DEFAULT 0, category VARCHAR(40),
    lat DOUBLE PRECISION, lng DOUBLE PRECISION,
    embedding halfvec(512),
    is_hidden BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
클린업 훅에 `DELETE FROM overseas_spots WHERE wikidata_id LIKE 'QTEST%'` 추가.

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_overseas_commons.py`:

```python
from pictrip_data.overseas.commons import parse_credits

PAGES = {"pages": {"1": {"title": "File:A.jpg", "imageinfo": [{"extmetadata": {
    "Artist": {"value": "<a href='x'>Jane Doe</a>"},
    "LicenseShortName": {"value": "CC BY-SA 4.0"},
    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
}}]}, "2": {"title": "File:B.jpg"}}}


def test_parse_credits_strips_html_and_maps_by_filename():
    credits = parse_credits({"query": PAGES})
    assert credits["A.jpg"].author == "Jane Doe"
    assert credits["A.jpg"].license == "CC BY-SA 4.0"
    assert credits["A.jpg"].license_url.startswith("https://creativecommons")


def test_parse_credits_missing_imageinfo_skipped():
    credits = parse_credits({"query": PAGES})
    assert "B.jpg" not in credits
```

`tests/test_overseas_sync.py` — 기존 `test_sync_daily.py` 패턴(가짜 클라이언트 + 실 DB):

```python
from pictrip_data.overseas.commons import Credit
from pictrip_data.overseas.countries import Country
from pictrip_data.overseas.sync import sync_overseas
from pictrip_data.overseas.wikidata import RawSpot

JP = Country("Q17", "JP", "일본")
SPOT = RawSpot("QTEST1", "도쿄타워", "Tokyo Tower", "도쿄의 전파탑", "Tokyo Tower.jpg",
               120, 35.66, 139.75, JP)
CREDIT = Credit(author="Jane", license="CC BY-SA 4.0",
                license_url="https://creativecommons.org/licenses/by-sa/4.0")


class FakeWikidata:
    def fetch_country(self, country):
        return [SPOT] if country.code == "JP" else []


class FakeCommons:
    def fetch_credits(self, filenames):
        return {"Tokyo Tower.jpg": CREDIT}


def test_sync_overseas_inserts_and_records_run(db_conn):
    sync_overseas(wikidata=FakeWikidata(), commons=FakeCommons(), conn=db_conn,
                  countries=[JP])
    with db_conn.cursor() as cur:
        cur.execute("SELECT name_ko, image_url, image_source_url, fame_score "
                    "FROM overseas_spots WHERE wikidata_id = 'QTEST1'")
        row = cur.fetchone()
    assert row[0] == "도쿄타워"
    assert row[1].startswith("https://commons.wikimedia.org/wiki/Special:FilePath/")
    assert "width=800" in row[1]
    assert row[2].startswith("https://commons.wikimedia.org/wiki/File:")
    with db_conn.cursor() as cur:
        cur.execute("SELECT status, mode FROM sync_runs ORDER BY id DESC LIMIT 1")
        assert cur.fetchone() == ("success", "overseas")


def test_sync_overseas_upsert_preserves_hidden_and_resets_embedding_on_image_change(db_conn):
    sync_overseas(wikidata=FakeWikidata(), commons=FakeCommons(), conn=db_conn, countries=[JP])
    with db_conn.cursor() as cur:
        cur.execute("UPDATE overseas_spots SET is_hidden = true, "
                    "embedding = array_fill(0.1::real, ARRAY[512])::halfvec "
                    "WHERE wikidata_id = 'QTEST1'")
    db_conn.commit()
    changed = RawSpot("QTEST1", "도쿄타워", None, None, "New Tower.jpg", 130, None, None, JP)

    class Changed(FakeWikidata):
        def fetch_country(self, country):
            return [changed]

    class ChangedCommons(FakeCommons):
        def fetch_credits(self, filenames):
            return {"New Tower.jpg": CREDIT}

    sync_overseas(wikidata=Changed(), commons=ChangedCommons(), conn=db_conn, countries=[JP])
    with db_conn.cursor() as cur:
        cur.execute("SELECT is_hidden, embedding IS NULL FROM overseas_spots "
                    "WHERE wikidata_id = 'QTEST1'")
        assert cur.fetchone() == (True, True)
```

- [ ] **Step 3: 실패 확인**

```bash
uv run pytest tests/test_overseas_commons.py tests/test_overseas_sync.py -v
```
Expected: FAIL (모듈 없음).

- [ ] **Step 4: 구현**

`overseas/commons.py`:

```python
import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pictrip_data.overseas.wikidata import USER_AGENT, _is_transient

API = "https://commons.wikimedia.org/w/api.php"
_TAG = re.compile(r"<[^>]+>")
_BATCH = 50


@dataclass(frozen=True)
class Credit:
    author: str | None
    license: str | None
    license_url: str | None


def thumb_url(filename: str) -> str:
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width=800"


def source_url(filename: str) -> str:
    return f"https://commons.wikimedia.org/wiki/File:{quote(filename)}"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = _TAG.sub("", value).strip()
    return text or None


def parse_credits(payload: dict) -> dict[str, Credit]:
    credits: dict[str, Credit] = {}
    for page in payload.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo")
        if not info:
            continue
        meta = info[0].get("extmetadata", {})
        name = page["title"].removeprefix("File:")
        credits[name] = Credit(
            author=_clean(meta.get("Artist", {}).get("value")),
            license=_clean(meta.get("LicenseShortName", {}).get("value")),
            license_url=_clean(meta.get("LicenseUrl", {}).get("value")),
        )
    return credits


class CommonsClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0), headers={"User-Agent": USER_AGENT}
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8),
           retry=retry_if_exception(_is_transient), reraise=True)
    def _call(self, titles: list[str]) -> dict:
        resp = self._client.get(API, params={
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "extmetadata", "titles": "|".join(titles),
        })
        resp.raise_for_status()
        return resp.json()

    def fetch_credits(self, filenames: list[str]) -> dict[str, Credit]:
        credits: dict[str, Credit] = {}
        for i in range(0, len(filenames), _BATCH):
            batch = [f"File:{n}" for n in filenames[i : i + _BATCH]]
            credits.update(parse_credits(self._call(batch)))
        return credits
```

`overseas/upsert.py` — 기존 `sync/upsert.py`의 ON CONFLICT 패턴:

```python
from pictrip_data.overseas.commons import Credit, source_url, thumb_url
from pictrip_data.overseas.wikidata import RawSpot

_SQL = """
INSERT INTO overseas_spots (
    wikidata_id, name_ko, name_en, country_code, country_name_ko, description_ko,
    image_url, image_author, image_license, image_license_url, image_source_url,
    fame_score, lat, lng, updated_at
) VALUES (
    %(wikidata_id)s, %(name_ko)s, %(name_en)s, %(country_code)s, %(country_name_ko)s,
    %(description_ko)s, %(image_url)s, %(image_author)s, %(image_license)s,
    %(image_license_url)s, %(image_source_url)s, %(fame_score)s, %(lat)s, %(lng)s, now()
)
ON CONFLICT (wikidata_id) DO UPDATE SET
    name_ko = EXCLUDED.name_ko, name_en = EXCLUDED.name_en,
    country_code = EXCLUDED.country_code, country_name_ko = EXCLUDED.country_name_ko,
    description_ko = EXCLUDED.description_ko,
    embedding = CASE WHEN overseas_spots.image_url IS DISTINCT FROM EXCLUDED.image_url
                     THEN NULL ELSE overseas_spots.embedding END,
    image_url = EXCLUDED.image_url, image_author = EXCLUDED.image_author,
    image_license = EXCLUDED.image_license, image_license_url = EXCLUDED.image_license_url,
    image_source_url = EXCLUDED.image_source_url,
    fame_score = EXCLUDED.fame_score, lat = EXCLUDED.lat, lng = EXCLUDED.lng,
    updated_at = now()
RETURNING (xmax = 0) AS inserted
"""


def upsert_overseas(cur, spot: RawSpot, credit: Credit | None) -> bool:
    cur.execute(_SQL, {
        "wikidata_id": spot.wikidata_id, "name_ko": spot.name_ko, "name_en": spot.name_en,
        "country_code": spot.country.code, "country_name_ko": spot.country.name_ko,
        "description_ko": spot.description_ko,
        "image_url": thumb_url(spot.image_filename),
        "image_author": credit.author if credit else None,
        "image_license": credit.license if credit else None,
        "image_license_url": credit.license_url if credit else None,
        "image_source_url": source_url(spot.image_filename),
        "fame_score": spot.fame_score, "lat": spot.lat, "lng": spot.lng,
    })
    return bool(cur.fetchone()[0])
```
주의: `is_hidden`은 INSERT 컬럼에도 UPDATE SET에도 넣지 않는다 (어드민 결정 보존).

`overseas/sync.py` — `daily.py:67`의 소유권 패턴(주입 없으면 자체 생성):

```python
from pictrip_data.db import connect
from pictrip_data.overseas.commons import CommonsClient
from pictrip_data.overseas.countries import COUNTRIES, Country
from pictrip_data.overseas.upsert import upsert_overseas
from pictrip_data.overseas.wikidata import WikidataClient
from pictrip_data.sync.audit import ensure_table, record_run


def sync_overseas(*, wikidata=None, commons=None, conn=None,
                  countries: list[Country] | None = None,
                  limit: int | None = None, dry_run: bool = False) -> None:
    wikidata = wikidata or WikidataClient()
    commons = commons or CommonsClient()
    countries = countries if countries is not None else COUNTRIES
    if conn is not None:
        _run(wikidata, commons, conn, countries, limit, dry_run)
        return
    with connect() as owned:
        _run(wikidata, commons, owned, countries, limit, dry_run)


def _run(wikidata, commons, conn, countries, limit, dry_run) -> None:
    ensure_table(conn)
    with record_run(conn, mode="overseas") as counters:
        total = 0
        for country in countries:
            spots = wikidata.fetch_country(country)
            counters["api_calls"] += 1
            if limit is not None:
                spots = spots[: max(limit - total, 0)]
            if not spots:
                continue
            credits = commons.fetch_credits([s.image_filename for s in spots])
            counters["api_calls"] += (len(spots) + 49) // 50
            with conn.cursor() as cur:
                for spot in spots:
                    inserted = upsert_overseas(cur, spot, credits.get(spot.image_filename))
                    counters["inserted" if inserted else "updated"] += 1
            counters["fetched"] += len(spots)
            total += len(spots)
            if dry_run:
                conn.rollback()
            else:
                conn.commit()
            if limit is not None and total >= limit:
                break
```
(`record_run`의 counter dict 키·commit 시맨틱은 `sync/audit.py`를 열어 정확히 맞춘다 —
dry-run 롤백이 audit 커밋과 충돌하지 않는지 기존 코드로 확인하고 필요하면 dry-run 시
`record_run` 없이 돌게 분기.)

`cli.py`에 등록:

```python
@app.command("sync-overseas")
def sync_overseas_cmd(
    limit: int | None = typer.Option(None),
    country: list[str] = typer.Option([], "--country"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    selected = [c for c in COUNTRIES if c.code in country] if country else None
    sync_overseas(countries=selected, limit=limit, dry_run=dry_run)
```

- [ ] **Step 5: 통과 확인 + 커밋**

```bash
uv run pytest -v && uv run ruff check .
git add src tests && git commit -m "feat(pipeline): sync-overseas — Wikidata→Commons→overseas_spots 적재"
```

---

### Task A4: 백엔드 — `/feed` · `/explore` (시드 셔플 커서 페이지네이션)

**Files:**
- Create: `backend/app/modules/feed/schemas.py`, `feed/repositories.py`,
  `feed/services/__init__.py`, `feed/services/posts.py`, `feed/routes.py`
- Modify: `backend/app/modules/feed/__init__.py` (router export),
  `backend/app/main.py` (라우터 등록), `backend/pyproject.toml` (import-linter 4개 계약에
  `app.modules.feed.routes/schemas/services/models` 추가)
- Test: `backend/tests/test_feed_posts.py`

**Interfaces:**
- Produces: `GET /v1/feed`, `GET /v1/explore` (페이로드는 개요 §공유 계약),
  `services.posts.list_posts(session, *, seed, cursor, limit) -> PostsPageRow`,
  `repositories.fetch_posts_page(session, *, seed, cursor_key, cursor_id, limit) -> list[OverseasPostRow]`.
  C(모바일)가 이 페이로드를 소비.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_feed_posts.py` — 기존 `test_home_feed.py`의 override 패턴
(`app.dependency_overrides[get_db]`, raw `text()` INSERT 시드):

```python
import pytest
from sqlalchemy import text

SEED_SQL = text("""
INSERT INTO overseas_spots (wikidata_id, name_ko, country_code, country_name_ko,
    description_ko, image_url, image_source_url, fame_score, is_hidden)
VALUES (:qid, :name, :cc, :cn, :desc, 'https://img/' || :qid, 'https://src/' || :qid,
    :fame, :hidden)
""")


@pytest.fixture
async def seeded(db_session):
    rows = [("QF1", "루브르", "FR", "프랑스", "파리의 미술관", 200, False),
            ("QF2", "에펠탑", "FR", "프랑스", None, 300, False),
            ("QJ1", "도쿄타워", "JP", "일본", "도쿄의 전파탑", 120, False),
            ("QH1", "숨김", "JP", "일본", None, 500, True)]
    for qid, name, cc, cn, desc, fame, hidden in rows:
        await db_session.execute(SEED_SQL, {"qid": qid, "name": name, "cc": cc, "cn": cn,
                                            "desc": desc, "fame": fame, "hidden": hidden})
    await db_session.commit()


async def test_feed_returns_seeded_page(client, seeded):
    res = await client.get("/v1/feed", params={"limit": 2})
    body = res.json()
    assert res.status_code == 200 and body["error"] is None
    data = body["data"]
    assert data["seed"] and len(data["items"]) == 2 and data["hasMore"] is True
    assert {"id", "nameKo", "countryCode", "countryNameKo", "descriptionKo", "imageUrl",
            "imageAuthor", "imageLicense", "imageLicenseUrl", "imageSourceUrl"} <= set(data["items"][0])


async def test_feed_excludes_hidden(client, seeded):
    res = await client.get("/v1/feed", params={"limit": 10})
    names = [i["nameKo"] for i in res.json()["data"]["items"]]
    assert "숨김" not in names and len(names) == 3


async def test_feed_cursor_no_duplicates_same_seed(client, seeded):
    first = (await client.get("/v1/feed", params={"limit": 2})).json()["data"]
    second = (await client.get("/v1/feed", params={
        "limit": 2, "seed": first["seed"], "cursor": first["nextCursor"]})).json()["data"]
    ids1 = {i["id"] for i in first["items"]}
    ids2 = {i["id"] for i in second["items"]}
    assert not ids1 & ids2 and second["hasMore"] is False


async def test_feed_same_seed_stable_order(client, seeded):
    a = (await client.get("/v1/feed", params={"limit": 3, "seed": "s1"})).json()["data"]
    b = (await client.get("/v1/feed", params={"limit": 3, "seed": "s1"})).json()["data"]
    assert [i["id"] for i in a["items"]] == [i["id"] for i in b["items"]]


async def test_explore_same_pool(client, seeded):
    res = await client.get("/v1/explore", params={"limit": 30})
    assert len(res.json()["data"]["items"]) == 3
```

- [ ] **Step 2: 실패 확인**

```bash
POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests/test_feed_posts.py -v
```
Expected: 404 (라우트 없음)로 FAIL.

- [ ] **Step 3: 구현**

`feed/repositories.py` — 시드 결정적 가중 셔플 + keyset:

```python
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_KEY_EXPR = (
    "power(greatest("
    "((('x' || left(md5(:seed || wikidata_id), 8))::bit(32)::int)::bigint + 2147483648)"
    " / 4294967296.0, 1e-9), 1.0 / ln(fame_score + 2))"
)

_PAGE_SQL = f"""
WITH scored AS (
    SELECT id, name_ko, country_code, country_name_ko, description_ko,
           image_url, image_author, image_license, image_license_url, image_source_url,
           {_KEY_EXPR} AS shuffle_key
    FROM overseas_spots
    WHERE is_hidden = false
)
SELECT * FROM scored
WHERE (:cursor_key IS NULL)
   OR (shuffle_key, id) < (:cursor_key, :cursor_id)
ORDER BY shuffle_key DESC, id DESC
LIMIT :lim
"""


@dataclass(frozen=True)
class OverseasPostRow:
    id: int
    name_ko: str
    country_code: str
    country_name_ko: str
    description_ko: str | None
    image_url: str
    image_author: str | None
    image_license: str | None
    image_license_url: str | None
    image_source_url: str
    shuffle_key: float


async def fetch_posts_page(session: AsyncSession, *, seed: str, cursor_key: float | None,
                           cursor_id: int | None, limit: int) -> list[OverseasPostRow]:
    result = await session.execute(text(_PAGE_SQL), {
        "seed": seed, "cursor_key": cursor_key, "cursor_id": cursor_id or 0, "lim": limit,
    })
    return [OverseasPostRow(**row._mapping) for row in result]
```
(`(:cursor_key IS NULL) OR (tuple) < (tuple)` 형이 asyncpg에서 타입 추론 오류를 내면
cursor 유무로 SQL 두 벌을 분기한다 — 동작이 우선.)

`feed/services/posts.py`:

```python
import base64
import secrets
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feed import repositories
from app.modules.feed.repositories import OverseasPostRow


@dataclass(frozen=True)
class PostsPageRow:
    seed: str
    items: list[OverseasPostRow]
    next_cursor: str | None
    has_more: bool


def _encode_cursor(row: OverseasPostRow) -> str:
    return base64.urlsafe_b64encode(f"{row.shuffle_key:.12f}:{row.id}".encode()).decode()


def _decode_cursor(cursor: str | None) -> tuple[float | None, int | None]:
    if not cursor:
        return None, None
    key, _, oid = base64.urlsafe_b64decode(cursor.encode()).decode().partition(":")
    return float(key), int(oid)


def _spread_countries(items: list[OverseasPostRow]) -> list[OverseasPostRow]:
    out = list(items)
    for i in range(1, len(out)):
        if out[i].country_code != out[i - 1].country_code:
            continue
        for j in range(i + 1, len(out)):
            if out[j].country_code != out[i - 1].country_code:
                out[i], out[j] = out[j], out[i]
                break
    return out


async def list_posts(session: AsyncSession, *, seed: str | None, cursor: str | None,
                     limit: int) -> PostsPageRow:
    seed = seed or secrets.token_hex(8)
    cursor_key, cursor_id = _decode_cursor(cursor)
    rows = await repositories.fetch_posts_page(
        session, seed=seed, cursor_key=cursor_key, cursor_id=cursor_id, limit=limit + 1
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1]) if page and has_more else None
    return PostsPageRow(seed=seed, items=_spread_countries(page),
                        next_cursor=next_cursor, has_more=has_more)
```
주의: `next_cursor`는 **다양성 셔플 이전** 마지막 행(`page[-1]`, keyset 순서 기준)으로
인코딩해야 한다 — `_spread_countries`가 페이지 내 순서만 바꾸므로 페이지의 keyset 마지막
행을 셔플 전에 잡아둔다 (구현 시 `tail = page[-1]`을 spread 호출 전에 확보).

`feed/schemas.py`:

```python
from pydantic import BaseModel

from app.modules.feed.repositories import OverseasPostRow


class OverseasPost(BaseModel):
    id: int
    nameKo: str
    countryCode: str
    countryNameKo: str
    descriptionKo: str | None
    imageUrl: str
    imageAuthor: str | None
    imageLicense: str | None
    imageLicenseUrl: str | None
    imageSourceUrl: str

    @classmethod
    def from_row(cls, row: OverseasPostRow) -> "OverseasPost":
        return cls(id=row.id, nameKo=row.name_ko, countryCode=row.country_code,
                   countryNameKo=row.country_name_ko, descriptionKo=row.description_ko,
                   imageUrl=row.image_url, imageAuthor=row.image_author,
                   imageLicense=row.image_license, imageLicenseUrl=row.image_license_url,
                   imageSourceUrl=row.image_source_url)


class PostsResponse(BaseModel):
    seed: str
    items: list[OverseasPost]
    nextCursor: str | None
    hasMore: bool
```
(schemas가 repositories의 dataclass를 import하는 게 "Schemas do not import SQLAlchemy"
계약에 걸리면 — repositories가 sqlalchemy를 import하므로 간접 위반 여부 확인 —
걸릴 경우 `from_row`를 services로 옮기고 schemas는 순수 필드만 갖게 한다.)

`feed/routes.py`:

```python
from typing import Any

from fastapi import APIRouter, Query

from app.core.db import DbSession
from app.core.schemas import ok
from app.modules.feed.schemas import OverseasPost, PostsResponse
from app.modules.feed.services import posts

router = APIRouter(tags=["feed"])


@router.get("/feed")
async def feed(session: DbSession, seed: str | None = Query(None),
               cursor: str | None = Query(None),
               limit: int = Query(6, ge=1, le=20)) -> dict[str, Any]:
    page = await posts.list_posts(session, seed=seed, cursor=cursor, limit=limit)
    return ok(_to_response(page))


@router.get("/explore")
async def explore(session: DbSession, seed: str | None = Query(None),
                  cursor: str | None = Query(None),
                  limit: int = Query(30, ge=1, le=60)) -> dict[str, Any]:
    page = await posts.list_posts(session, seed=seed, cursor=cursor, limit=limit)
    return ok(_to_response(page))


def _to_response(page: posts.PostsPageRow) -> PostsResponse:
    return PostsResponse(seed=page.seed, items=[OverseasPost.from_row(r) for r in page.items],
                         nextCursor=page.next_cursor, hasMore=page.has_more)
```

`feed/__init__.py`: `from app.modules.feed.routes import router` (+`__all__`).
`main.py` /v1 블록에 `app.include_router(feed_router, prefix=prefix)` 추가
(`from app.modules.feed import router as feed_router`).
`pyproject.toml` import-linter 4개 계약의 소스/금지 목록에 feed 경로 추가
(기존 taste·spots 나열과 동일 형식).

- [ ] **Step 4: 통과 확인 + 전체 게이트 + 커밋**

```bash
POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests/test_feed_posts.py -v
uv run ruff check . && uv run mypy app && uv run lint-imports
git add app pyproject.toml tests && git commit -m "feat(backend): /feed·/explore 시드 셔플 커서 페이지네이션"
```

---

### Task A5: 백엔드 — `/overseas/{id}/matches` 실시간 매칭 + Redis 캐시

**Files:**
- Create: `backend/app/modules/feed/text.py`, `feed/services/matching.py`
- Modify: `backend/app/modules/feed/routes.py`, `feed/repositories.py`, `feed/schemas.py`,
  `feed/services/__init__.py`, `backend/app/config.py` (`MATCH_DISTANCE_MAX`,
  `MATCH_CANDIDATES`), `backend/app/modules/spots/services/cards.py` +
  `services/__init__.py` (`load_overview_map` 신설·재수출)
- Test: `backend/tests/test_feed_matching.py`, `backend/tests/test_feed_text.py`

**Interfaces:**
- Consumes: `load_active_spot_cards_by_ids`, `load_region_meta` (spots services 기존),
  `RedisDep`(core), `spot_embeddings` hnsw 쿼리 패턴(`images/repositories.py:40` 형).
- Produces: `GET /v1/overseas/{id}/matches` → `{overseasId, matches:[MatchCard]}`;
  `spots.services.load_overview_map(session, content_ids) -> dict[str, str | None]`;
  `feed.text.first_sentence(text) -> str | None`.

- [ ] **Step 1: first_sentence 실패 테스트**

`tests/test_feed_text.py`:

```python
from app.modules.feed.text import first_sentence


def test_first_sentence_korean_period():
    assert first_sentence("산자락을 따라 늘어선 마을이다. 골목길이 이어진다.") == \
        "산자락을 따라 늘어선 마을이다."


def test_first_sentence_no_terminator_returns_whole():
    assert first_sentence("마침표 없는 소개문") == "마침표 없는 소개문"


def test_first_sentence_none_and_blank():
    assert first_sentence(None) is None
    assert first_sentence("   ") is None


def test_first_sentence_is_pure_truncation():
    src = "첫 문장이다. 둘째."
    out = first_sentence(src)
    assert out is not None and src.startswith(out)
```

- [ ] **Step 2: 구현 — `feed/text.py`**

```python
import re

_TERMINATOR = re.compile(r"[.!?](?=\s|$)")


def first_sentence(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    match = _TERMINATOR.search(stripped)
    return stripped[: match.end()] if match else stripped
```

```bash
POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests/test_feed_text.py -v
```
Expected: PASS. verbatim 원칙: 어떤 치환도 없이 원문 접두 절삭만 (`startswith` 테스트가 게이트).

- [ ] **Step 3: 매칭 실패 테스트**

`tests/test_feed_matching.py` — `test_taste_photo_search.py`의 시드 방식(스팟+임베딩
raw INSERT)과 FakeRedis override를 그대로 차용. 시나리오:

```python
async def test_matches_returns_similar_domestic(client, seeded_matching):
    res = await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    body = res.json()
    assert res.status_code == 200 and body["error"] is None
    matches = body["data"]["matches"]
    assert 1 <= len(matches) <= 3
    assert {"contentId", "title", "regionLabel", "imageUrl", "overviewFirst"} <= set(matches[0])


async def test_matches_threshold_filters_far_spots(client, seeded_matching_far):
    res = await client.get(f"/v1/overseas/{seeded_matching_far.overseas_id}/matches")
    assert res.json()["data"]["matches"] == []


async def test_matches_cached_in_redis(client, seeded_matching, redis_client_fake):
    await client.get(f"/v1/overseas/{seeded_matching.overseas_id}/matches")
    assert await redis_client_fake.get(f"match:{seeded_matching.overseas_id}") is not None


async def test_matches_unknown_id_404(client):
    res = await client.get("/v1/overseas/999999/matches")
    assert res.status_code == 404 and res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_matches_without_embedding_returns_empty(client, seeded_overseas_no_embedding):
    res = await client.get(f"/v1/overseas/{seeded_overseas_no_embedding}/matches")
    assert res.json()["data"]["matches"] == []
```
시드 픽스처: overseas_spots 1행(embedding = `[0.1]*512` 방향 벡터), spots+spot_embeddings
2행(가까운 벡터), spot_details에 overview 1행. far 픽스처는 직교 벡터. 벡터 리터럴은
`"[" + ",".join(...) + "]"` 문자열로 INSERT (`CAST(:emb AS halfvec(512))`).

- [ ] **Step 4: 구현**

`config.py`에 추가 (PHOTO_SEARCH 설정들 옆):

```python
MATCH_DISTANCE_MAX: float = 0.45
MATCH_CANDIDATES: int = 40
```

`feed/repositories.py`에 추가:

```python
_NEIGHBORS_SQL = """
SELECT se.content_id,
       (se.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid))::float AS distance
FROM spot_embeddings se
ORDER BY se.embedding <=> (SELECT embedding FROM overseas_spots WHERE id = :oid)
LIMIT :lim
"""


async def get_overseas_brief(session: AsyncSession, overseas_id: int) -> tuple[int, bool] | None:
    row = (await session.execute(text(
        "SELECT id, embedding IS NOT NULL AS has_embedding FROM overseas_spots "
        "WHERE id = :oid AND is_hidden = false"), {"oid": overseas_id})).first()
    return (row.id, row.has_embedding) if row else None


async def find_domestic_neighbors(session: AsyncSession, overseas_id: int,
                                  *, limit: int) -> list[tuple[str, float]]:
    result = await session.execute(text(_NEIGHBORS_SQL), {"oid": overseas_id, "lim": limit})
    return [(r.content_id, r.distance) for r in result]
```

`spots/services/cards.py`에 추가 + `services/__init__.py` 재수출:

```python
async def load_overview_map(session: AsyncSession, content_ids: Sequence[str]) -> dict[str, str | None]:
    if not content_ids:
        return {}
    result = await session.execute(
        select(SpotDetail.content_id, SpotDetail.overview)
        .where(SpotDetail.content_id.in_(content_ids))
    )
    return {row.content_id: row.overview for row in result}
```

`feed/services/matching.py`:

```python
import json
from dataclasses import asdict, dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ResourceNotFound
from app.modules.feed import repositories
from app.modules.feed.text import first_sentence
from app.modules.spots import services as spots_services

_TTL_SECONDS = 6 * 3600
_MATCH_COUNT = 3


@dataclass(frozen=True)
class MatchRow:
    content_id: str
    title: str
    region_label: str
    image_url: str
    overview_first: str | None


async def find_matches(session: AsyncSession, redis: Redis, overseas_id: int) -> list[MatchRow]:
    cached = await _cache_get(redis, overseas_id)
    if cached is not None:
        return cached
    brief = await repositories.get_overseas_brief(session, overseas_id)
    if brief is None:
        raise ResourceNotFound(f"overseas spot {overseas_id} not found")
    if not brief[1]:
        return []
    neighbors = await repositories.find_domestic_neighbors(
        session, overseas_id, limit=settings.MATCH_CANDIDATES)
    candidate_ids = [cid for cid, dist in neighbors if dist <= settings.MATCH_DISTANCE_MAX]
    rows = await _hydrate(session, candidate_ids)
    await _cache_set(redis, overseas_id, rows)
    return rows
```
`_hydrate`: `spots_services.load_active_spot_cards_by_ids`(노출 가능+이미지 보유 필터를
이미 수행하는 seam — 실제 시그니처는 `spots/services/cards.py`에서 확인) + `load_region_meta`
+ `load_overview_map`으로 카드 구성, `first_sentence(overview)` 적용, 후보 순서(거리순)
유지하며 이미지 있는 것만 앞에서 `_MATCH_COUNT`개. `_cache_get/_cache_set`은
`detail.py:61`의 fail-open JSON 패턴 복제 (`match:{id}`, `ex=_TTL_SECONDS`).

`feed/schemas.py`에 `MatchCard`·`MatchesResponse`, `feed/routes.py`에:

```python
@router.get("/overseas/{overseas_id}/matches")
async def overseas_matches(session: DbSession, redis: RedisDep,
                           overseas_id: int) -> dict[str, Any]:
    rows = await matching.find_matches(session, redis, overseas_id)
    return ok(MatchesResponse(
        overseasId=overseas_id,
        matches=[MatchCard(contentId=r.content_id, title=r.title, regionLabel=r.region_label,
                           imageUrl=r.image_url, overviewFirst=r.overview_first) for r in rows]))
```

- [ ] **Step 5: 통과 확인 + 게이트 + 커밋**

```bash
POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests/test_feed_matching.py tests/test_feed_text.py -v
uv run ruff check . && uv run mypy app && uv run lint-imports
git add app tests && git commit -m "feat(backend): 해외→국내 실시간 매칭 + match: Redis 캐시"
```

---

### Task A6: 백엔드 — 해외 임베딩 배치 (`scripts/embed_overseas.py`)

**Files:**
- Create: `backend/app/modules/feed/embedding_job.py`, `backend/scripts/embed_overseas.py`
- Test: `backend/tests/test_overseas_embedding_job.py`

**Interfaces:**
- Consumes: `app.core.embedding.embedder.embed_image(bytes)`,
  `images/embedding_job.py`의 다운로드·락·배치 커밋 패턴.
- Produces: `run_overseas_embedding_job(*, limit=None, concurrency=8, batch_size=50,
  session_factory=async_session_factory) -> dict[str, int]` (counters: targets, embedded,
  failed), CLI `uv run python -m scripts.embed_overseas [--limit N] [--concurrency N]`.

- [ ] **Step 1: 실패 테스트 작성**

기존 `images/embedding_job.py` 테스트(있다면 그 파일 패턴, 없다면 `test_taste_photo_search.py`의
CLIP monkeypatch 방식)를 따라: `ClipEmbedder.embed_image`를 `[0.1]*512` 반환으로
monkeypatch, httpx 다운로드는 `respx` 또는 transport mock으로 고정 바이트 반환.

```python
async def test_job_embeds_missing_rows(db_session, monkeypatch):
    # overseas_spots 2행 시드: 하나 embedding NULL, 하나 이미 있음
    counters = await run_overseas_embedding_job(session_factory=make_factory(db_session))
    assert counters["embedded"] == 1
    row = (await db_session.execute(text(
        "SELECT embedding IS NOT NULL FROM overseas_spots WHERE wikidata_id='QE1'"))).scalar()
    assert row is True


async def test_job_counts_download_failure(db_session, monkeypatch):
    counters = await run_overseas_embedding_job(session_factory=make_factory(db_session))
    assert counters["failed"] == 1
```

- [ ] **Step 2: 실패 확인**

```bash
POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests/test_overseas_embedding_job.py -v
```
Expected: FAIL (모듈 없음).

- [ ] **Step 3: 구현**

`feed/embedding_job.py` — `images/embedding_job.py`의 구조(semaphore 다운로드 병렬 +
`_embed_lock` 직렬 CLIP + 배치 커밋)를 overseas용으로 단순화:

```python
import asyncio

import httpx
from sqlalchemy import text

from app.core.db import async_session_factory
from app.core.embedding import embedder

_TARGETS_SQL = "SELECT id, image_url FROM overseas_spots WHERE embedding IS NULL ORDER BY id{limit}"
_WRITE_SQL = text("UPDATE overseas_spots SET embedding = CAST(:emb AS halfvec(512)), updated_at = now() WHERE id = :oid")
_embed_lock = asyncio.Lock()


async def run_overseas_embedding_job(*, limit: int | None = None, concurrency: int = 8,
                                     batch_size: int = 50,
                                     session_factory=async_session_factory) -> dict[str, int]:
    ...
```
본문은 `images/embedding_job.py`의 `run_embedding_job` 골격을 그대로 이식하되:
타깃 = 위 SQL, 성공 시 `_WRITE_SQL`, 실패는 counters["failed"] 증가 + 구조화 로그만
(실패 테이블 없음 — 대상이 수천 건이라 재실행으로 충분). embedding 문자열 리터럴은
`"[" + ",".join(f"{v:.8f}" for v in vec) + "]"`.

`scripts/embed_overseas.py` — `scripts/backfill_embeddings.py`의 argparse 래퍼 형식 복제:

```python
import argparse
import asyncio

from app.modules.feed.embedding_job import run_overseas_embedding_job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    counters = asyncio.run(run_overseas_embedding_job(
        limit=args.limit, concurrency=args.concurrency))
    print(counters)


if __name__ == "__main__":
    main()
```
(backfill_embeddings.py에 로깅 셋업·종료코드 관례가 있으면 그대로 맞춘다.)

- [ ] **Step 4: 통과 확인 + 게이트 + 커밋**

```bash
POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests/test_overseas_embedding_job.py -v
uv run ruff check . && uv run mypy app
git add app scripts tests && git commit -m "feat(backend): overseas 임베딩 배치 잡 + embed_overseas 스크립트"
```

---

### Task A7: 어드민 — 게시물(해외 스팟) 숨김 관리

**Files:**
- Modify: `backend/app/modules/admin/repositories.py`, `admin/services.py`,
  `admin/routes.py`, `admin/schemas.py`
- Create: `admin/mockups/overseas.html`, `admin/mockups/assets/overseas.js`,
  `admin/mockups/assets/overseas.css`
- Modify: `admin/mockups/{index,history,health,curation}.html` (네비에 "게시물" 링크),
  전체를 `backend/app/modules/admin/static/`에 복사 (drift check)
- Modify: `CLAUDE.md` (admin 쓰기 범위에 `overseas_spots.is_hidden` 추가)
- Test: `backend/tests/test_admin_overseas.py`

**Interfaces:**
- Produces: `GET /admin/api/overseas?q=&cursor=&limit=50` →
  `{items:[{id, nameKo, countryNameKo, imageUrl, fameScore, isHidden}], nextCursor}`,
  `PUT /admin/api/overseas/{id}/visibility` body `{"isHidden": bool}` → `{id, isHidden}`.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_admin_overseas.py` — 기존 admin 라우트 테스트의 로그인 세션 픽스처 방식 차용:

```python
async def test_list_overseas_requires_auth(client):
    res = await client.get("/admin/api/overseas")
    assert res.status_code == 401


async def test_list_overseas_search(admin_client, seeded_overseas):
    res = await admin_client.get("/admin/api/overseas", params={"q": "루브르"})
    items = res.json()["data"]["items"]
    assert len(items) == 1 and items[0]["nameKo"] == "루브르"


async def test_toggle_visibility(admin_client, seeded_overseas):
    oid = seeded_overseas.ids[0]
    res = await admin_client.put(f"/admin/api/overseas/{oid}/visibility",
                                 json={"isHidden": True})
    assert res.json()["data"]["isHidden"] is True
    res = await admin_client.get("/admin/api/overseas")
    target = [i for i in res.json()["data"]["items"] if i["id"] == oid][0]
    assert target["isHidden"] is True


async def test_hidden_spot_excluded_from_feed(client, admin_client, seeded_overseas):
    oid = seeded_overseas.ids[0]
    await admin_client.put(f"/admin/api/overseas/{oid}/visibility", json={"isHidden": True})
    res = await client.get("/v1/feed", params={"limit": 20})
    assert oid not in [i["id"] for i in res.json()["data"]["items"]]
```

- [ ] **Step 2: 백엔드 구현**

`admin/repositories.py` — admin 예외 관례(자체 raw 쿼리)로:

```python
async def list_overseas(session, *, q: str | None, cursor_id: int | None, limit: int):
    sql = ("SELECT id, name_ko, country_name_ko, image_url, fame_score, is_hidden "
           "FROM overseas_spots WHERE (:q IS NULL OR name_ko ILIKE '%%' || :q || '%%') "
           "AND (:cid IS NULL OR id > :cid) ORDER BY id LIMIT :lim")
    ...

async def set_overseas_hidden(session, overseas_id: int, hidden: bool) -> bool:
    result = await session.execute(text(
        "UPDATE overseas_spots SET is_hidden = :h, updated_at = now() "
        "WHERE id = :oid RETURNING id"), {"h": hidden, "oid": overseas_id})
    return result.first() is not None
```
`admin/services.py`: 커밋 + `_audit` 구조화 로그(기존 curation write들과 동일 형식) +
못 찾으면 `AdminCurationNotFound` 대신 신규 `AdminOverseasNotFound`(404) 추가
(`core/exceptions.py`). `admin/routes.py`: `AdminAuth` 게이트로 GET/PUT 2개 등록.

- [ ] **Step 3: 어드민 UI (mockups → static 복사)**

`admin/mockups/overseas.html`: 기존 `curation.html`의 마크업 골격(헤더·네비·테이블)을
복제해 목록 테이블(썸네일 img·이름·나라·유명도·상태 뱃지·숨김/해제 토글 버튼) +
상단 검색 input + "더 보기" 버튼(커서). `assets/overseas.js`: `curation.js`의 fetch 관례
(`/admin/api/...`, 401 시 `/admin/login` 리다이렉트)로 목록 로드·검색·토글 구현.
`assets/overseas.css`: `curation.css` 토큰 재사용, 페이지 고유 스타일만.
네비: 4개 기존 html의 네비 블록에 `<a href="/admin/overseas">게시물</a>` 추가하고
`overseas.html` 자신도 동일 네비 포함. `admin/routes.py`에 `GET /overseas` HTML 페이지
라우트(기존 `/curation` 페이지 서빙 방식 복제).

```bash
rsync -a --delete --exclude README.md admin/mockups/ backend/app/modules/admin/static/
bash .github/scripts/check-admin-mockup-drift.sh
```
Expected: drift check 통과.

- [ ] **Step 4: CLAUDE.md 갱신**

admin 예외 조항 두 곳(Architecture 절, Review guidelines 절 아님 — Architecture만)의
"scoped writes to `curations`/`curation_spots` only"를
"scoped writes to `curations`/`curation_spots`/`overseas_spots.is_hidden` only"로.

- [ ] **Step 5: 통과 확인 + 게이트 + 커밋**

```bash
POSTGRES_DB=pictrip_test NO_COLOR=1 uv run pytest tests/test_admin_overseas.py -v
uv run ruff check . && uv run mypy app && uv run lint-imports
git add backend/app backend/tests admin/mockups backend/app/modules/admin/static CLAUDE.md
git commit -m "feat(admin): 해외 게시물 숨김 관리 화면 + API"
```

---

### Task A8: 프로덕션 부트스트랩 + 매칭 임계값 튜닝 (스펙 §10.2·§10.3)

**Files:**
- Modify: `docs/plans/s13-a0-probe-results.md` (튜닝 결과 추가 기록)
- Modify(필요시): `backend/app/config.py` (`MATCH_DISTANCE_MAX` 확정값)

PR 머지·CT111 배포 후 실행하는 운영 태스크. dev 머지 = 라이브지만 이 시점까지 모바일은
아무것도 이 API를 부르지 않으므로 안전.

- [ ] **Step 1: ETL 본실행 (CT111)**

```bash
ssh root@100.83.101.1 "pct exec 111 -- bash -lc 'cd /opt/pictrip-pipeline/pipeline && uv run pictrip-data sync-overseas'"
```
Expected: sync_runs에 mode=overseas success 행. 규모 확인(목표 2,000~5,000):

```bash
ssh root@100.83.101.1 "pct exec 110 -- docker exec pictrip-postgres psql -U pictrip -d pictrip -c \"SELECT count(*), count(description_ko), count(image_author) FROM overseas_spots\""
```
2,000 미만이면 `MIN_SITELINKS`를 낮추거나 국가·클래스를 늘려 재실행. 결과를 기록.

- [ ] **Step 2: 샘플 100개 수동 검수 (스펙 §10.2 — 1회성 구축 검증)**

```sql
SELECT wikidata_id, name_ko, country_name_ko, description_ko, image_url
FROM overseas_spots ORDER BY random() LIMIT 100;
```
이름/설명 한국어 품질·이미지 적합성을 훑고, 부적합 행은 어드민 숨김 처리(A7 화면 사용).
불량률과 패턴(예: 특정 클래스 QID가 소음원)을 기록 — 필요 시 `_CLASS_QIDS` 조정 후 재적재.

- [ ] **Step 3: 임베딩 배치 (CT112 컨테이너)**

```bash
ssh root@100.83.101.1 "pct exec 112 -- docker exec api-host-api-1 python -m scripts.embed_overseas"
```
Expected: counters embedded ≈ 행 수. `SELECT count(*) FROM overseas_spots WHERE embedding IS NULL` → 0 근접.

- [ ] **Step 4: 매칭 임계값 튜닝 (스펙 §10.3)**

유명 스팟 20~30개로 눈검사:

```bash
for id in $(psql ... -tAc "SELECT id FROM overseas_spots ORDER BY fame_score DESC LIMIT 25"); do
  curl -s "https://api.pictrip.org/v1/overseas/${id}/matches" | python3 -c "..."
done
```
매칭 3곳의 그럴듯함을 보고 `MATCH_DISTANCE_MAX`(0.40/0.45/0.50)를 비교, 확정값을
config 기본값으로 커밋하고 CT112 `.env`에 반영 없이 코드 기본값으로 배포.
튜닝 판단과 확정값을 `s13-a0-probe-results.md`에 기록.

- [ ] **Step 5: 커밋**

```bash
git add docs/plans/s13-a0-probe-results.md backend/app/config.py
git commit -m "chore(s13): overseas 부트스트랩 검수 + 매칭 임계값 확정"
```

---

## Self-Review 체크 결과

- 스펙 §5.2(사전 임베딩→실시간 pgvector·Redis match:*·overview 조인) → A5·A6.
  §5.3(커서·다양성 셔플·새 시드) → A4. §6(탐색 동일 풀) → A4 `/explore`.
  §7.1(테이블·출처 4필드) → A1·A3. §7.2(SPARQL·유명도·월 1회) → A2·A3·A8
  (월 크론 등록은 B6에서 concentration 크론과 함께 처리). §8(어드민 is_hidden) → A7.
  §10.2·10.3·10.5 → A0·A8.
- 미커버 알림: 스펙 §5.2의 "미캐시 스팟 백그라운드 채움"은 기존 `warm_spot_details`
  프리워머가 인기 스팟을 이미 워밍하므로 초기 구현에서 인라인 백그라운드 태스크를 넣지
  않는다(overviewFirst=null 허용이 스펙에 명시됨). 매칭 결과가 자주 비면 후속에서
  warm 스크립트 대상을 매칭 후보로 확장.
