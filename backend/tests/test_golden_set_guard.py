from __future__ import annotations

import pytest

from scripts.travel_golden_set import DEFAULT_BASE_URL, targets_a_shared_key


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.pictrip.org",
        "https://api.pictrip.org/v1",
        "http://100.83.101.1:8000",
        "http://ct112.local:8000",
    ],
)
def test_a_remote_target_shares_the_production_gemini_key(base_url: str) -> None:
    assert targets_a_shared_key(base_url) is True


@pytest.mark.parametrize(
    "base_url",
    [
        DEFAULT_BASE_URL,
        "http://localhost:8099",
        "http://127.0.0.1:8000",
        "http://[::1]:8099",
    ],
)
def test_a_loopback_target_runs_against_a_local_key(base_url: str) -> None:
    assert targets_a_shared_key(base_url) is False


def test_a_base_url_without_a_host_is_treated_as_shared_rather_than_assumed_safe() -> None:
    assert targets_a_shared_key("not a url") is True
