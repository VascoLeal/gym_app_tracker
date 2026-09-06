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
    response = client.post(
        "/auth/register",
        json={"email": "lifter@example.com", "password": "correct-horse-battery"},
    )
    return response.json()["id"]


@pytest.fixture()
def exercise_ids(client):
    return {e["name"]: e["id"] for e in client.get("/exercises").json()}


@pytest.fixture()
def mesocycle(client, athlete_id, exercise_ids):
    created = client.post(
        "/mesocycles",
        json={
            "athlete_id": athlete_id,
            "name": "Block 1",
            "number_of_weeks": 4,
            "deload_strategy": "reduced_load",
            "workout_templates": [
                {
                    "name": "Push A", "order_in_split": 1,
                    "exercise_ids": [exercise_ids["Barbell Bench Press"]],
                },
                {
                    "name": "Pull A", "order_in_split": 2,
                    "exercise_ids": [exercise_ids["Lat Pulldown"]],
                },
            ],
        },
    ).json()
    return client.post(f"/mesocycles/{created['id']}/start").json()


def _add_prescription(client, mesocycle, template_name, week_number):
    template = next(
        t for t in mesocycle["workout_templates"] if t["name"] == template_name
    )
    slot = template["exercises"][0]
    week = next(w for w in mesocycle["weeks"] if w["week_number"] == week_number)

    prescription = client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={
            "week_id": week["id"],
            "notes": "",
            "sets": [
                {"set_type": "straight_set", "tempo": "normal",
                 "rep_range_min": 8, "rep_range_max": 10},
                {"set_type": "straight_set", "tempo": "normal",
                 "rep_range_min": 8, "rep_range_max": 10},
            ],
        },
    ).json()
    return slot, prescription


def test_start_session_uses_current_position_and_prepopulates_slots(
    client, mesocycle
):
    slot, prescription = _add_prescription(client, mesocycle, "Push A", 1)

    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()

    assert session["status"] == "in_progress"
    assert session["workout_template_id"] == next(
        t["id"] for t in mesocycle["workout_templates"] if t["name"] == "Push A"
    )
    assert len(session["performed_exercises"]) == 1
    performed = session["performed_exercises"][0]
    assert performed["exercise_name"] == "Barbell Bench Press"
    # Prescribed sets show up immediately — that's the expected-vs-actual pairing.
    assert len(performed["prescribed_sets"]) == 2
    assert performed["performed_sets"] == []


def test_cannot_start_second_session_while_one_in_progress(client, mesocycle):
    _add_prescription(client, mesocycle, "Push A", 1)
    client.post(f"/mesocycles/{mesocycle['id']}/sessions/start")
    response = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start")
    assert response.status_code == 409


def test_log_sets_and_complete_advances_sessions_completed(client, mesocycle):
    _add_prescription(client, mesocycle, "Push A", 1)
    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()
    performed_exercise_id = session["performed_exercises"][0]["id"]
    prescribed = session["performed_exercises"][0]["prescribed_sets"]

    for p in prescribed:
        client.post(
            f"/performed-exercises/{performed_exercise_id}/sets",
            json={"actual_weight": 60.0, "actual_reps": 9, "actual_rpe": 8.5},
        )

    completed = client.post(f"/workout-sessions/{session['id']}/complete").json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None
    assert len(completed["performed_exercises"][0]["performed_sets"]) == 2

    updated_mesocycle = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert updated_mesocycle["sessions_completed"] == 1
    # 2-day split: after 1 session, still in week 1, next up is Pull A.
    assert updated_mesocycle["current_week_number"] == 1
    pull_a_id = next(
        t["id"] for t in updated_mesocycle["workout_templates"] if t["name"] == "Pull A"
    )
    assert updated_mesocycle["next_workout_template_id"] == pull_a_id


def test_abandon_session_does_not_advance_sessions_completed(client, mesocycle):
    _add_prescription(client, mesocycle, "Push A", 1)
    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()

    abandoned = client.post(f"/workout-sessions/{session['id']}/abandon").json()
    assert abandoned["status"] == "abandoned"

    updated_mesocycle = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert updated_mesocycle["sessions_completed"] == 0

    # A new session can now be started (the old one is no longer "in progress").
    retry = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start")
    assert retry.status_code == 201


def test_exercise_swap_is_allowed_at_the_data_level(client, mesocycle, exercise_ids):
    _add_prescription(client, mesocycle, "Push A", 1)
    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()
    performed_exercise_id = session["performed_exercises"][0]["id"]

    # Directly verify the schema allows a different exercise than planned —
    # no dedicated swap endpoint exists yet, but nothing prevents it at the
    # data level (per this milestone's scoping decision).
    from app.infrastructure.session_models import PerformedExerciseModel

    db = client.session_factory()
    row = db.query(PerformedExerciseModel).filter(
        PerformedExerciseModel.id == performed_exercise_id
    ).first()
    row.exercise_id = exercise_ids["Incline Barbell Bench Press"]
    db.commit()
    db.close()

    updated = client.get(f"/workout-sessions/{session['id']}").json()
    assert updated["performed_exercises"][0]["exercise_name"] == "Incline Barbell Bench Press"
