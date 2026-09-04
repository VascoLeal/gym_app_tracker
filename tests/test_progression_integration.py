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


def _create_mesocycle(client, athlete_id, exercise_ids, weeks, deload_strategy):
    return client.post(
        "/mesocycles",
        json={
            "athlete_id": athlete_id,
            "name": "Block 1",
            "number_of_weeks": weeks,
            "deload_strategy": deload_strategy,
            "workout_templates": [{
                "name": "Push A", "order_in_split": 1,
                "exercise_ids": [exercise_ids["Barbell Bench Press"]],
            }],
        },
    ).json()


def _prescribe_week_1(client, mesocycle):
    slot = mesocycle["workout_templates"][0]["exercises"][0]
    week_1 = mesocycle["weeks"][0]
    client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={
            "week_id": week_1["id"], "notes": "",
            "sets": [{"set_type": "straight_set", "tempo": "normal",
                      "rep_range_min": 8, "rep_range_max": 10, "target_weight": 100.0}],
        },
    )
    return slot


def _run_session(client, mesocycle_id, actual_weight, actual_reps, actual_rpe):
    """Starts the next session, logs the given performance against every
    prescribed set for the day's exercise (correctly linked by
    set_prescription_id), and completes it. Returns the completed session."""
    session = client.post(f"/mesocycles/{mesocycle_id}/sessions/start").json()
    performed_exercise_id = session["performed_exercises"][0]["id"]
    for prescribed_set in session["performed_exercises"][0]["prescribed_sets"]:
        client.post(
            f"/performed-exercises/{performed_exercise_id}/sets",
            json={
                "set_prescription_id": prescribed_set["id"],
                "actual_weight": actual_weight,
                "actual_reps": actual_reps,
                "actual_rpe": actual_rpe,
            },
        )
    return client.post(f"/workout-sessions/{session['id']}/complete").json()


def test_hitting_top_of_range_auto_generates_increased_weight_for_next_week(
    client, athlete_id, exercise_ids
):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none")
    _prescribe_week_1(client, mesocycle)

    # Hit the top of the range (10 reps) at week 1's target RPE (7.0).
    _run_session(client, mesocycle["id"], actual_weight=100.0, actual_reps=10, actual_rpe=7.0)

    week_2_id = mesocycle["weeks"][1]["id"]
    prescriptions = client.get(f"/weeks/{week_2_id}/prescriptions").json()
    assert len(prescriptions) == 1
    assert "Auto-progressed" in prescriptions[0]["notes"]
    assert "increased load" in prescriptions[0]["notes"]
    assert prescriptions[0]["sets"][0]["target_weight"] == 105.0  # 100 * 1.05


def test_missing_reps_auto_generates_decreased_weight(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none")
    _prescribe_week_1(client, mesocycle)

    # Missed the bottom of the range (8).
    _run_session(client, mesocycle["id"], actual_weight=100.0, actual_reps=6, actual_rpe=9.5)

    week_2_id = mesocycle["weeks"][1]["id"]
    prescriptions = client.get(f"/weeks/{week_2_id}/prescriptions").json()
    assert "reduced load" in prescriptions[0]["notes"]
    assert prescriptions[0]["sets"][0]["target_weight"] == 95.0  # 100 * 0.95


def test_reduced_load_deload_week_gets_flat_fifty_percent_regardless_of_performance(
    client, athlete_id, exercise_ids
):
    # 4 weeks, reduced_load -> week 4 is the deload week.
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="reduced_load")
    _prescribe_week_1(client, mesocycle)

    # Week 1 (target_weight=100, manually set): crush it -> week 2 auto-set to 105.0 (100*1.05).
    _run_session(client, mesocycle["id"], actual_weight=100.0, actual_reps=10, actual_rpe=7.0)
    # Week 2 (target_weight=105.0): crush it -> week 3 auto-set to 110.0 (105*1.05=110.25, rounds to 110).
    _run_session(client, mesocycle["id"], actual_weight=105.0, actual_reps=10, actual_rpe=7.0)
    # Week 3 (target_weight=110.0, the last NORMAL week): crush it -> week 4 is the deload
    # week, so this should get a flat 50% cut (55.0), NOT another "increase".
    _run_session(client, mesocycle["id"], actual_weight=110.0, actual_reps=10, actual_rpe=7.0)

    week_4_id = mesocycle["weeks"][3]["id"]
    prescriptions = client.get(f"/weeks/{week_4_id}/prescriptions").json()
    assert len(prescriptions) == 1
    assert "deload week" in prescriptions[0]["notes"]
    assert prescriptions[0]["sets"][0]["target_weight"] == 55.0  # 110 * 0.5


def test_rest_deload_week_gets_no_generated_prescription(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="rest")
    _prescribe_week_1(client, mesocycle)

    completed = None
    for _ in range(3):  # 3 normal weeks required for a 4-week "rest" mesocycle
        completed = _run_session(client, mesocycle["id"], actual_weight=100.0, actual_reps=10, actual_rpe=7.0)

    assert completed["status"] == "completed"  # mesocycle finished, week 4 never needed
    week_4_id = mesocycle["weeks"][3]["id"]
    assert client.get(f"/weeks/{week_4_id}/prescriptions").json() == []


def test_exercise_swap_does_not_generate_a_recommendation(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none")
    _prescribe_week_1(client, mesocycle)

    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()
    performed_exercise_id = session["performed_exercises"][0]["id"]
    prescribed_set_id = session["performed_exercises"][0]["prescribed_sets"][0]["id"]

    from app.infrastructure.session_models import PerformedExerciseModel

    db = client.session_factory()
    row = db.query(PerformedExerciseModel).filter(
        PerformedExerciseModel.id == performed_exercise_id
    ).first()
    row.exercise_id = exercise_ids["Incline Barbell Bench Press"]  # swap
    db.commit()
    db.close()

    client.post(
        f"/performed-exercises/{performed_exercise_id}/sets",
        json={"set_prescription_id": prescribed_set_id,
              "actual_weight": 100.0, "actual_reps": 10, "actual_rpe": 7.0},
    )
    client.post(f"/workout-sessions/{session['id']}/complete")

    week_2_id = mesocycle["weeks"][1]["id"]
    assert client.get(f"/weeks/{week_2_id}/prescriptions").json() == []
