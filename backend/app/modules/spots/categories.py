from __future__ import annotations

from enum import StrEnum

from sqlalchemy import and_, or_
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ColumnElement

from app.modules.spots.models import Spot

_VE_EXCLUDE = ("VE06", "VE07", "VE08", "VE09", "VE10", "VE11")

_TRAVEL_VE_EXCLUDE = ("VE08", "VE09", "VE10", "VE11")

_LODGING_CONTENT_TYPE = 32


class NearbyCategory(StrEnum):
    attraction = "attraction"
    food = "food"
    cafe = "cafe"
    leisure = "leisure"
    shopping = "shopping"


def category_predicate(cat: NearbyCategory) -> ColumnElement[bool]:
    if cat is NearbyCategory.attraction:
        return and_(
            Spot.content_type_id != _LODGING_CONTENT_TYPE,
            or_(
                Spot.lcls_systm1.in_(("HS", "NA", "EX")),
                and_(
                    Spot.lcls_systm1 == "VE",
                    or_(Spot.lcls_systm2.is_(None), Spot.lcls_systm2.notin_(_VE_EXCLUDE)),
                ),
            ),
        )
    if cat is NearbyCategory.food:
        return and_(
            Spot.lcls_systm2.in_(("FD01", "FD02", "FD03")),
            or_(Spot.lcls_systm3.is_(None), Spot.lcls_systm3 != "FD030100"),
        )
    if cat is NearbyCategory.cafe:
        return or_(Spot.lcls_systm2 == "FD05", Spot.lcls_systm3 == "FD030100")
    if cat is NearbyCategory.leisure:
        return Spot.lcls_systm1 == "LS"
    return and_(
        Spot.lcls_systm1 == "SH",
        or_(Spot.lcls_systm2.is_(None), Spot.lcls_systm2 != "SH04"),
    )


def all_categories_predicate() -> ColumnElement[bool]:
    return or_(*(category_predicate(c) for c in NearbyCategory))


def _predicate_sql(predicate: ColumnElement[bool]) -> str:
    return str(
        predicate.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )


def category_sql(cat: NearbyCategory) -> str:
    return _predicate_sql(category_predicate(cat))


def all_categories_sql() -> str:
    return _predicate_sql(all_categories_predicate())


def attraction_category_sql() -> str:
    return _predicate_sql(category_predicate(NearbyCategory.attraction))


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


def in_travel_pool(code: str) -> bool:
    """여행지 풀은 숙박·레포츠·쇼핑을 뺀다 — 코드가 풀려도 결과가 0곳인 종류가 있다."""
    if code.startswith(("HS", "NA", "EX")):
        return True
    return code.startswith("VE") and not code.startswith(_TRAVEL_VE_EXCLUDE)


def travel_category_sql() -> str:
    return _predicate_sql(travel_category_predicate())


def derive_category(l1: str | None, l2: str | None, l3: str | None) -> str | None:
    if l2 == "FD05" or l3 == "FD030100":
        return "cafe"
    if l2 in ("FD01", "FD02", "FD03") and l3 != "FD030100":
        return "food"
    if l1 in ("HS", "NA", "EX") or (l1 == "VE" and l2 not in _VE_EXCLUDE):
        return "attraction"
    if l1 == "LS":
        return "leisure"
    if l1 == "SH" and l2 != "SH04":
        return "shopping"
    return None
