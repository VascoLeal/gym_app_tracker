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
    test_client.session_factory = TestingSessionLocal  # for tests needing raw DB access
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


def _mesocycle_payload(athlete_id, exercise_ids, weeks=4, name="Block 1"):
    return {
        "athlete_id": athlete_id,
        "name": name,
        "number_of_weeks": weeks,
        "deload_strategy": "reduced_load",
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
    }


def test_create_mesocycle_starts_as_draft_with_weeks_generated(
    client, athlete_id, exercise_ids
):
    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids, weeks=6)
    ).json()

    assert len(mesocycle["weeks"]) == 6
    assert [w["is_deload"] for w in mesocycle["weeks"]] == [
        False, False, False, False, False, True,
    ]
    assert mesocycle["status"] == "draft"
    assert mesocycle["sessions_completed"] == 0


def test_mesocycle_length_out_of_range_is_rejected(client, athlete_id, exercise_ids):
    payload = _mesocycle_payload(athlete_id, exercise_ids, weeks=20)
    response = client.post("/mesocycles", json=payload)
    assert response.status_code == 422


def test_can_create_multiple_drafts_while_one_is_active(client, athlete_id, exercise_ids):
    """The author's explicit ask: planning the next block while still
    training the current one shouldn't be blocked by anything."""
    first = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids, name="Block 1")
    ).json()
    client.post(f"/mesocycles/{first['id']}/start")

    # Creating more drafts is always allowed, active mesocycle notwithstanding.
    second = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids, name="Block 2")
    )
    third = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids, name="Block 3")
    )
    assert second.status_code == 201
    assert third.status_code == 201
    assert second.json()["status"] == "draft"
    assert third.json()["status"] == "draft"

    all_mesocycles = client.get(f"/athletes/{athlete_id}/mesocycles").json()
    assert len(all_mesocycles) == 3


def test_starting_a_second_draft_while_one_is_active_is_blocked(
    client, athlete_id, exercise_ids
):
    first = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids, name="Block 1")
    ).json()
    client.post(f"/mesocycles/{first['id']}/start")

    second = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids, name="Block 2")
    ).json()
    # Creating it succeeded (it's just a draft) — but STARTING it is what's gated.
    response = client.post(f"/mesocycles/{second['id']}/start")
    assert response.status_code == 409


def test_cannot_start_a_mesocycle_twice(client, athlete_id, exercise_ids):
    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids)
    ).json()
    client.post(f"/mesocycles/{mesocycle['id']}/start")

    response = client.post(f"/mesocycles/{mesocycle['id']}/start")
    assert response.status_code == 409


def test_stop_and_keep_as_history_then_start_new_one(client, athlete_id, exercise_ids):
    first = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids)
    ).json()
    client.post(f"/mesocycles/{first['id']}/start")

    stop_response = client.post(
        f"/mesocycles/{first['id']}/stop", json={"keep_as_history": True}
    )
    assert stop_response.status_code == 204

    # Now a new one can be created AND started.
    second = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids, name="Block 2")
    ).json()
    start_response = client.post(f"/mesocycles/{second['id']}/start")
    assert start_response.status_code == 200

    history = client.get(f"/athletes/{athlete_id}/mesocycles").json()
    assert len(history) == 2
    stopped = next(m for m in history if m["id"] == first["id"])
    assert stopped["status"] == "abandoned"


def test_stop_without_keeping_history_deletes_it(client, athlete_id, exercise_ids):
    first = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids)
    ).json()
    client.post(f"/mesocycles/{first['id']}/start")

    client.post(f"/mesocycles/{first['id']}/stop", json={"keep_as_history": False})

    assert client.get(f"/mesocycles/{first['id']}").status_code == 404
    history = client.get(f"/athletes/{athlete_id}/mesocycles").json()
    assert history == []


def test_copy_mesocycle_produces_a_draft_not_active(
    client, athlete_id, exercise_ids
):
    original = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids)
    ).json()
    client.post(f"/mesocycles/{original['id']}/start")

    copy = client.post(
        f"/mesocycles/{original['id']}/copy", json={"new_name": "Block 1 (repeat)"}
    ).json()

    assert copy["name"] == "Block 1 (repeat)"
    assert copy["status"] == "draft"  # NOT active — start it separately when ready
    assert len(copy["workout_templates"]) == len(original["workout_templates"])
    push_a = next(t for t in copy["workout_templates"] if t["name"] == "Push A")
    assert [e["exercise_name"] for e in push_a["exercises"]] == [
        "Barbell Bench Press", "Cable Triceps Overhead Extension",
    ]

    # Since the original is still active, starting the copy right away is blocked.
    assert client.post(f"/mesocycles/{copy['id']}/start").status_code == 409

    # But stopping the original frees it up.
    client.post(f"/mesocycles/{original['id']}/stop", json={"keep_as_history": True})
    assert client.post(f"/mesocycles/{copy['id']}/start").status_code == 200


def test_current_position_advances_by_completed_sessions_not_calendar(
    client, athlete_id, exercise_ids
):
    """This directly tests the session-count-based week derivation: with a
    2-day split, session 3 (0-indexed: 2) should land in week 2, on the
    2nd template — regardless of what calendar day that happens to be."""
    from app.infrastructure.mesocycle_models import MesocycleModel

    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(athlete_id, exercise_ids)
    ).json()
    mesocycle = client.post(f"/mesocycles/{mesocycle['id']}/start").json()

    # Simulate 3 completed sessions directly.
    db = client.session_factory()
    row = db.query(MesocycleModel).filter(MesocycleModel.id == mesocycle["id"]).first()
    row.sessions_completed = 3
    db.commit()
    db.close()

    updated = client.get(f"/mesocycles/{mesocycle['id']}").json()
    assert updated["current_week_number"] == 2
    # Sessions 0=Push A, 1=Pull A (week 1); 2=Push A (week 2, done);
    # next up is session 3 = Pull A.
    pull_a_id = next(
        t["id"] for t in updated["workout_templates"] if t["name"] == "Pull A"
    )
    assert updated["next_workout_template_id"] == pull_a_id
