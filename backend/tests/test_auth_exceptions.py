from app.core.exceptions import (
    AppError,
    AuthSessionRevoked,
    OAuthIdTokenInvalid,
    OAuthProviderUnavailable,
    SessionStoreUnavailable,
)


def test_oauth_provider_unavailable_maps_to_502():
    err = OAuthProviderUnavailable()
    assert isinstance(err, AppError)
    assert err.code == "OAUTH_PROVIDER_UNAVAILABLE"
    assert err.http_status == 502


def test_oauth_id_token_invalid_maps_to_401():
    err = OAuthIdTokenInvalid()
    assert err.code == "OAUTH_ID_TOKEN_INVALID"
    assert err.http_status == 401


def test_auth_session_revoked_maps_to_401():
    err = AuthSessionRevoked()
    assert err.code == "AUTH_SESSION_REVOKED"
    assert err.http_status == 401


def test_session_store_unavailable_maps_to_503():
    err = SessionStoreUnavailable()
    assert err.code == "SESSION_STORE_UNAVAILABLE"
    assert err.http_status == 503
