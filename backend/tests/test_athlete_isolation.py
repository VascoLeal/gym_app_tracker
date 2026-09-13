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


def _register_and_login(client, email):
    client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    return client.post(
        "/auth/login", json={"email": email, "password": "correct-horse-battery"}
    ).json()


@pytest.fixture()
def exercise_ids(client):
    return {e["name"]: e["id"] for e in client.get("/exercises").json()}


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _mesocycle_payload(exercise_ids, name="Athlete A's Block"):
    return {
        "name": name,
        "number_of_weeks": 4,
        "deload_strategy": "none",
        "workout_templates": [{
            "name": "Push A", "order_in_split": 1,
            "exercise_ids": [exercise_ids["Barbell Bench Press"]],
        }],
    }


@pytest.fixture()
def two_athletes(client):
    athlete_a = _register_and_login(client, "athlete-a@example.com")
    athlete_b = _register_and_login(client, "athlete-b@example.com")
    return athlete_a, athlete_b


def test_athlete_a_mesocycle_is_invisible_to_athlete_b(client, exercise_ids, two_athletes):
    athlete_a, athlete_b = two_athletes

    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(exercise_ids),
        headers=_auth_headers(athlete_a["access_token"]),
    ).json()

    # Athlete B trying to fetch it directly gets 404, not 403 — it should
    # be indistinguishable from a mesocycle that doesn't exist at all.
    response = client.get(
        f"/mesocycles/{mesocycle['id']}", headers=_auth_headers(athlete_b["access_token"])
    )
    assert response.status_code == 404

    # And it doesn't show up in B's own list.
    b_list = client.get("/me/mesocycles", headers=_auth_headers(athlete_b["access_token"])).json()
    assert b_list == []

    # But A can still see it fine.
    a_view = client.get(
        f"/mesocycles/{mesocycle['id']}", headers=_auth_headers(athlete_a["access_token"])
    )
    assert a_view.status_code == 200


def test_athlete_b_cannot_start_or_edit_athlete_as_mesocycle(client, exercise_ids, two_athletes):
    athlete_a, athlete_b = two_athletes
    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(exercise_ids),
        headers=_auth_headers(athlete_a["access_token"]),
    ).json()

    b_headers = _auth_headers(athlete_b["access_token"])
    assert client.post(f"/mesocycles/{mesocycle['id']}/start", headers=b_headers).status_code == 404
    assert client.patch(
        f"/mesocycles/{mesocycle['id']}", json={"name": "Hijacked"}, headers=b_headers
    ).status_code == 404
    assert client.delete(f"/mesocycles/{mesocycle['id']}", headers=b_headers).status_code == 404
    assert client.post(
        f"/mesocycles/{mesocycle['id']}/copy", json={"new_name": "Stolen"}, headers=b_headers
    ).status_code == 404

    # A can still legitimately start their own mesocycle afterward.
    a_headers = _auth_headers(athlete_a["access_token"])
    assert client.post(f"/mesocycles/{mesocycle['id']}/start", headers=a_headers).status_code == 200


def test_athlete_b_cannot_touch_athlete_as_workout_templates_or_exercises(
    client, exercise_ids, two_athletes
):
    athlete_a, athlete_b = two_athletes
    a_headers = _auth_headers(athlete_a["access_token"])
    b_headers = _auth_headers(athlete_b["access_token"])

    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(exercise_ids), headers=a_headers
    ).json()
    template_id = mesocycle["workout_templates"][0]["id"]
    slot_id = mesocycle["workout_templates"][0]["exercises"][0]["id"]

    assert client.patch(
        f"/workout-templates/{template_id}", json={"name": "Hijacked"}, headers=b_headers
    ).status_code == 404
    assert client.post(
        f"/workout-templates/{template_id}/exercises",
        json={"exercise_id": exercise_ids["Lat Pulldown"]}, headers=b_headers,
    ).status_code == 404
    assert client.patch(
        f"/template-exercises/{slot_id}",
        json={"exercise_id": exercise_ids["Lat Pulldown"]}, headers=b_headers,
    ).status_code == 404
    assert client.delete(f"/template-exercises/{slot_id}", headers=b_headers).status_code == 404


def test_athlete_b_cannot_touch_athlete_as_prescriptions_or_sets(
    client, exercise_ids, two_athletes
):
    athlete_a, athlete_b = two_athletes
    a_headers = _auth_headers(athlete_a["access_token"])
    b_headers = _auth_headers(athlete_b["access_token"])

    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(exercise_ids), headers=a_headers
    ).json()
    slot = mesocycle["workout_templates"][0]["exercises"][0]
    week_1 = mesocycle["weeks"][0]

    prescription = client.post(
        f"/template-exercises/{slot['id']}/prescriptions",
        json={"week_id": week_1["id"], "notes": "",
              "sets": [{"set_type": "straight_set", "tempo": "normal",
                        "rep_range_min": 8, "rep_range_max": 10}]},
        headers=a_headers,
    ).json()

    assert client.patch(
        f"/exercise-prescriptions/{prescription['id']}", json={"notes": "hijacked"},
        headers=b_headers,
    ).status_code == 404
    assert client.delete(
        f"/exercise-prescriptions/{prescription['id']}", headers=b_headers
    ).status_code == 404

    set_id = prescription["sets"][0]["id"]
    assert client.patch(
        f"/set-prescriptions/{set_id}", json={"rep_range_min": 1}, headers=b_headers
    ).status_code == 404
    assert client.delete(f"/set-prescriptions/{set_id}", headers=b_headers).status_code == 404

    # And B can't even see A's prescriptions for that week.
    assert client.get(f"/weeks/{week_1['id']}/prescriptions", headers=b_headers).json() == []


def test_athlete_b_cannot_touch_athlete_as_workout_sessions(
    client, exercise_ids, two_athletes
):
    athlete_a, athlete_b = two_athletes
    a_headers = _auth_headers(athlete_a["access_token"])
    b_headers = _auth_headers(athlete_b["access_token"])

    mesocycle = client.post(
        "/mesocycles", json=_mesocycle_payload(exercise_ids), headers=a_headers
    ).json()
    client.post(f"/mesocycles/{mesocycle['id']}/start", headers=a_headers)

    # B can't start a session on A's mesocycle at all.
    assert client.post(
        f"/mesocycles/{mesocycle['id']}/sessions/start", headers=b_headers
    ).status_code == 404

    session = client.post(
        f"/mesocycles/{mesocycle['id']}/sessions/start", headers=a_headers
    ).json()
    performed_exercise_id = session["performed_exercises"][0]["id"]

    assert client.get(f"/workout-sessions/{session['id']}", headers=b_headers).status_code == 404
    assert client.post(
        f"/performed-exercises/{performed_exercise_id}/sets",
        json={"actual_weight": 100.0, "actual_reps": 10, "actual_rpe": 8.0},
        headers=b_headers,
    ).status_code == 404
    assert client.post(
        f"/workout-sessions/{session['id']}/complete", headers=b_headers
    ).status_code == 404
    assert client.post(
        f"/workout-sessions/{session['id']}/abandon", headers=b_headers
    ).status_code == 404

    # A can still legitimately complete their own session.
    real_log = client.post(
        f"/performed-exercises/{performed_exercise_id}/sets",
        json={"actual_weight": 100.0, "actual_reps": 10, "actual_rpe": 8.0},
        headers=a_headers,
    )
    assert real_log.status_code == 201
    assert client.post(
        f"/workout-sessions/{session['id']}/complete", headers=a_headers
    ).status_code == 200


def test_unauthenticated_requests_are_rejected(client, exercise_ids):
    response = client.post("/mesocycles", json=_mesocycle_payload(exercise_ids))
    assert response.status_code in (401, 403)
