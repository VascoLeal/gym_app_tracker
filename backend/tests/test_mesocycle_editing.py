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
    test_client = TestClient(app)
    test_client.session_factory = TestingSessionLocal
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def athlete_id(client):
    return client.post(
        "/auth/register",
        json={"email": "lifter@example.com", "password": "correct-horse-battery"},
    ).json()["id"]


@pytest.fixture()
def exercise_ids(client):
    return {e["name"]: e["id"] for e in client.get("/exercises").json()}


@pytest.fixture()
def mesocycle(client, athlete_id, exercise_ids):
    created = client.post(
        "/mesocycles",
        json={
            "athlete_id": athlete_id, "name": "Block 1", "number_of_weeks": 4,
            "deload_strategy": "none",
            "workout_templates": [{
                "name": "Push A", "order_in_split": 1,
                "exercise_ids": [
                    exercise_ids["Barbell Bench Press"],
                    exercise_ids["Cable Triceps Overhead Extension"],
                    exercise_ids["Cable Lateral Raise"],
                ],
            }],
        },
    ).json()
    return client.post(f"/mesocycles/{created['id']}/start").json()


def test_reorder_moves_exercise_and_shifts_others(client, mesocycle):
    exercises = mesocycle["workout_templates"][0]["exercises"]
    bench_id = next(e["id"] for e in exercises if e["exercise_name"] == "Barbell Bench Press")

    reordered = client.patch(
        f"/template-exercises/{bench_id}/order", json={"new_position": 3}
    ).json()

    assert [e["order_in_workout"] for e in reordered] == [1, 2, 3]
    assert reordered[2]["exercise_name"] == "Barbell Bench Press"
    assert reordered[0]["exercise_name"] == "Cable Triceps Overhead Extension"
    assert reordered[1]["exercise_name"] == "Cable Lateral Raise"


def test_reorder_position_beyond_range_clamps_to_end(client, mesocycle):
    exercises = mesocycle["workout_templates"][0]["exercises"]
    bench_id = next(e["id"] for e in exercises if e["exercise_name"] == "Barbell Bench Press")

    reordered = client.patch(
        f"/template-exercises/{bench_id}/order", json={"new_position": 99}
    ).json()
    assert reordered[-1]["exercise_name"] == "Barbell Bench Press"


def test_cannot_reorder_after_mesocycle_started(client, athlete_id, mesocycle, exercise_ids):
    exercises = mesocycle["workout_templates"][0]["exercises"]
    bench_id = next(e["id"] for e in exercises if e["exercise_name"] == "Barbell Bench Press")

    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()
    client.post(f"/workout-sessions/{session['id']}/complete")

    response = client.patch(
        f"/template-exercises/{bench_id}/order", json={"new_position": 1}
    )
    assert response.status_code == 409


def test_add_edit_and_remove_set_from_prescription(client, mesocycle):
    slot = mesocycle["workout_templates"][0]["exercises"][0]
    week_1 = mesocycle["weeks"][0]

    prescription = client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={
            "week_id": week_1["id"], "notes": "",
            "sets": [{"set_type": "straight_set", "tempo": "normal",
                      "rep_range_min": 8, "rep_range_max": 10, "target_weight": 60.0}],
        },
    ).json()
    assert len(prescription["sets"]) == 1

    added = client.post(
        f"/exercise-prescriptions/{prescription['id']}/sets",
        json={"set_type": "drop_set", "tempo": "normal",
              "rep_range_min": 6, "rep_range_max": 10, "target_weight": 50.0},
    ).json()
    assert added["set_number"] == 2
    assert added["set_type"] == "drop_set"

    edited = client.patch(
        f"/set-prescriptions/{added['id']}",
        json={"rep_range_min": 5, "target_weight": 45.0},
    ).json()
    assert edited["rep_range_min"] == 5
    assert edited["target_weight"] == 45.0
    assert edited["set_type"] == "drop_set"  # untouched fields stay as they were

    remove_response = client.delete(f"/set-prescriptions/{added['id']}")
    assert remove_response.status_code == 204

    week_prescriptions = client.get(f"/weeks/{week_1['id']}/prescriptions").json()
    assert len(week_prescriptions[0]["sets"]) == 1  # back to just the original set


def test_edit_set_can_explicitly_clear_target_weight(client, mesocycle):
    slot = mesocycle["workout_templates"][0]["exercises"][0]
    week_1 = mesocycle["weeks"][0]
    prescription = client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={
            "week_id": week_1["id"], "notes": "",
            "sets": [{"set_type": "straight_set", "tempo": "normal",
                      "rep_range_min": 8, "rep_range_max": 10, "target_weight": 60.0}],
        },
    ).json()
    set_id = prescription["sets"][0]["id"]

    cleared = client.patch(
        f"/set-prescriptions/{set_id}", json={"clear_target_weight": True}
    ).json()
    assert cleared["target_weight"] is None
