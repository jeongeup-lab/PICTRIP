from __future__ import annotations

import pytest

from app.config import settings
from app.kto.display import T1_TILE_WIDTH, t1_display_url
from app.modules.feed.routes import _channel_card
from app.modules.feed.schemas import HomeSpotCard
from app.modules.feed.services.channels import ChannelCardRow

KTO_MID = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"


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


def test_only_type1_may_be_rewritten(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    assert t1_display_url(KTO_MID, "Type3") == KTO_MID
    assert t1_display_url(KTO_MID, "Type4") == KTO_MID
    assert t1_display_url(KTO_MID, "Type2") == KTO_MID
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


def test_channel_card_type3_survives_the_schema_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "IMG_PROXY_T1_SECRET", "s3cret")
    row = ChannelCardRow(
        content_id="1", title="t", region_label="부산", image_url=KTO_MID, cpyrht_div_cd="Type3"
    )
    card = _channel_card(row)
    assert card.imageUrl == KTO_MID


def test_home_card_type3_survives_the_schema_validator() -> None:
    card = HomeSpotCard(contentId="1", title="t", regionLabel="부산", imageUrl=KTO_MID)
    assert card.imageUrl == KTO_MID


def test_a_plain_http_data_go_kr_base_is_forced_to_https() -> None:
    from app.kto.client import https_data_go_kr

    assert (
        https_data_go_kr("http://apis.data.go.kr/B551011/KorService2")
        == "https://apis.data.go.kr/B551011/KorService2"
    )


def test_every_kto_service_resolves_to_https() -> None:
    from app.kto.client import _SERVICE_BASE

    assert all(base.startswith("https://") for base in _SERVICE_BASE.values())


def test_a_non_data_go_kr_base_is_left_alone() -> None:
    from app.kto.client import https_data_go_kr

    assert https_data_go_kr("http://localhost:9999/stub") == "http://localhost:9999/stub"
