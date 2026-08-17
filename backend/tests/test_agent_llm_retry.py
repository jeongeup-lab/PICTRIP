import httpx
import pytest

from app.modules.agent.llm import MAX_ERROR_BODY_CHARS, _failure_detail, _is_transient


def _status_error(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models")
    response = httpx.Response(status, request=request, text=body)
    return httpx.HTTPStatusError("err", request=request, response=response)


def test_a_quota_429_is_not_retried_because_retrying_only_burns_more_quota() -> None:
    assert _is_transient(_status_error(429)) is False


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_are_still_retried(status: int) -> None:
    assert _is_transient(_status_error(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_deterministic_client_errors_are_not_retried(status: int) -> None:
    assert _is_transient(_status_error(status)) is False


def test_network_failures_are_still_retried() -> None:
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models")
    assert _is_transient(httpx.ConnectTimeout("timeout", request=request)) is True
    assert _is_transient(httpx.ConnectError("refused", request=request)) is True
    assert _is_transient(httpx.RemoteProtocolError("hung up", request=request)) is True


def test_unrelated_exceptions_are_not_retried() -> None:
    assert _is_transient(ValueError("nope")) is False


def test_a_429_body_is_carried_into_the_log_so_the_quota_can_be_named() -> None:
    body = '{"error":{"code":429,"message":"Quota exceeded for generate_content_free_tier"}}'
    assert _failure_detail(_status_error(429, body)) == body


def test_a_long_error_body_is_clipped_so_one_failure_cannot_flood_the_log() -> None:
    detail = _failure_detail(_status_error(429, "x" * (MAX_ERROR_BODY_CHARS + 500)))
    assert detail is not None
    assert len(detail) == MAX_ERROR_BODY_CHARS


def test_a_failure_without_a_response_has_no_body_to_report() -> None:
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models")
    assert _failure_detail(httpx.ConnectTimeout("timeout", request=request)) is None
    assert _failure_detail(ValueError("nope")) is None


def _gemini_probe() -> tuple[object, list[httpx.Request]]:
    from app.modules.agent import llm

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        return httpx.Response(200, json=payload)

    client = llm.GeminiClient()
    client._client = httpx.AsyncClient(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    )
    return client, seen


async def test_structured_calls_bound_the_output_so_a_runaway_cannot_flood_the_turn() -> None:
    from app.modules.agent.llm import STRUCTURED_MAX_OUTPUT_TOKENS

    client, seen = _gemini_probe()
    await client.generate_json(system="s", user_text="q", response_schema={"type": "OBJECT"})

    import json as _json

    body = _json.loads(seen[0].content)
    assert body["generationConfig"]["maxOutputTokens"] == STRUCTURED_MAX_OUTPUT_TOKENS


async def test_structured_calls_time_out_fast_enough_for_the_keyword_fallback_to_matter() -> None:
    from app.modules.agent.llm import STRUCTURED_TIMEOUT_SECONDS

    client, seen = _gemini_probe()
    await client.generate_json(system="s", user_text="q", response_schema={"type": "OBJECT"})

    timeout = seen[0].extensions["timeout"]
    assert timeout["read"] == STRUCTURED_TIMEOUT_SECONDS
    assert STRUCTURED_TIMEOUT_SECONDS <= 5.0
