"""
End-to-end smoke test: hits the real FastAPI app (through TestClient) with
a real SQLite database, exercising the full chain — API -> application ->
persistence -> argon2 hashing — without needing a live Postgres connection.

This is deliberately the ONE place SQLite is used for anything beyond a
one-off sanity check: the app itself always targets Postgres per
project-brief.md; this test just swaps the engine so it's fast and doesn't
require a real database to run `pytest`.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.infrastructure.database import Base, get_db


@pytest.fixture()
def client():
    # In-memory SQLite, shared across the one connection in the pool, so
    # every request in this test sees the same tables/data.
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
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_then_login(client):
    register_response = client.post(
        "/auth/register",
        json={"email": "Athlete@Example.com", "password": "correct-horse-battery"},
    )
    assert register_response.status_code == 201
    body = register_response.json()
    # Domain rule (Athlete.__post_init__) normalizes email to lowercase.
    assert body["email"] == "athlete@example.com"
    assert "password_hash" not in body  # never leaks over the API

    login_response = client.post(
        "/auth/login",
        json={"email": "athlete@example.com", "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["email"] == "athlete@example.com"


def test_login_with_wrong_password_fails(client):
    client.post(
        "/auth/register",
        json={"email": "athlete2@example.com", "password": "correct-horse-battery"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "athlete2@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_duplicate_registration_fails(client):
    payload = {"email": "athlete3@example.com", "password": "correct-horse-battery"}
    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409
