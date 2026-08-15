from __future__ import annotations

from sqlalchemy import exists
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.expression import Exists

from app.modules.images.models import SpotEmbedding


def spot_has_embedding_clause(correlate_col: InstrumentedAttribute[str]) -> Exists:
    return exists().where(SpotEmbedding.content_id == correlate_col)
