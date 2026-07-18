from __future__ import annotations

from urllib.parse import quote

from app.modules.plan.schemas import ExternalLinks


def place_links(name: str, lat: float | None, lng: float | None) -> ExternalLinks:
    naver = f"https://map.naver.com/p/search/{quote(name)}"
    kakao = f"https://map.kakao.com/link/map/{quote(name)},{lat},{lng}" if lat and lng else None
    return ExternalLinks(naver=naver, kakao=kakao)
