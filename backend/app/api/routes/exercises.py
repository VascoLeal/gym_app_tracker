from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_athlete
from app.api.schemas import (
    ExerciseCreateRequest,
    ExerciseEditRequest,
    ExerciseResponse,
    MuscleContributionResponse,
)
from app.application.exercise_service import (
    DuplicateExerciseName,
    ExerciseInput,
    ExerciseNotFound,
    MuscleContributionInput,
    UnknownReferenceValue,
    create_exercise,
    edit_exercise,
    get_exercise,
    list_exercises,
)
from app.domain.exercise import Exercise
from app.infrastructure.database import get_db
from app.infrastructure.models import AthleteModel

router = APIRouter(prefix="/exercises", tags=["exercises"])


def _to_input(body: ExerciseCreateRequest) -> ExerciseInput:
    return ExerciseInput(
        name=body.name,
        description=body.description,
        equipment_name=body.equipment_name,
        movement_category=body.movement_category,
        exercise_type=body.exercise_type,
        notes=body.notes,
        muscles=[
            MuscleContributionInput(muscle_name=m.muscle_name, contribution=m.contribution)
            for m in body.muscles
        ],
        supported_set_types=body.supported_set_types,
        supported_tempos=body.supported_tempos,
    )


def _to_response(exercise: Exercise) -> ExerciseResponse:
    return ExerciseResponse(
        id=exercise.id,
        name=exercise.name,
        description=exercise.description,
        equipment_name=exercise.equipment_name,
        movement_category=exercise.movement_category,
        exercise_type=exercise.exercise_type,
        notes=exercise.notes,
        muscles=[
            MuscleContributionResponse(
                muscle_name=m.muscle_name, contribution=m.contribution
            )
            for m in exercise.muscles
        ],
        supported_set_types=exercise.supported_set_types,
        supported_tempos=exercise.supported_tempos,
    )


@router.get("", response_model=list[ExerciseResponse])
def list_all(db: Session = Depends(get_db)) -> list[ExerciseResponse]:
    return [_to_response(e) for e in list_exercises(db)]


@router.get("/{exercise_id}", response_model=ExerciseResponse)
def get_one(exercise_id: int, db: Session = Depends(get_db)) -> ExerciseResponse:
    exercise = get_exercise(db, exercise_id)
    if exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found."
        )
    return _to_response(exercise)


@router.post("", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
def create_exercise_route(
    body: ExerciseCreateRequest,
    db: Session = Depends(get_db),
    current_athlete: AthleteModel = Depends(get_current_athlete),
) -> ExerciseResponse:
    # The library itself isn't athlete-owned (it's the shared Exercise
    # Library per docs/constitution.md §2) — current_athlete is required only to
    # prove the caller is a logged-in athlete, not to attribute ownership.
    del current_athlete
    try:
        exercise = create_exercise(db, _to_input(body))
    except DuplicateExerciseName as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An exercise named '{exc.args[0]}' already exists.",
        ) from exc
    except UnknownReferenceValue as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _to_response(exercise)


@router.patch("/{exercise_id}", response_model=ExerciseResponse)
def edit_exercise_route(
    exercise_id: int,
    body: ExerciseEditRequest,
    db: Session = Depends(get_db),
    current_athlete: AthleteModel = Depends(get_current_athlete),
) -> ExerciseResponse:
    del current_athlete
    try:
        exercise = edit_exercise(db, exercise_id, _to_input(body))
    except ExerciseNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found."
        ) from exc
    except DuplicateExerciseName as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An exercise named '{exc.args[0]}' already exists.",
        ) from exc
    except UnknownReferenceValue as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _to_response(exercise)
