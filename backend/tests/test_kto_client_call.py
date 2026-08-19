import httpx
import pytest

from app.kto.client import KtoClient, KtoService, redact_service_key
from app.web.errors import KtoApiUnavailable, KtoQuotaExhausted

QUOTA_BODY = (
    '{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{'
    '"errMsg":"LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",'
    '"returnAuthMsg":"일일 서비스 요청제한 횟수 초과 에러","returnReasonCode":"22"}}}'
)
OK_BODY = {
    "response": {
        "header": {"resultCode": "0000", "resultMsg": "OK"},
        "body": {"items": {"item": [{"contentid": "1", "overview": "설명"}]}},
    }
}


def _client(handler: object) -> KtoClient:
    kto = KtoClient()
    kto._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    return kto


async def _call(kto: KtoClient) -> list[dict[str, object]]:
    try:
        return await kto.call(KtoService.KOR, "detailCommon2", contentId="1")
    finally:
        await kto.aclose()


@pytest.mark.anyio
async def test_transient_server_error_is_retried_until_success() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            return httpx.Response(503, text="upstream down")
        return httpx.Response(200, json=OK_BODY)

    assert await _call(_client(handler)) == [{"contentid": "1", "overview": "설명"}]
    assert len(attempts) == 2


@pytest.mark.anyio
async def test_daily_quota_429_raises_without_retry() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(429, text=QUOTA_BODY)

    with pytest.raises(KtoQuotaExhausted):
        await _call(_client(handler))
    assert len(attempts) == 1


@pytest.mark.anyio
async def test_quota_exhausted_is_a_kto_api_unavailable() -> None:
    assert issubclass(KtoQuotaExhausted, KtoApiUnavailable)


@pytest.mark.anyio
async def test_http_200_rejection_is_not_an_empty_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"resultCode": "10", "resultMsg": "INVALID_REQUEST_PARAMETER_ERROR(contentId)"},
        )

    with pytest.raises(KtoApiUnavailable):
        await _call(_client(handler))


@pytest.mark.anyio
async def test_non_ok_result_code_in_envelope_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"response": {"header": {"resultCode": "22", "resultMsg": "LIMIT"}, "body": {}}},
        )

    with pytest.raises(KtoApiUnavailable):
        await _call(_client(handler))


@pytest.mark.anyio
async def test_empty_items_still_return_empty_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"response": {"header": {"resultCode": "0000"}, "body": {"items": ""}}}
        )

    assert await _call(_client(handler)) == []


def test_service_key_never_reaches_logs() -> None:
    raw = "GET https://apis.data.go.kr/x?serviceKey=N2HXHIq9lb1%2Bs&contentId=1 failed"
    assert "N2HXHIq9lb1" not in redact_service_key(raw)
    assert "contentId=1" in redact_service_key(raw)
