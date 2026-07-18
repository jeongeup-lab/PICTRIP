from __future__ import annotations

import json
import re

import pytest

from app.config import settings
from app.modules.plan.llm import generate_json
from app.modules.plan.naver_local import search_local
from app.modules.plan.odsay import transit_minutes

_NAVER_URL = re.compile(r"https://openapi\.naver\.com/v1/search/local\.json.*")
_ODSAY_URL = re.compile(r"https://api\.odsay\.com/v1/api/searchPubTransPathT.*")
_GEMINI_URL = re.compile(r".*generativelanguage\.googleapis\.com.*:generateContent.*")


@pytest.fixture
def _naver_keys(monkeypatch):
    monkeypatch.setattr(settings, "NAVER_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", "secret")


@pytest.fixture
def _odsay_key(monkeypatch):
    monkeypatch.setattr(settings, "ODSAY_API_KEY", "okey")


@pytest.fixture
def _gemini_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gkey")


async def test_naver_strips_tags_and_scales_coords(_naver_keys, httpx_mock):
    httpx_mock.add_response(
        url=_NAVER_URL,
        json={
            "items": [
                {
                    "title": "<b>초당</b>할머니순두부",
                    "category": "한식>두부요리",
                    "roadAddress": "강원 강릉시",
                    "mapx": "1289112345",
                    "mapy": "377512345",
                }
            ]
        },
    )
    places = await search_local("강릉 맛집")
    assert len(places) == 1
    assert places[0].name == "초당할머니순두부"
    assert places[0].lat == pytest.approx(37.7512345)
    assert places[0].lng == pytest.approx(128.9112345)


async def test_naver_without_keys_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "NAVER_CLIENT_ID", "")
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", "")
    assert await search_local("강릉 맛집") == []


async def test_naver_request_error_returns_empty(_naver_keys, httpx_mock):
    httpx_mock.add_response(url=_NAVER_URL, status_code=500)
    assert await search_local("강릉 맛집") == []


async def test_odsay_parses_total_time(_odsay_key, httpx_mock):
    httpx_mock.add_response(
        url=_ODSAY_URL,
        json={"result": {"path": [{"info": {"totalTime": 42}}]}},
    )
    minutes = await transit_minutes(from_lat=37.7, from_lng=128.9, to_lat=37.8, to_lng=128.95)
    assert minutes == 42


async def test_odsay_bad_payload_returns_none(_odsay_key, httpx_mock):
    httpx_mock.add_response(url=_ODSAY_URL, json={"error": {"code": "500"}})
    assert await transit_minutes(from_lat=37.7, from_lng=128.9, to_lat=37.8, to_lng=128.95) is None


async def test_gemini_parses_json_text(_gemini_key, httpx_mock):
    httpx_mock.add_response(
        url=_GEMINI_URL,
        json={"candidates": [{"content": {"parts": [{"text": json.dumps({"region": "강릉"})}]}}]},
    )
    out = await generate_json(system="s", user="u", schema={"type": "OBJECT"})
    assert out == {"region": "강릉"}


async def test_gemini_bad_response_returns_none(_gemini_key, httpx_mock):
    httpx_mock.add_response(url=_GEMINI_URL, json={"candidates": []})
    assert await generate_json(system="s", user="u", schema={"type": "OBJECT"}) is None


async def test_gemini_without_key_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    assert await generate_json(system="s", user="u", schema={"type": "OBJECT"}) is None


async def test_clamp_days_bounds():
    from app.modules.plan.services.intent import clamp_days

    assert clamp_days(7) == 3
    assert clamp_days(2) == 2
    assert clamp_days(0) is None
    assert clamp_days("당일") is None


async def test_gemini_turn_parses_function_call(_gemini_key, httpx_mock):
    from app.modules.plan.llm import generate_turn

    httpx_mock.add_response(
        url=_GEMINI_URL,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"functionCall": {"name": "create_plan", "args": {"region": "강릉"}}}
                        ]
                    }
                }
            ]
        },
    )
    turn = await generate_turn(system="s", contents=[], tools=[])
    assert turn is not None
    assert turn.call_name == "create_plan"
    assert turn.call_args == {"region": "강릉"}


async def test_gemini_turn_parses_text(_gemini_key, httpx_mock):
    from app.modules.plan.llm import generate_turn

    httpx_mock.add_response(
        url=_GEMINI_URL,
        json={"candidates": [{"content": {"parts": [{"text": "며칠 일정이세요?"}]}}]},
    )
    turn = await generate_turn(system="s", contents=[], tools=[])
    assert turn is not None
    assert turn.call_name is None
    assert turn.text == "며칠 일정이세요?"
