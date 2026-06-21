import pytest

from app.core.exceptions import OAuthProviderUnavailable
from app.core.kakao_oidc import _jwks_cache, get_jwks


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    _jwks_cache.clear()
    yield
    _jwks_cache.clear()


@pytest.mark.asyncio
async def test_get_jwks_caches_after_fetch(mock_kakao_jwks, kakao_signing_key):
    _, expected = kakao_signing_key
    first = await get_jwks()
    second = await get_jwks()  # served from cache, no second HTTP call
    assert first == expected
    assert second == expected


@pytest.mark.asyncio
async def test_get_jwks_raises_on_initial_failure(httpx_mock):
    # _fetch_jwks retries once → two attempts, each needs a registered response
    for _ in range(2):
        httpx_mock.add_exception(
            Exception("network down"),
            url="https://kauth.kakao.com/.well-known/jwks.json",
        )
    with pytest.raises(OAuthProviderUnavailable):
        await get_jwks()


@pytest.mark.asyncio
async def test_get_jwks_serves_stale_on_error(httpx_mock, kakao_signing_key):
    _, jwks = kakao_signing_key
    # first call succeeds and populates cache
    httpx_mock.add_response(url="https://kauth.kakao.com/.well-known/jwks.json", json=jwks)
    await get_jwks()
    # force expiry of fresh TTL
    _jwks_cache["fresh_until"] = 0
    # next call: upstream is down, but stale value should be served
    # _fetch_jwks retries once → two attempts, each needs a registered response
    for _ in range(2):
        httpx_mock.add_exception(
            Exception("network down"),
            url="https://kauth.kakao.com/.well-known/jwks.json",
        )
    stale = await get_jwks()
    assert stale == jwks


# ---------------------------------------------------------------------------
# verify_id_token tests
# ---------------------------------------------------------------------------

from app.core.exceptions import OAuthIdTokenInvalid  # noqa: E402
from app.core.kakao_oidc import KakaoClaims, verify_id_token  # noqa: E402
from tests.conftest import make_kakao_id_token  # noqa: E402 — plain helper, not a fixture


@pytest.fixture
def override_settings(monkeypatch):
    monkeypatch.setattr("app.config.settings.KAKAO_REST_API_KEY", "test-rest-api-key")


@pytest.mark.asyncio
async def test_verify_id_token_happy_path(mock_kakao_jwks, kakao_signing_key, override_settings):
    priv, _ = kakao_signing_key
    token = make_kakao_id_token(sub="12345", key=priv)
    claims = await verify_id_token(token)
    assert isinstance(claims, KakaoClaims)
    assert claims.sub == "12345"


@pytest.mark.asyncio
async def test_verify_id_token_rejects_bad_signature(
    mock_kakao_jwks, kakao_signing_key, override_settings
):
    from cryptography.hazmat.primitives.asymmetric import rsa

    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_kakao_id_token(sub="12345", key=other)
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_id_token(token)


@pytest.mark.asyncio
async def test_verify_id_token_rejects_wrong_aud(
    mock_kakao_jwks, kakao_signing_key, override_settings
):
    priv, _ = kakao_signing_key
    token = make_kakao_id_token(sub="12345", aud="someone-else", key=priv)
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_id_token(token)


@pytest.mark.asyncio
async def test_verify_id_token_rejects_wrong_iss(
    mock_kakao_jwks, kakao_signing_key, override_settings
):
    priv, _ = kakao_signing_key
    token = make_kakao_id_token(sub="12345", iss="https://attacker.example", key=priv)
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_id_token(token)


@pytest.mark.asyncio
async def test_verify_id_token_rejects_expired(
    mock_kakao_jwks, kakao_signing_key, override_settings
):
    priv, _ = kakao_signing_key
    token = make_kakao_id_token(sub="12345", exp_offset=-400, key=priv)
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_id_token(token)


@pytest.mark.asyncio
async def test_verify_id_token_rejects_nonce_mismatch(
    mock_kakao_jwks, kakao_signing_key, override_settings
):
    priv, _ = kakao_signing_key
    token = make_kakao_id_token(sub="12345", nonce="abc", key=priv)
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_id_token(token, expected_nonce="xyz")


@pytest.mark.asyncio
async def test_verify_id_token_unknown_kid_with_fresh_jwks(
    mock_kakao_jwks, kakao_signing_key, override_settings
):
    priv, _ = kakao_signing_key
    token = make_kakao_id_token(sub="12345", key=priv, kid="unknown-kid")
    with pytest.raises(OAuthIdTokenInvalid):
        await verify_id_token(token)


@pytest.mark.asyncio
async def test_kakao_rejected_when_no_audience_configured(
    mock_kakao_jwks, kakao_signing_key, monkeypatch
):
    # With NO Kakao audience configured, `valid_audiences` is empty. A validly
    # signed id_token from ANY Kakao app must be REJECTED (OAuthProviderUnavailable),
    # never accepted via PyJWT's audience=None aud-validation skip (account takeover).
    monkeypatch.setattr("app.config.settings.KAKAO_REST_API_KEY", "")
    monkeypatch.setattr("app.config.settings.KAKAO_NATIVE_APP_KEY", "")
    priv, _ = kakao_signing_key
    token = make_kakao_id_token(sub="12345", key=priv)
    with pytest.raises(OAuthProviderUnavailable):
        await verify_id_token(token)
