from __future__ import annotations

import io

from PIL import Image

from app.ml.embedding import ClipEmbedder
from app.modules.plan.services.ingest import ALLOWED_IMAGE_MIMES


def _heic_bytes() -> bytes:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(buffer, format="HEIF")
    return buffer.getvalue()


def test_heic_upload_decodes_after_registering_the_opener() -> None:
    payload = _heic_bytes()

    ClipEmbedder()._ensure_heif_decoder()
    decoded = Image.open(io.BytesIO(payload)).convert("RGB")

    assert decoded.size == (16, 16)


def test_every_advertised_upload_mime_is_decodable() -> None:
    ClipEmbedder()._ensure_heif_decoder()
    samples = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/heic": "HEIF",
    }

    assert set(samples) == ALLOWED_IMAGE_MIMES

    for mime, image_format in samples.items():
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), "blue").save(buffer, format=image_format)
        assert Image.open(io.BytesIO(buffer.getvalue())).convert("RGB").size == (16, 16), mime
