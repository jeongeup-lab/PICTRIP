from __future__ import annotations

import io
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 512


class ClipEmbedder:
    _model: Any = None
    _processor: Any = None
    _torch: Any = None
    _heif_registered: bool = False

    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._torch = None
        self._heif_registered = False

    def _ensure_heif_decoder(self) -> None:
        if self._heif_registered:
            return
        from pillow_heif import register_heif_opener

        register_heif_opener()
        self._heif_registered = True

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import CLIPModel, CLIPProcessor

        logger.info("clip.loading", model=settings.CLIP_MODEL_NAME, device=settings.CLIP_DEVICE)
        self._model = CLIPModel.from_pretrained(settings.CLIP_MODEL_NAME)
        self._processor = CLIPProcessor.from_pretrained(settings.CLIP_MODEL_NAME)
        self._model.eval()
        if settings.CLIP_DEVICE != "cpu":
            self._model = self._model.to(settings.CLIP_DEVICE)
        self._torch = torch

    def embed_image(self, image_bytes: bytes) -> list[float]:
        from PIL import Image

        self._ensure_heif_decoder()
        self._ensure_loaded()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt")
        if settings.CLIP_DEVICE != "cpu":
            inputs = {k: v.to(settings.CLIP_DEVICE) for k, v in inputs.items()}

        with self._torch.no_grad():
            features = self._model.get_image_features(**inputs)
            if not isinstance(features, self._torch.Tensor):
                features = features.pooler_output
            features = features / features.norm(dim=-1, keepdim=True)

        embedding: list[float] = features.squeeze(0).cpu().tolist()
        return embedding

    def embed_texts(self, prompts: list[str]) -> list[list[float]]:
        self._ensure_loaded()

        inputs = self._processor(text=prompts, return_tensors="pt", padding=True)
        if settings.CLIP_DEVICE != "cpu":
            inputs = {k: v.to(settings.CLIP_DEVICE) for k, v in inputs.items()}

        with self._torch.no_grad():
            features = self._model.get_text_features(**inputs)
            if not isinstance(features, self._torch.Tensor):
                features = features.pooler_output
            features = features / features.norm(dim=-1, keepdim=True)

        vectors: list[list[float]] = features.cpu().tolist()
        return vectors


embedder = ClipEmbedder()
