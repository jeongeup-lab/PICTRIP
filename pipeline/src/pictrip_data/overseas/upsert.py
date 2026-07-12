from pictrip_data.overseas.commons import Credit, source_url, thumb_url
from pictrip_data.overseas.wikidata import RawSpot

_SQL = """
INSERT INTO overseas_spots (
    wikidata_id, name_ko, name_en, country_code, country_name_ko, description_ko,
    image_url, image_author, image_license, image_license_url, image_source_url,
    fame_score, lat, lng, updated_at
) VALUES (
    %(wikidata_id)s, %(name_ko)s, %(name_en)s, %(country_code)s, %(country_name_ko)s,
    %(description_ko)s, %(image_url)s, %(image_author)s, %(image_license)s,
    %(image_license_url)s, %(image_source_url)s, %(fame_score)s, %(lat)s, %(lng)s, now()
)
ON CONFLICT (wikidata_id) DO UPDATE SET
    name_ko = EXCLUDED.name_ko, name_en = EXCLUDED.name_en,
    country_code = EXCLUDED.country_code, country_name_ko = EXCLUDED.country_name_ko,
    description_ko = EXCLUDED.description_ko,
    embedding = CASE WHEN overseas_spots.image_url IS DISTINCT FROM EXCLUDED.image_url
                     THEN NULL ELSE overseas_spots.embedding END,
    image_url = EXCLUDED.image_url, image_author = EXCLUDED.image_author,
    image_license = EXCLUDED.image_license, image_license_url = EXCLUDED.image_license_url,
    image_source_url = EXCLUDED.image_source_url,
    fame_score = EXCLUDED.fame_score, lat = EXCLUDED.lat, lng = EXCLUDED.lng,
    updated_at = now()
RETURNING (xmax = 0) AS inserted
"""


def upsert_overseas(cur, spot: RawSpot, credit: Credit | None) -> bool:
    cur.execute(_SQL, {
        "wikidata_id": spot.wikidata_id, "name_ko": spot.name_ko, "name_en": spot.name_en,
        "country_code": spot.country.code, "country_name_ko": spot.country.name_ko,
        "description_ko": spot.description_ko,
        "image_url": thumb_url(spot.image_filename),
        "image_author": credit.author if credit else None,
        "image_license": credit.license if credit else None,
        "image_license_url": credit.license_url if credit else None,
        "image_source_url": source_url(spot.image_filename),
        "fame_score": spot.fame_score, "lat": spot.lat, "lng": spot.lng,
    })
    return bool(cur.fetchone()[0])
