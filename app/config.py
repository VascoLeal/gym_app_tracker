"""
Application settings, loaded from environment variables (and a local .env
file during development). Nothing sensitive is ever hardcoded here — see
the constitution's security baseline.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Example: postgresql+psycopg://user:password@host/dbname
    database_url: str


@lru_cache
def get_settings() -> Settings:
    """
    Cached so we only parse the environment once per process, and so
    FastAPI's dependency injection (see api/routes/auth.py) can request
    settings cheaply wherever they're needed.
    """
    return Settings()
