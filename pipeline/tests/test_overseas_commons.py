from pictrip_data.overseas.commons import parse_credits

PAGES = {"pages": {"1": {"title": "File:A.jpg", "imageinfo": [{"extmetadata": {
    "Artist": {"value": "<a href='x'>Jane Doe</a>"},
    "LicenseShortName": {"value": "CC BY-SA 4.0"},
    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
}}]}, "2": {"title": "File:B.jpg"}}}


def test_parse_credits_strips_html_and_maps_by_filename():
    credits = parse_credits({"query": PAGES})
    assert credits["A.jpg"].author == "Jane Doe"
    assert credits["A.jpg"].license == "CC BY-SA 4.0"
    assert credits["A.jpg"].license_url.startswith("https://creativecommons")


def test_parse_credits_missing_imageinfo_skipped():
    credits = parse_credits({"query": PAGES})
    assert "B.jpg" not in credits
