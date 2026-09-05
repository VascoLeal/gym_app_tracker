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


def _create_mesocycle(client, athlete_id, exercise_ids, weeks, deload_strategy, name="Block 1"):
    created = client.post(
        "/mesocycles",
        json={
            "athlete_id": athlete_id,
            "name": name,
            "number_of_weeks": weeks,
            "deload_strategy": deload_strategy,
            "workout_templates": [
                {
                    "name": "Push A", "order_in_split": 1,
                    "exercise_ids": [exercise_ids["Barbell Bench Press"]],
                },
            ],
        },
    ).json()
    return client.post(f"/mesocycles/{created['id']}/start").json()


def _run_one_session(client, mesocycle_id):
    session = client.post(f"/mesocycles/{mesocycle_id}/sessions/start").json()
    performed_exercise_id = session["performed_exercises"][0]["id"]
    client.post(
        f"/performed-exercises/{performed_exercise_id}/sets",
        json={"actual_weight": 60.0, "actual_reps": 9, "actual_rpe": 8.0},
    )
    return client.post(f"/workout-sessions/{session['id']}/complete").json()


def test_mesocycle_auto_completes_with_reduced_load_deload(client, athlete_id, exercise_ids):
    # 1 day/week, 4 weeks, reduced_load -> deload week still trains -> 4 sessions total.
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="reduced_load")

    for _ in range(3):
        result = _run_one_session(client, mesocycle["id"])
        assert result is not None
    final_mesocycle = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert final_mesocycle["status"] == "active"  # 3 of 4 done

    _run_one_session(client, mesocycle["id"])
    final_mesocycle = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert final_mesocycle["status"] == "completed"
    assert final_mesocycle["sessions_completed"] == 4

    # A new mesocycle can be created AND started now — the completed one no longer blocks it.
    new_one = client.post(
        "/mesocycles",
        json={
            "athlete_id": athlete_id, "name": "Block 2", "number_of_weeks": 4,
            "deload_strategy": "rest",
            "workout_templates": [{
                "name": "Push A", "order_in_split": 1,
                "exercise_ids": [exercise_ids["Barbell Bench Press"]],
            }],
        },
    ).json()
    assert new_one["status"] == "draft"
    start_response = client.post(f"/mesocycles/{new_one['id']}/start")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "active"


def test_mesocycle_with_rest_deload_completes_without_a_deload_week_session(
    client, athlete_id, exercise_ids
):
    # 1 day/week, 4 weeks, rest -> deload week needs ZERO sessions -> 3 total.
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="rest")

    _run_one_session(client, mesocycle["id"])
    _run_one_session(client, mesocycle["id"])
    still_active = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert still_active["status"] == "active"

    completed = _run_one_session(client, mesocycle["id"])
    assert completed["status"] == "completed"
    final_mesocycle = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert final_mesocycle["status"] == "completed"
    assert final_mesocycle["sessions_completed"] == 3  # never trained week 4


def test_edit_template_exercise_before_starting(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="rest")
    slot_id = mesocycle["workout_templates"][0]["exercises"][0]["id"]

    response = client.patch(
        f"/template-exercises/{slot_id}",
        json={"exercise_id": exercise_ids["Incline Barbell Bench Press"]},
    )
    assert response.status_code == 200
    assert response.json()["exercise_name"] == "Incline Barbell Bench Press"


def test_cannot_edit_template_exercise_after_mesocycle_started(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="rest")
    slot_id = mesocycle["workout_templates"][0]["exercises"][0]["id"]

    _run_one_session(client, mesocycle["id"])

    response = client.patch(
        f"/template-exercises/{slot_id}",
        json={"exercise_id": exercise_ids["Incline Barbell Bench Press"]},
    )
    assert response.status_code == 409


def test_add_and_remove_template_exercise(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="rest")
    template_id = mesocycle["workout_templates"][0]["id"]

    added = client.post(
        f"/workout-templates/{template_id}/exercises",
        json={"exercise_id": exercise_ids["Cable Triceps Overhead Extension"]},
    ).json()
    assert added["order_in_workout"] == 2

    remove_response = client.delete(f"/template-exercises/{added['id']}")
    assert remove_response.status_code == 204


def test_delete_mesocycle_from_history_but_not_while_active(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="rest")

    still_active_delete = client.delete(f"/mesocycles/{mesocycle['id']}")
    assert still_active_delete.status_code == 409

    client.post(f"/mesocycles/{mesocycle['id']}/stop", json={"keep_as_history": True})
    delete_response = client.delete(f"/mesocycles/{mesocycle['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/mesocycles/{mesocycle['id']}").status_code == 404
