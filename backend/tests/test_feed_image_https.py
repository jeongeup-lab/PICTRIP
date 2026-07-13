"""feed KTO 이미지 URL은 http→https로 업그레이드된다 (iOS ATS가 http 이미지 로드를
차단 — 매치/채널 카드가 빈 화면으로 뜨던 원인). map/spots 스키마와 동일 규약."""

from __future__ import annotations

from app.modules.feed.schemas import ChannelCard, ChannelMeta, MatchCard, OverseasPost

KTO_HTTP = "http://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
KTO_HTTPS = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"


def test_match_card_upgrades_kto_http_to_https() -> None:
    card = MatchCard(
        contentId="1", title="t", regionLabel="강원", imageUrl=KTO_HTTP, overviewFirst=None
    )
    assert card.imageUrl == KTO_HTTPS


def test_channel_card_upgrades_kto_http_to_https() -> None:
    card = ChannelCard(contentId="1", title="t", regionLabel="강원", imageUrl=KTO_HTTP)
    assert card.imageUrl == KTO_HTTPS


def test_channel_meta_upgrades_thumbnail() -> None:
    meta = ChannelMeta(key="hot", label="Hot", thumbnailUrl=KTO_HTTP, available=True)
    assert meta.thumbnailUrl == KTO_HTTPS


def test_non_kto_and_null_untouched() -> None:
    commons = "https://upload.wikimedia.org/wikipedia/commons/a/ab/x.jpg"
    assert (
        OverseasPost(
            id=1,
            nameKo="n",
            countryCode="GR",
            countryNameKo="그리스",
            descriptionKo=None,
            imageUrl=commons,
            imageAuthor=None,
            imageLicense=None,
            imageLicenseUrl=None,
            imageSourceUrl=commons,
        ).imageUrl
        == commons
    )
    assert ChannelCard(contentId=None, title="t", regionLabel="", imageUrl=None).imageUrl is None
