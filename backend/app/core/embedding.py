"""CLIP image embedding (ADR-006: inline FastAPI, CPU).

The model is loaded lazily on first use. User-uploaded images are processed
in-memory and discarded immediately — never persisted to disk.
"""

from __future__ import annotations

import io
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 512  # CLIP ViT-B/32


class ClipEmbedder:
    """Lazy-loaded CLIP embedder. Keeps a single model instance per process."""

    # `transformers` and `torch` are intentionally Any-typed: importing them at
    # module level would add ~1s to cold start and force CI to install the GPU
    # variant of torch on every process, including request workers that may never
    # hit the photo-search path.
    _model: Any = None
    _processor: Any = None
    _torch: Any = None

    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._torch = None

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
        """Return a 512-dim L2-normalised embedding for the given image bytes."""
        from PIL import Image

        self._ensure_loaded()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt")
        if settings.CLIP_DEVICE != "cpu":
            inputs = {k: v.to(settings.CLIP_DEVICE) for k, v in inputs.items()}

        with self._torch.no_grad():
            features = self._model.get_image_features(**inputs)
            # transformers <5 returns the projected image-embeds tensor directly;
            # >=5 wraps it in a ModelOutput whose `pooler_output` holds the same
            # 512-dim projected embedding. Handle both so the embedder is
            # version-agnostic (the deployed image drifted to transformers 5.x).
            if not isinstance(features, self._torch.Tensor):
                features = features.pooler_output
            features = features / features.norm(dim=-1, keepdim=True)

        embedding: list[float] = features.squeeze(0).cpu().tolist()
        return embedding


embedder = ClipEmbedder()
