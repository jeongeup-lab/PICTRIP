"""hires_kto_image: KTO 대표이미지 URL을 `_image2_1`(940px)에서 `_image1_1`(≈1620px)
원본으로 승격한다. https_kto_image와 동일한 transport-only 규약 — 다운로드·저장 없음."""

from __future__ import annotations

from app.core.kto_images import hires_kto_image, https_kto_image

MID_HTTPS = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
BIG_HTTPS = "https://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg"


def test_upgrades_mid_to_original() -> None:
    assert hires_kto_image(MID_HTTPS) == BIG_HTTPS


def test_also_upgrades_http_to_https() -> None:
    http_mid = "http://tong.visitkorea.or.kr/cms/resource/98/3045598_image2_1.jpg"
    assert hires_kto_image(http_mid) == BIG_HTTPS


def test_uppercase_extension_preserved() -> None:
    mid = "https://tong.visitkorea.or.kr/cms/resource/47/3383547_image2_1.JPG"
    big = "https://tong.visitkorea.or.kr/cms/resource/47/3383547_image1_1.JPG"
    assert hires_kto_image(mid) == big


def test_already_original_unchanged() -> None:
    assert hires_kto_image(BIG_HTTPS) == BIG_HTTPS


def test_non_kto_untouched() -> None:
    commons = "https://upload.wikimedia.org/wikipedia/commons/a/ab/x_image2_1.jpg"
    assert hires_kto_image(commons) == commons


def test_kto_host_only_as_substring_untouched() -> None:
    # Real host is example.com; the KTO host merely appears in a query param.
    tricky = "https://example.com/img?u=https://tong.visitkorea.or.kr/x_image2_1.jpg"
    assert hires_kto_image(tricky) == tricky


def test_foreign_http_url_with_kto_substring_not_https_promoted() -> None:
    # Regression: hires must not inherit https_kto_image's old substring match and flip the
    # outer scheme of a foreign http URL that only mentions the KTO host in a query param.
    tricky = "http://example.com/img?u=http://tong.visitkorea.or.kr/x_image2_1.jpg"
    assert hires_kto_image(tricky) == tricky
    assert https_kto_image(tricky) == tricky


def test_https_promotion_only_for_real_kto_host() -> None:
    assert (
        https_kto_image("http://tong.visitkorea.or.kr/cms/x_image2_1.jpg")
        == "https://tong.visitkorea.or.kr/cms/x_image2_1.jpg"
    )


def test_none_untouched() -> None:
    assert hires_kto_image(None) is None
