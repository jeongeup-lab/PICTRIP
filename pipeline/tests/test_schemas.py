import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from pictrip_data.kto.schemas import KtoSpot, parse_modifiedtime

FIXTURE = Path(__file__).parent / "fixtures" / "sync_list_response.json"


def _items():
    return json.loads(FIXTURE.read_text())["response"]["body"]["items"]["item"]


def test_from_kto_maps_core_fields():
    spot = KtoSpot.from_kto(_items()[0])
    assert spot.content_id == "2865520"
    assert spot.content_type_id == 15
    assert spot.mapx == Decimal("128.3514221857")
    assert spot.first_image_url.startswith("http://tong.visitkorea")
    assert spot.cpyrht_div_cd == "Type3"


def test_signgu_code_is_composite():
    # lDongRegnCd 43 + lDongSignguCd 800 -> 43800 (단양군)
    assert KtoSpot.from_kto(_items()[0]).ldong_signgu_cd == "43800"
    assert KtoSpot.from_kto(_items()[1]).ldong_signgu_cd == "11110"


def test_showflag_to_int():
    assert KtoSpot.from_kto(_items()[0]).show_flag == 0
    assert KtoSpot.from_kto(_items()[1]).show_flag == 1


def test_blank_strings_become_none():
    spot = KtoSpot.from_kto(_items()[1])
    assert spot.addr2 is None


def test_parse_modifiedtime_kst():
    dt = parse_modifiedtime("20260627043000")
    assert dt == datetime(2026, 6, 27, 4, 30, 0, tzinfo=ZoneInfo("Asia/Seoul"))


def test_missing_signgu_part_yields_none():
    raw = dict(_items()[0])
    raw["lDongSignguCd"] = ""
    assert KtoSpot.from_kto(raw).ldong_signgu_cd is None
