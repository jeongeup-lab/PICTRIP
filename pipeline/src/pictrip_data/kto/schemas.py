"""KTO response parsing DTOs."""

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
