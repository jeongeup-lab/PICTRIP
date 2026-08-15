from __future__ import annotations

from app.modules.feed.schemas import ChannelCard, ChannelMeta, MatchCard, OverseasPost

KTO_HTTP = "http://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
KTO_HTTPS = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"


def test_match_card_forces_https_without_rewriting_the_path() -> None:
    card = MatchCard(
        contentId="1", title="t", regionLabel="강원", imageUrl=KTO_HTTP, overviewFirst=None
    )
    assert card.imageUrl == KTO_HTTPS


def test_channel_card_forces_https_without_rewriting_the_path() -> None:
    card = ChannelCard(contentId="1", title="t", regionLabel="강원", imageUrl=KTO_HTTP)
    assert card.imageUrl == KTO_HTTPS


def test_channel_meta_thumbnail_stays_mid_https() -> None:
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


def test_non_kto_https_preserved_on_channels() -> None:
    ext = "https://cdn.example.com/gallery/1.jpg"
    assert ChannelCard(contentId=None, title="t", regionLabel="", imageUrl=ext).imageUrl == ext
    assert (
        ChannelMeta(key="snap", label="Snap", thumbnailUrl=ext, available=True).thumbnailUrl == ext
    )
