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


@pytest.fixture()
def athlete_id(client):
    response = client.post(
        "/auth/register",
        json={"email": "lifter@example.com", "password": "correct-horse-battery"},
    )
    return response.json()["id"]


@pytest.fixture()
def exercise_ids(client):
    exercises = {e["name"]: e["id"] for e in client.get("/exercises").json()}
    return exercises


def test_build_full_mesocycle_and_add_prescription(client, athlete_id, exercise_ids):
    program = client.post(
        "/programs",
        json={"athlete_id": athlete_id, "name": "Hypertrophy Block", "description": ""},
    ).json()

    mesocycle = client.post(
        f"/programs/{program['id']}/mesocycles",
        json={
            "name": "Block 1",
            "weeks": [
                {"week_number": 1, "is_deload": False},
                {"week_number": 2, "is_deload": False},
                {"week_number": 3, "is_deload": False},
                {"week_number": 4, "is_deload": True},
            ],
            "workout_templates": [
                {
                    "name": "Push A",
                    "order_in_split": 1,
                    "exercise_ids": [
                        exercise_ids["Barbell Bench Press"],
                        exercise_ids["Cable Triceps Overhead Extension"],
                    ],
                },
                {
                    "name": "Pull A",
                    "order_in_split": 2,
                    "exercise_ids": [exercise_ids["Lat Pulldown"]],
                },
            ],
        },
    ).json()

    assert len(mesocycle["weeks"]) == 4
    assert mesocycle["weeks"][3]["is_deload"] is True
    push_a = next(t for t in mesocycle["workout_templates"] if t["name"] == "Push A")
    assert [e["exercise_name"] for e in push_a["exercises"]] == [
        "Barbell Bench Press", "Cable Triceps Overhead Extension",
    ]

    week_1_id = mesocycle["weeks"][0]["id"]
    bench_slot_id = push_a["exercises"][0]["id"]

    prescription = client.post(
        f"/template-exercises/{bench_slot_id}/prescriptions",
        json={
            "week_id": week_1_id,
            "notes": "First week — establish baseline",
            "sets": [
                {"set_type": "straight_set", "tempo": "normal",
                 "rep_range_min": 8, "rep_range_max": 10, "target_rir": 2.0},
                {"set_type": "straight_set", "tempo": "normal",
                 "rep_range_min": 8, "rep_range_max": 10, "target_rir": 2.0},
                {"set_type": "drop_set", "tempo": "normal",
                 "rep_range_min": 6, "rep_range_max": 10, "target_rir": 0.0},
            ],
        },
    ).json()

    assert len(prescription["sets"]) == 3
    assert prescription["sets"][2]["set_type"] == "drop_set"

    week_prescriptions = client.get(f"/weeks/{week_1_id}/prescriptions").json()
    assert len(week_prescriptions) == 1
    assert week_prescriptions[0]["template_exercise_id"] == bench_slot_id


def test_get_nonexistent_mesocycle_returns_404(client):
    response = client.get("/mesocycles/99999")
    assert response.status_code == 404
