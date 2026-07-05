from pydantic import BaseModel, ConfigDict


class Location(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Provider's native place id, stringified, or a deterministic hash of
    # (name, admin1, country_code, latitude, longitude) if the provider
    # gives none — populated by the provider layer (Phase 6), not here.
    id: str
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None
    admin2: str | None = None
    population: int | None = None
    timezone: str | None = None
