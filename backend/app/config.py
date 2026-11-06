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

    # Signs JWT access tokens (HS256 — symmetric, fine for a single backend).
    # Generate a real one with: python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret_key: str
    jwt_expiry_days: int = 30

    # Browsers only let these exact origins (scheme + host + port) call the
    # API. Comma-separated, because env vars are plain strings. Production
    # sets its deployed frontend's URL; the default suits local Vite.
    cors_allowed_origins: str = "http://localhost:5173"

    # Comma-separated emails allowed to register. The deployed API is on the
    # public internet and the exercise library is shared, so production names
    # its users here. Empty means anyone may register, for local development.
    registration_allowed_emails: str = ""

    @property
    def cors_origins(self) -> list[str]:
        # A trailing slash is an easy paste mistake, and an origin containing
        # one never matches what a browser sends.
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    def can_register(self, email: str) -> bool:
        allowed = {
            entry.strip().lower()
            for entry in self.registration_allowed_emails.split(",")
            if entry.strip()
        }
        return not allowed or email.strip().lower() in allowed


@lru_cache
def get_settings() -> Settings:
    """
    Cached so we only parse the environment once per process, and so
    FastAPI's dependency injection (see api/routes/auth.py) can request
    settings cheaply wherever they're needed.
    """
    return Settings()
