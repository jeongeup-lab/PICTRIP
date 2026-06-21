"""Shared sido (province) region-code validation for region-scoped reads.

Extracted from the four copy-pasted blocks in catalog/similar/trending so the
normalise-then-validate logic has one source of truth.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailed
from app.modules.spots.models import Region


async def _validate_region(session: AsyncSession, region: str | None) -> str | None:
    """Normalise and validate a sido (province) region code.

    Strips whitespace and treats empty as ``None`` (no filter). Raises
    ``ValidationFailed`` when a non-empty code is not a real areacode. Returns
    the canonical region code, or ``None`` when no filter applies.
    """
    region_code = (region.strip() if region else None) or None
    if region_code is not None:
        known = await session.scalar(
            select(Region.ldong_regn_cd).where(Region.ldong_regn_cd == region_code)
        )
        if known is None:
            raise ValidationFailed(f"Unknown region code '{region_code}'.")
    return region_code
