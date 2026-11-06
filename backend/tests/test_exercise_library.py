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
    assert "Band External Rotation" in names
    assert len(response.json()) == 8


def test_incline_bench_shows_contribution_weighting(client):
    all_exercises = client.get("/exercises").json()
    incline = next(
        e for e in all_exercises if e["name"] == "Incline Barbell Bench Press"
    )
    response = client.get(f"/exercises/{incline['id']}")
    body = response.json()

    assert "is_warmup_suitable" not in body  # deliberately removed
    assert "rep_range_min" not in body

    contributions = {m["muscle_name"]: m["contribution"] for m in body["muscles"]}
    assert contributions["Upper Chest"] == 1.0
    assert contributions["Mid Chest"] == 0.4


def test_warmup_exercise_type_and_rotator_cuff_muscle(client):
    all_exercises = client.get("/exercises").json()
    rotation = next(e for e in all_exercises if e["name"] == "Band External Rotation")

    assert rotation["exercise_type"] == "warmup"
    muscle_names = {m["muscle_name"] for m in rotation["muscles"]}
    assert "Rotator Cuff" in muscle_names


def test_bench_press_still_supports_warmup_sets_despite_no_warmup_flag(client):
    # This is the other half of is_warmup_suitable's old job: doing warmup
    # SETS of an exercise is expressed via supported_set_types, not a flag.
    all_exercises = client.get("/exercises").json()
    bench = next(e for e in all_exercises if e["name"] == "Barbell Bench Press")
    assert "warmup_set" in bench["supported_set_types"]
    assert bench["exercise_type"] == "compound"  # not "warmup" — different question


def test_get_nonexistent_exercise_returns_404(client):
    response = client.get("/exercises/99999")
    assert response.status_code == 404


@pytest.fixture()
def authed_client(client):
    client.post(
        "/auth/register",
        json={"email": "librarian@example.com", "password": "correct-horse-battery"},
    )
    login = client.post(
        "/auth/login",
        json={"email": "librarian@example.com", "password": "correct-horse-battery"},
    ).json()
    client.headers["Authorization"] = f"Bearer {login['access_token']}"
    return client


def _new_exercise_body(**overrides):
    body = {
        "name": "Cable Face Pull",
        "description": "",
        "equipment_name": "Cable Machine",
        "movement_category": "horizontal_pull",
        "exercise_type": "isolation",
        "notes": "",
        "muscles": [
            {"muscle_name": "Rear Delts", "contribution": 1.0},
            {"muscle_name": "Traps", "contribution": 0.3},
        ],
        "supported_set_types": ["straight_set", "warmup_set"],
        "supported_tempos": ["normal", "slow"],
    }
    body.update(overrides)
    return body


def test_create_exercise_requires_auth(client):
    response = client.post("/exercises", json=_new_exercise_body())
    assert response.status_code == 401


def test_create_exercise_persists_muscles_set_types_and_tempos(authed_client):
    response = authed_client.post("/exercises", json=_new_exercise_body())
    assert response.status_code == 201
    body = response.json()

    fetched = authed_client.get(f"/exercises/{body['id']}").json()
    contributions = {m["muscle_name"]: m["contribution"] for m in fetched["muscles"]}
    assert contributions == {"Rear Delts": 1.0, "Traps": 0.3}
    assert set(fetched["supported_set_types"]) == {"straight_set", "warmup_set"}
    assert set(fetched["supported_tempos"]) == {"normal", "slow"}


def test_create_exercise_rejects_duplicate_name(authed_client):
    authed_client.post("/exercises", json=_new_exercise_body())
    response = authed_client.post("/exercises", json=_new_exercise_body())
    assert response.status_code == 409


def test_create_exercise_rejects_unknown_muscle(authed_client):
    body = _new_exercise_body(
        muscles=[{"muscle_name": "Not A Real Muscle", "contribution": 1.0}]
    )
    response = authed_client.post("/exercises", json=body)
    assert response.status_code == 422


def test_edit_exercise_replaces_muscles_and_renames(authed_client):
    created = authed_client.post("/exercises", json=_new_exercise_body()).json()

    response = authed_client.patch(
        f"/exercises/{created['id']}",
        json=_new_exercise_body(
            name="Cable Face Pull (renamed)",
            muscles=[{"muscle_name": "Lateral Delts", "contribution": 0.6}],
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Cable Face Pull (renamed)"
    assert [m["muscle_name"] for m in body["muscles"]] == ["Lateral Delts"]


def test_edit_nonexistent_exercise_returns_404(authed_client):
    response = authed_client.patch("/exercises/99999", json=_new_exercise_body())
    assert response.status_code == 404


def test_edit_exercise_rejects_renaming_to_an_existing_name(authed_client):
    authed_client.post("/exercises", json=_new_exercise_body())
    other = authed_client.post(
        "/exercises", json=_new_exercise_body(name="Another Exercise")
    ).json()

    response = authed_client.patch(
        f"/exercises/{other['id']}", json=_new_exercise_body(name="Cable Face Pull")
    )
    assert response.status_code == 409
