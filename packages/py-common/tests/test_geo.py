from alphaview_common.geo import describe, place_name

AUSTIN = {
    "label": "Austin, Texas, United States", "lat": 30.27, "lon": -97.74,
    "country_code": "US", "country": "United States", "region": "Texas", "city": "Austin",
}


def test_place_name_follows_radius():
    assert place_name({**AUSTIN, "radius_km": 25}) == "Austin"
    assert place_name({**AUSTIN, "radius_km": 300}) == "Texas"
    assert place_name({**AUSTIN, "radius_km": 1000}) == "United States"
    assert place_name(None) is None


def test_describe():
    assert describe(None) == "Global"
    assert describe({**AUSTIN, "radius_km": 50}) == "Austin, Texas, United States (within 50 km)"
