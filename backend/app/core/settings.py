from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://allfind:allfind@localhost:5432/allfind"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    google_maps_api_key: str | None = None
    amadeus_client_id: str | None = None
    amadeus_client_secret: str | None = None
    travelpayouts_token: str | None = None

    proxy_url: str | None = None

    nearby_airports_radius_km: int = 200
    self_transfer_buffer_minutes: int = 180

    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
