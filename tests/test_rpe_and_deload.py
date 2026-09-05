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
    created = client.post(
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
    return client.post(f"/mesocycles/{created['id']}/start").json()


def test_rpe_ramp_four_weeks_no_deload_matches_author_example(client, athlete_id, exercise_ids):
    # Author's example: 4 weeks, no deload -> RPE 7, 8, 9, 10.
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none")
    target_rpes = [w["target_rpe"] for w in mesocycle["weeks"]]
    assert target_rpes == [7.0, 8.0, 9.0, 10.0]
    assert all(w["is_deload"] is False for w in mesocycle["weeks"])


def test_rpe_ramp_seven_weeks_rest_deload_matches_author_example(client, athlete_id, exercise_ids):
    # Author's example: 7 weeks, deload rest -> RPE 7,8,8,9,9,10, then rest.
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=7, deload_strategy="rest")
    target_rpes = [w["target_rpe"] for w in mesocycle["weeks"]]
    assert target_rpes == [7.0, 8.0, 8.0, 9.0, 9.0, 10.0, None]
    assert [w["is_deload"] for w in mesocycle["weeks"]] == [
        False, False, False, False, False, False, True,
    ]


def test_none_deload_strategy_needs_full_session_count(client, athlete_id, exercise_ids):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none")
    # 1 day/week, 4 weeks, no deload -> needs all 4 sessions, none skipped.
    for i in range(3):
        session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()
        client.post(f"/workout-sessions/{session['id']}/complete")
    still_active = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert still_active["status"] == "active"

    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()
    client.post(f"/workout-sessions/{session['id']}/complete")
    finished = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert finished["status"] == "completed"
    assert finished["sessions_completed"] == 4


def test_prescribed_set_shows_computed_target_rpe_not_manually_settable(
    client, athlete_id, exercise_ids
):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none")
    slot = mesocycle["workout_templates"][0]["exercises"][0]
    week_1 = mesocycle["weeks"][0]

    prescription = client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={
            "week_id": week_1["id"], "notes": "",
            "sets": [{"set_type": "straight_set", "tempo": "normal",
                      "rep_range_min": 8, "rep_range_max": 10}],
        },
    ).json()
    # No target_rpe was sent in the request — it's computed from the week.
    assert prescription["sets"][0]["target_rpe"] == 7.0


def test_logging_a_set_only_needs_weight_reps_rpe_plus_optional_notes(
    client, athlete_id, exercise_ids
):
    mesocycle = _create_mesocycle(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none")
    session = client.post(f"/mesocycles/{mesocycle['id']}/sessions/start").json()
    performed_exercise_id = session["performed_exercises"][0]["id"]

    response = client.post(
        f"/performed-exercises/{performed_exercise_id}/sets",
        json={"actual_weight": 100.0, "actual_reps": 8, "actual_rpe": 7.5,
              "notes": "felt easy, could've done more"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["actual_rpe"] == 7.5
    assert body["notes"] == "felt easy, could've done more"
    assert "set_type" not in body
    assert "tempo" not in body
