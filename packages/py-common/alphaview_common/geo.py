"""Search location shared by discovery, crawler and integrations. Passed between services as a plain dict."""

from typing import TypedDict

from pydantic import BaseModel, Field, field_validator

# Radius bands that decide which place name best describes the search area.
CITY_MAX_KM = 100
REGION_MAX_KM = 500
MAX_RADIUS_KM = 1000


class Geo(TypedDict, total=False):
    label: str
    lat: float
    lon: float
    radius_km: int
    country_code: str  # ISO 3166-1 alpha-2, upper case
    country: str
    region: str
    city: str


class GeoIn(BaseModel):
    """Validated location from API clients."""

    label: str = Field(min_length=1, max_length=300)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: int = Field(default=50, ge=1, le=MAX_RADIUS_KM)
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    country: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)

    @field_validator("country_code")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    def to_geo(self) -> Geo:
        return Geo(**self.model_dump(exclude_none=True))


def place_name(geo: Geo | None) -> str | None:
    """Most specific place name that still covers the radius (city -> region -> country)."""
    if not geo:
        return None
    radius = geo.get("radius_km", CITY_MAX_KM)
    if radius <= CITY_MAX_KM and geo.get("city"):
        return geo["city"]
    if radius <= REGION_MAX_KM and geo.get("region"):
        return geo["region"]
    return geo.get("country") or geo.get("region") or geo.get("city") or geo.get("label", "").split(",")[-1].strip() or None


def describe(geo: Geo | None) -> str:
    if not geo:
        return "Global"
    return f"{geo.get('label', 'Selected location')} (within {geo.get('radius_km', 0)} km)"
