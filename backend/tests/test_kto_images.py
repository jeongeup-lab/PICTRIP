from __future__ import annotations

import hashlib
import hmac

from app.kto.client import hires_kto_image, https_kto_image, t1_transform_url

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
    tricky = "https://example.com/img?u=https://tong.visitkorea.or.kr/x_image2_1.jpg"
    assert hires_kto_image(tricky) == tricky


def test_foreign_http_url_with_kto_substring_not_https_promoted() -> None:
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


def test_t1_transform_url_signs_kto_url() -> None:
    url = t1_transform_url(BIG_HTTPS, width=1080, secret="s3cret", origin="https://img.pictrip.org")
    assert url is not None
    prefix = "https://img.pictrip.org/t1/1080/"
    assert url.startswith(prefix)
    sig, _, target = url[len(prefix) :].partition("/")
    assert target == "tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg"
    assert sig == hmac.new(b"s3cret", f"1080/{target}".encode(), hashlib.sha256).hexdigest()


def test_t1_transform_url_upgrades_http_before_signing() -> None:
    http_url = "http://tong.visitkorea.or.kr/cms/resource/98/3045598_image1_1.jpg"
    assert t1_transform_url(http_url, width=1080, secret="s", origin="https://o") == (
        t1_transform_url(BIG_HTTPS, width=1080, secret="s", origin="https://o")
    )


def test_t1_transform_url_disabled_without_secret() -> None:
    assert t1_transform_url(BIG_HTTPS, width=1080, secret="", origin="https://o") is None


def test_t1_transform_url_non_kto_and_none_untouched() -> None:
    commons = "https://upload.wikimedia.org/wikipedia/commons/a/ab/x.jpg"
    assert t1_transform_url(commons, width=1080, secret="s", origin="https://o") is None
    assert t1_transform_url(None, width=1080, secret="s", origin="https://o") is None
