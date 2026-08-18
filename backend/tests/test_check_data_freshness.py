from __future__ import annotations

import pytest

from scripts.check_data_freshness import CHECKS, _age_hours


def test_checks_cover_every_ingestion_surface() -> None:
    names = {c.name for c in CHECKS}
    assert names == {
        "spots.modified_time",
        "sync_runs.incremental",
        "spot_concentration.collected_at",
        "overseas_spots.updated_at",
    }


def test_thresholds_leave_room_for_the_job_cadence() -> None:
    by_name = {c.name: c.max_age_hours for c in CHECKS}
    assert by_name["sync_runs.incremental"] > 24
    assert by_name["spot_concentration.collected_at"] > 24
    assert by_name["overseas_spots.updated_at"] > 24 * 31


def test_overseas_check_uses_the_oldest_row() -> None:
    check = next(c for c in CHECKS if c.name == "overseas_spots.updated_at")
    assert "min(updated_at)" in check.sql


@pytest.mark.asyncio
async def test_age_hours_is_none_when_table_is_empty(db_session) -> None:
    age = await _age_hours(db_session, "SELECT max(updated_at) FROM overseas_spots")
    assert age is None
