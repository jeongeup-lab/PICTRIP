from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.modules.agent import llm
from app.modules.agent.errors import AgentIntentUnavailable
from app.modules.agent.services.intent import _RESPONSE_SCHEMA
from app.web.errors import RateLimited


class StubClient:
    def __init__(self, name: str, *, error: Exception | None = None) -> None:
        self.name = name
        self.error = error
        self.calls = 0

    async def generate_json(self, **kwargs: Any) -> Any:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"served_by": self.name}

    async def aclose(self) -> None:
        return None


def _http_error(status: int) -> llm.ProviderError:
    request = httpx.Request("POST", "https://example.test")
    response = httpx.Response(status, request=request)
    return llm._classify("stub", httpx.HTTPStatusError("boom", request=request, response=response))


@pytest.fixture(autouse=True)
def reset_llm_state() -> Any:
    llm._clients = None
    llm._tripped.clear()
    llm._active = ""
    yield
    llm._clients = None
    llm._tripped.clear()
    llm._active = ""


def _install(*stubs: StubClient) -> None:
    llm._clients = list(stubs)


async def _call() -> Any:
    return await llm.generate_json(system="s", user_text="u", response_schema={})


async def test_the_primary_answers_and_becomes_the_reported_provider() -> None:
    primary = StubClient("Gemini")
    secondary = StubClient("Cerebras")
    _install(primary, secondary)

    assert await _call() == {"served_by": "Gemini"}
    assert llm.active_name() == "Gemini"
    assert secondary.calls == 0


async def test_a_rate_limited_primary_hands_the_call_to_the_secondary() -> None:
    primary = StubClient("Gemini", error=_http_error(429))
    secondary = StubClient("Cerebras")
    _install(primary, secondary)

    assert await _call() == {"served_by": "Cerebras"}
    assert llm.active_name() == "Cerebras"


async def test_a_server_error_on_the_primary_also_falls_through() -> None:
    primary = StubClient("Gemini", error=_http_error(503))
    secondary = StubClient("Cerebras")
    _install(primary, secondary)

    assert await _call() == {"served_by": "Cerebras"}


async def test_a_tripped_primary_is_skipped_on_the_next_call() -> None:
    primary = StubClient("Gemini", error=_http_error(429))
    secondary = StubClient("Cerebras")
    _install(primary, secondary)

    await _call()
    await _call()

    assert primary.calls == 1
    assert secondary.calls == 2


async def test_the_trip_expires_and_the_primary_is_tried_again() -> None:
    primary = StubClient("Gemini", error=_http_error(429))
    secondary = StubClient("Cerebras")
    _install(primary, secondary)

    await _call()
    llm._tripped["Gemini"] = 0.0
    await _call()

    assert primary.calls == 2


async def test_a_schema_rejection_is_not_retried_on_the_other_provider() -> None:
    primary = StubClient("Gemini", error=_http_error(400))
    secondary = StubClient("Cerebras")
    _install(primary, secondary)

    with pytest.raises(AgentIntentUnavailable):
        await _call()

    assert secondary.calls == 0
    assert "Gemini" not in llm._tripped


async def test_every_provider_rate_limited_surfaces_rate_limited() -> None:
    _install(
        StubClient("Gemini", error=_http_error(429)),
        StubClient("Cerebras", error=_http_error(429)),
    )

    with pytest.raises(RateLimited):
        await _call()


async def test_a_lone_provider_still_answers_after_its_trip_window_opens() -> None:
    only = StubClient("Gemini", error=_http_error(429))
    _install(only)

    with pytest.raises(RateLimited):
        await _call()

    only.error = None
    assert await _call() == {"served_by": "Gemini"}


async def test_cerebras_is_only_wired_up_when_its_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm.settings, "CEREBRAS_API_KEY", "")
    assert [client.name for client in llm.clients()] == ["Gemini"]

    llm._clients = None
    monkeypatch.setattr(llm.settings, "CEREBRAS_API_KEY", "sk-test")
    assert [client.name for client in llm.clients()] == ["Gemini", "Cerebras"]


def test_gemini_dialect_uppercases_types_and_drops_additional_properties() -> None:
    converted = llm.to_gemini_schema(_RESPONSE_SCHEMA)

    assert converted["type"] == "OBJECT"
    assert "additionalProperties" not in converted
    assert converted["properties"]["categoryKeywords"] == {
        "type": "ARRAY",
        "items": {"type": "STRING"},
    }
    assert converted["properties"]["festivalOnly"] == {"type": "BOOLEAN"}


def test_gemini_dialect_turns_a_nullable_union_into_the_nullable_flag() -> None:
    place = llm.to_gemini_schema(_RESPONSE_SCHEMA)["properties"]["namedPlaces"]["items"]

    assert place["properties"]["nameKo"] == {"type": "STRING", "nullable": True}
    assert place["properties"]["name"] == {"type": "STRING"}
    assert "additionalProperties" not in place


def test_gemini_dialect_keeps_enums_and_required_lists_intact() -> None:
    converted = llm.to_gemini_schema(_RESPONSE_SCHEMA)

    assert converted["properties"]["crowdPreference"]["enum"] == ["quiet", "any", "popular"]
    assert converted["required"] == _RESPONSE_SCHEMA["required"]


def test_canonical_schema_stays_strict_mode_compatible() -> None:
    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) == set(node.get("properties", {}))
        for value in node.get("properties", {}).values():
            walk(value)
        if "items" in node:
            walk(node["items"])

    walk(_RESPONSE_SCHEMA)
