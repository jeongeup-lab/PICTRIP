from __future__ import annotations

import io

import pytest
from PIL import Image
from starlette.requests import Request

from app.modules.agent import routes, search
from app.modules.agent.schemas import QueryIntent, RefinePatch

PHOTO = b"\xff\xd8\xff\xe0"
MESSAGE = "이거 어디야"


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


def _multipart(payload: bytes, declared: bytes) -> Request:
    body = (
        b"--B\r\n"
        b'Content-Disposition: form-data; name="photo"; filename="a.jpg"\r\n'
        b"Content-Type: " + declared + b"\r\n\r\n" + payload + b"\r\n"
        b"--B\r\n"
        b'Content-Disposition: form-data; name="message"\r\n\r\n' + MESSAGE.encode() + b"\r\n"
        b"--B--\r\n"
    )
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/agent/chat",
        "headers": [
            (b"content-type", b"multipart/form-data; boundary=B"),
            (b"content-length", str(len(body)).encode()),
        ],
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def test_photo_without_a_chip_searches_the_whole_country() -> None:
    call = search._opening(None, PHOTO, None, None)

    assert call is not None
    assert call.name == "uploaded_photo"
    assert call.args == {}


def test_chip_on_a_photo_turn_keeps_the_photo_and_the_region() -> None:
    intent = QueryIntent(regionHints=["통영"])

    call = search._opening(None, PHOTO, intent, RefinePatch(crowdPreference="quiet"))

    assert call is not None
    assert call.name == "uploaded_photo"
    assert call.args == {"regions": ["통영"]}


def test_widening_the_region_drops_it_from_the_photo_search() -> None:
    intent = QueryIntent(regionHints=["통영"])

    call = search._opening(None, PHOTO, intent, RefinePatch(drop="region"))

    assert call is not None
    assert call.name == "uploaded_photo"
    assert call.args == {}


@pytest.mark.asyncio
async def test_upload_mime_comes_from_the_bytes_not_the_client_header() -> None:
    """expo/fetch 가 붙이는 content-type 을 믿으면 멀쩡한 사진이 튕긴다."""
    fields, image_bytes, image_mime = await routes._read_fields(
        _multipart(_jpeg(), b"application/octet-stream")
    )

    assert image_mime == "image/jpeg"
    assert image_bytes is not None
    assert fields["message"] == MESSAGE


@pytest.mark.asyncio
async def test_a_format_we_do_not_accept_gets_no_mime() -> None:
    _fields, image_bytes, image_mime = await routes._read_fields(
        _multipart(b"GIF89a" + b"\x00" * 32, b"image/jpeg")
    )

    assert image_bytes is not None
    assert image_mime is None
