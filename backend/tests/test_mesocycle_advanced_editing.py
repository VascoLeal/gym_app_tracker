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


def _create_and_start(client, athlete_id, exercise_ids, weeks=4, deload_strategy="none"):
    created = client.post(
        "/mesocycles",
        json={
            "athlete_id": athlete_id, "name": "Block 1", "number_of_weeks": weeks,
            "deload_strategy": deload_strategy,
            "workout_templates": [{
                "name": "Push A", "order_in_split": 1,
                "exercise_ids": [exercise_ids["Barbell Bench Press"]],
            }],
        },
    ).json()
    return client.post(f"/mesocycles/{created['id']}/start").json()


def _run_session(client, mesocycle_id):
    session = client.post(f"/mesocycles/{mesocycle_id}/sessions/start").json()
    performed_exercise_id = session["performed_exercises"][0]["id"]
    client.post(
        f"/performed-exercises/{performed_exercise_id}/sets",
        json={"actual_weight": 60.0, "actual_reps": 9, "actual_rpe": 8.0},
    )
    return client.post(f"/workout-sessions/{session['id']}/complete").json()


# --- edit_mesocycle ---


def test_rename_mesocycle_works_even_after_started(client, athlete_id, exercise_ids):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids)
    _run_session(client, mesocycle["id"])

    response = client.patch(f"/mesocycles/{mesocycle['id']}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_edit_number_of_weeks_before_any_session_regenerates_target_rpes(
    client, athlete_id, exercise_ids
):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids, weeks=4)

    response = client.patch(f"/mesocycles/{mesocycle['id']}", json={"number_of_weeks": 6})
    assert response.status_code == 200
    body = response.json()
    assert len(body["weeks"]) == 6
    assert [w["is_deload"] for w in body["weeks"]] == [False] * 6  # still "none" strategy


def test_edit_number_of_weeks_after_a_session_is_blocked(client, athlete_id, exercise_ids):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids, weeks=4)
    _run_session(client, mesocycle["id"])

    response = client.patch(f"/mesocycles/{mesocycle['id']}", json={"number_of_weeks": 6})
    assert response.status_code == 409


# --- workout template CRUD ---


def test_add_edit_reorder_and_remove_workout_template(client, athlete_id, exercise_ids):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids)

    added = client.post(
        f"/mesocycles/{mesocycle['id']}/workout-templates",
        json={"name": "Pull A", "order_in_split": 2,
              "exercise_ids": [exercise_ids["Lat Pulldown"]]},
    ).json()
    assert added["name"] == "Pull A"

    renamed = client.patch(
        f"/workout-templates/{added['id']}", json={"name": "Pull B"}
    ).json()
    assert renamed["name"] == "Pull B"

    reordered = client.patch(
        f"/workout-templates/{added['id']}/order", json={"new_position": 1}
    ).json()
    assert reordered[0]["name"] == "Pull B"

    remove_response = client.delete(f"/workout-templates/{added['id']}")
    assert remove_response.status_code == 204
    final = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert len(final["workout_templates"]) == 1


def test_cannot_add_workout_template_after_mesocycle_started(
    client, athlete_id, exercise_ids
):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids)
    _run_session(client, mesocycle["id"])

    response = client.post(
        f"/mesocycles/{mesocycle['id']}/workout-templates",
        json={"name": "Pull A", "order_in_split": 2,
              "exercise_ids": [exercise_ids["Lat Pulldown"]]},
    )
    assert response.status_code == 409


def test_rename_workout_template_still_works_after_started(client, athlete_id, exercise_ids):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids)
    _run_session(client, mesocycle["id"])
    template_id = mesocycle["workout_templates"][0]["id"]

    response = client.patch(f"/workout-templates/{template_id}", json={"name": "Renamed"})
    assert response.status_code == 200


# --- locked mesocycle (completed/abandoned) ---


def test_completed_mesocycle_blocks_all_mutations(client, athlete_id, exercise_ids):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids, weeks=4)
    for _ in range(4):
        completed = _run_session(client, mesocycle["id"])
    assert completed["status"] == "completed"

    assert client.patch(
        f"/mesocycles/{mesocycle['id']}", json={"name": "Nope"}
    ).status_code == 409
    assert client.patch(
        f"/workout-templates/{mesocycle['workout_templates'][0]['id']}",
        json={"name": "Nope"},
    ).status_code == 409


def test_abandoned_mesocycle_blocks_mutations_too(client, athlete_id, exercise_ids):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids)
    client.post(f"/mesocycles/{mesocycle['id']}/stop", json={"keep_as_history": True})

    response = client.patch(f"/mesocycles/{mesocycle['id']}", json={"name": "Nope"})
    assert response.status_code == 409


# --- week-already-trained guard ---


def test_editing_prescription_for_untrained_future_week_still_works(
    client, athlete_id, exercise_ids
):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids, weeks=4)
    slot = mesocycle["workout_templates"][0]["exercises"][0]
    week_2 = mesocycle["weeks"][1]

    prescription = client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={"week_id": week_2["id"], "notes": "",
              "sets": [{"set_type": "straight_set", "tempo": "normal",
                        "rep_range_min": 8, "rep_range_max": 10}]},
    ).json()

    edited = client.patch(
        f"/exercise-prescriptions/{prescription['id']}", json={"notes": "updated plan"}
    )
    assert edited.status_code == 200
    assert edited.json()["notes"] == "updated plan"


def test_editing_prescription_for_already_trained_week_is_blocked(
    client, athlete_id, exercise_ids
):
    mesocycle = _create_and_start(client, athlete_id, exercise_ids, weeks=4)
    slot = mesocycle["workout_templates"][0]["exercises"][0]
    week_1 = mesocycle["weeks"][0]

    prescription = client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={"week_id": week_1["id"], "notes": "",
              "sets": [{"set_type": "straight_set", "tempo": "normal",
                        "rep_range_min": 8, "rep_range_max": 10}]},
    ).json()

    _run_session(client, mesocycle["id"])  # trains week 1

    edited = client.patch(
        f"/exercise-prescriptions/{prescription['id']}", json={"notes": "too late"}
    )
    assert edited.status_code == 409

    remove_response = client.delete(f"/exercise-prescriptions/{prescription['id']}")
    assert remove_response.status_code == 409

    set_id = prescription["sets"][0]["id"]
    assert client.patch(
        f"/set-prescriptions/{set_id}", json={"rep_range_min": 5}
    ).status_code == 409
    assert client.delete(f"/set-prescriptions/{set_id}").status_code == 409
