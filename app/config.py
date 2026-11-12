"""Central configuration. All secrets come from environment / .env, never from code."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    postgres_user: str = "amas"
    postgres_password: str = ""
    postgres_db: str = "amas_drm"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    graph_path: str = "data/guwahati_roads.graphml"
    frontend_origin: str = "http://localhost:5173"
    max_snap_m: float = 1000.0  # reject locations farther than this from any mapped road

    # Geocoding (OpenStreetMap Nominatim). Set GEOCODE_ONLINE=false to use only the built-in gazetteer.
    geocode_online: bool = True
    geocode_user_agent: str = "amas_drm_geocoder"
    geocode_timeout_s: float = 6.0
    geocode_cache_path: str = "data/geocode_cache.json"

    # Active hazard zones (flood / landslide polygons) are kept here so they survive a restart.
    hazards_path: str = "data/hazards.json"
    default_hazard_radius_m: float = 400.0

    # Rough bounding box of Guwahati; used to reject hallucinated coordinates.
    bbox_south: float = 26.05
    bbox_north: float = 26.25
    bbox_west: float = 91.55
    bbox_east: float = 91.95

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def in_bbox(self, lat: float, lon: float) -> bool:
        """True when BOTH coordinates fall inside the Guwahati bounding box."""
        return (
            self.bbox_south <= lat <= self.bbox_north
            and self.bbox_west <= lon <= self.bbox_east
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
