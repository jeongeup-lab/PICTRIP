"""IMG repositories — DB queries; SQLAlchemy lives here."""

from __future__ import annotations

from sqlalchemy import exists
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.expression import Exists

from app.modules.images.models import SpotEmbedding


def spot_has_embedding_clause(correlate_col: InstrumentedAttribute[str]) -> Exists:
    """EXISTS clause: a spot_embeddings row whose content_id matches the outer column."""
    return exists().where(SpotEmbedding.content_id == correlate_col)
