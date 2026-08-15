from __future__ import annotations

import pytest

from app.modules.spots.schemas import SpotCard, SpotImageOut


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "http://tong.visitkorea.or.kr/cms/resource/57/3390157_image2_1.jpg",
            "https://tong.visitkorea.or.kr/cms/resource/57/3390157_image2_1.jpg",
        ),
        (
            "https://tong.visitkorea.or.kr/cms/resource/56/4066656_image2_1.jpg",
            "https://tong.visitkorea.or.kr/cms/resource/56/4066656_image2_1.jpg",
        ),
        ("http://example.com/x.jpg", "http://example.com/x.jpg"),
        (None, None),
    ],
)
def test_spot_card_first_image_url_https_upgrade(raw: str | None, expected: str | None) -> None:
    card = SpotCard(contentId="1", title="t", firstImageUrl=raw)
    assert card.firstImageUrl == expected


def test_spot_image_out_https_upgrade() -> None:
    img = SpotImageOut(
        originImageUrl="http://tong.visitkorea.or.kr/origin.jpg",
        smallImageUrl="http://tong.visitkorea.or.kr/small.jpg",
    )
    assert img.originImageUrl == "https://tong.visitkorea.or.kr/origin.jpg"
    assert img.smallImageUrl == "https://tong.visitkorea.or.kr/small.jpg"
