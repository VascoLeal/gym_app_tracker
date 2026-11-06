"""Settings that only matter once the API is on the public internet: which
browser origins may call it, and who may create an account."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.config import Settings, get_settings
from app.infrastructure.database import Base, get_db


def make_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        jwt_secret_key="test-only",
        **overrides,
    )


def test_cors_origins_are_split_and_trimmed():
    settings = make_settings(
        cors_allowed_origins=" https://voacs.example/ , http://localhost:5173,"
    )
    assert settings.cors_origins == ["https://voacs.example", "http://localhost:5173"]


def test_anyone_can_register_when_no_allowlist_is_set():
    assert make_settings(registration_allowed_emails="").can_register("a@example.com")


def test_allowlist_ignores_case_and_spacing():
    settings = make_settings(registration_allowed_emails=" A@example.com , b@example.com")
    assert settings.can_register("a@EXAMPLE.com")
    assert settings.can_register(" b@example.com ")
    assert not settings.can_register("stranger@example.com")


def test_preflight_allows_only_configured_origins():
    client = TestClient(app)
    headers = {"Access-Control-Request-Method": "GET"}

    allowed_origin = get_settings().cors_origins[0]
    allowed = client.options("/health", headers={**headers, "Origin": allowed_origin})
    assert allowed.headers.get("access-control-allow-origin") == allowed_origin

    blocked = client.options(
        "/health", headers={**headers, "Origin": "https://stranger.example"}
    )
    assert "access-control-allow-origin" not in blocked.headers


@pytest.fixture()
def client_with_allowlist():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: make_settings(
        registration_allowed_emails="invited@example.com"
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_register_rejects_an_email_outside_the_allowlist(client_with_allowlist):
    response = client_with_allowlist.post(
        "/auth/register",
        json={"email": "stranger@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Registration is closed."


def test_register_accepts_an_allowlisted_email_and_it_can_log_in(client_with_allowlist):
    credentials = {"email": "Invited@example.com", "password": "correct-horse-battery"}
    assert client_with_allowlist.post("/auth/register", json=credentials).status_code == 201
    assert client_with_allowlist.post("/auth/login", json=credentials).status_code == 200
