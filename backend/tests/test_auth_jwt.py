from app.core.auth import create_refresh_token, decode_token


def test_create_refresh_token_embeds_claims():
    # Denylist model: refresh tokens carry no `sid` (no session family).
    token = create_refresh_token(user_id=42, jti="jti-abc")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["jti"] == "jti-abc"
    assert payload["type"] == "refresh"
    assert "sid" not in payload
