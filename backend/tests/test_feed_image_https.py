"""feed KTO 이미지 URL은 http→https로 업그레이드된다 (iOS ATS가 http 이미지 로드를
차단 — 매치/채널 카드가 빈 화면으로 뜨던 원인). map/spots 스키마와 동일 규약."""

from __future__ import annotations

from app.modules.feed.schemas import ChannelCard, ChannelMeta, MatchCard, OverseasPost

KTO_HTTP = "http://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
KTO_HTTPS = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
KTO_HIRES = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg"


def test_match_card_upgrades_kto_to_hires_https() -> None:
    # 매치 카드는 풀카드로 렌더 → https + 원본(_image1_1) 승격.
    card = MatchCard(
        contentId="1", title="t", regionLabel="강원", imageUrl=KTO_HTTP, overviewFirst=None
    )
    assert card.imageUrl == KTO_HIRES


def test_channel_card_upgrades_kto_to_hires_https() -> None:
    # 채널 카드는 스토리 전체화면으로 렌더 → https + 원본 승격.
    card = ChannelCard(contentId="1", title="t", regionLabel="강원", imageUrl=KTO_HTTP)
    assert card.imageUrl == KTO_HIRES


def test_channel_meta_thumbnail_stays_mid_https() -> None:
    # 채널 타일 썸네일은 작아서 원본 불필요 — https만 승격, 크기는 940px 유지.
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
    # snap uses non-KTO https URLs (galWebImageUrl) — must be kept, not nulled.
    ext = "https://cdn.example.com/gallery/1.jpg"
    assert ChannelCard(contentId=None, title="t", regionLabel="", imageUrl=ext).imageUrl == ext
    assert (
        ChannelMeta(key="snap", label="Snap", thumbnailUrl=ext, available=True).thumbnailUrl == ext
    )
