"""KTO retry policy: only transient failures (429/5xx/connection) are retried.

Non-transient 4xx (bad serviceKey, bad params) must raise immediately —
retrying them burns the shared daily quota for zero benefit.
"""

import httpx
import pytest

from app.core.kto_client import _is_transient


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://apis.data.go.kr/test")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_transient_statuses_are_retried(status: int) -> None:
    assert _is_transient(_status_error(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_non_transient_4xx_raise_immediately(status: int) -> None:
    assert _is_transient(_status_error(status)) is False


def test_connection_errors_are_retried() -> None:
    request = httpx.Request("GET", "https://apis.data.go.kr/test")
    assert _is_transient(httpx.ConnectTimeout("timeout", request=request)) is True
    assert _is_transient(httpx.ConnectError("refused", request=request)) is True
    assert _is_transient(httpx.RemoteProtocolError("server hung up", request=request)) is True


def test_deterministic_client_errors_are_not_retried() -> None:
    request = httpx.Request("GET", "https://apis.data.go.kr/test")
    assert _is_transient(httpx.UnsupportedProtocol("bad scheme", request=request)) is False
    assert _is_transient(httpx.TooManyRedirects("loop", request=request)) is False
    assert _is_transient(httpx.DecodingError("bad gzip", request=request)) is False


def test_unrelated_exceptions_are_not_retried() -> None:
    assert _is_transient(ValueError("nope")) is False
