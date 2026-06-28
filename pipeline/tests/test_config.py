from pictrip_data.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.kto_base_url_kor == "http://apis.data.go.kr/B551011/KorService2"
    assert s.kto_mobile_app == "PicTrip"


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("KTO_API_KEY", "decoded-key-123")
    s = Settings(_env_file=None)
    assert s.kto_api_key == "decoded-key-123"
