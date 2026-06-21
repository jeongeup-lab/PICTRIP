"""PR-A: shared region-code validation helper (DRY of 4 copy-pasted blocks)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailed
from app.modules.spots.services.region import _validate_region


@pytest.mark.asyncio
async def test_known_code_passes_through(db_session: AsyncSession) -> None:
    assert await _validate_region(db_session, "51") == "51"


@pytest.mark.asyncio
async def test_unknown_code_raises_validation_failed(db_session: AsyncSession) -> None:
    with pytest.raises(ValidationFailed, match="'99'"):
        await _validate_region(db_session, "99")


@pytest.mark.asyncio
async def test_whitespace_around_valid_code_is_trimmed(db_session: AsyncSession) -> None:
    assert await _validate_region(db_session, "  51  ") == "51"


@pytest.mark.asyncio
async def test_empty_and_whitespace_normalise_to_none(db_session: AsyncSession) -> None:
    assert await _validate_region(db_session, None) is None
    assert await _validate_region(db_session, "") is None
    assert await _validate_region(db_session, "   ") is None
