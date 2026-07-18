from __future__ import annotations

import pytest

from app.config import settings
from app.modules.feed.routes import _channel_card
from app.modules.feed.services.channels import ChannelCardRow
from app.modules.feed.services.display import T1_TILE_WIDTH, t1_display_url

KTO_MID = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
KTO_HIRES = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg"


def test_type1_returns_signed_transform_at_full_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    url = t1_display_url(KTO_MID, "Type1")
    assert url is not None
    assert url.startswith("https://img.pictrip.org/t1/1620/")
    assert url.endswith("/tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg")


def test_tile_width_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    url = t1_display_url(KTO_MID, "Type1", width=T1_TILE_WIDTH)
    assert url is not None
    assert url.startswith("https://img.pictrip.org/t1/320/")


def test_type3_unknown_and_no_secret_pass_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    assert t1_display_url(KTO_MID, "Type3") == KTO_MID
    assert t1_display_url(KTO_MID, None) == KTO_MID
    assert t1_display_url(None, "Type1") is None
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "")
    assert t1_display_url(KTO_MID, "Type1") == KTO_MID


def test_channel_card_type1_gets_transform_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    row = ChannelCardRow(
        content_id="1", title="t", region_label="부산", image_url=KTO_MID, cpyrht_div_cd="Type1"
    )
    card = _channel_card(row)
    assert card.imageUrl is not None
    assert card.imageUrl.startswith("https://img.pictrip.org/t1/1620/")


def test_channel_card_type3_keeps_hires_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    row = ChannelCardRow(
        content_id="1", title="t", region_label="부산", image_url=KTO_MID, cpyrht_div_cd="Type3"
    )
    card = _channel_card(row)
    assert card.imageUrl == KTO_HIRES
