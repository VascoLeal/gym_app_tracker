import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.infrastructure.database import Base, get_db
from app.infrastructure.seed_data import seed


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = TestingSessionLocal()
    seed(db)
    db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_exercises_returns_seeded_data(client):
    response = client.get("/exercises")
    assert response.status_code == 200
    names = {e["name"] for e in response.json()}
    assert "Barbell Bench Press" in names
    assert len(response.json()) == 7


def test_incline_bench_shows_contribution_weighting(client):
    all_exercises = client.get("/exercises").json()
    incline = next(
        e for e in all_exercises if e["name"] == "Incline Barbell Bench Press"
    )

    response = client.get(f"/exercises/{incline['id']}")
    assert response.status_code == 200
    body = response.json()

    assert body["movement_category"] == "horizontal_push"
    assert body["exercise_type"] == "compound"
    assert "rep_range_min" not in body  # deliberately removed

    contributions = {m["muscle_name"]: m["contribution"] for m in body["muscles"]}
    # Upper chest is the priority target, mid chest a lesser one — exactly
    # the distinction a primary/secondary role couldn't express.
    assert contributions["Upper Chest"] == 1.0
    assert contributions["Mid Chest"] == 0.4

    assert "drop_set" in body["supported_set_types"]
    assert "paused" in body["supported_tempos"]


def test_triceps_overhead_extension_weights_long_head_highest(client):
    all_exercises = client.get("/exercises").json()
    extension = next(
        e for e in all_exercises if e["name"] == "Cable Triceps Overhead Extension"
    )
    contributions = {m["muscle_name"]: m["contribution"] for m in extension["muscles"]}
    assert contributions["Triceps Long Head"] == 1.0
    assert contributions["Triceps Lateral Head"] < contributions["Triceps Long Head"]
    assert contributions["Triceps Medial Head"] < contributions["Triceps Long Head"]


def test_get_nonexistent_exercise_returns_404(client):
    response = client.get("/exercises/99999")
    assert response.status_code == 404
