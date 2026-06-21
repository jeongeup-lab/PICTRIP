from app.core.auth import create_refresh_token, decode_token


def test_create_refresh_token_embeds_sid_claim():
    token = create_refresh_token(user_id=42, jti="jti-abc", sid="sid-xyz")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["jti"] == "jti-abc"
    assert payload["sid"] == "sid-xyz"
    assert payload["type"] == "refresh"
