from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import ExerciseResponse, MuscleContributionResponse
from app.application.exercise_service import get_exercise, list_exercises
from app.domain.exercise import Exercise
from app.infrastructure.database import get_db

router = APIRouter(prefix="/exercises", tags=["exercises"])


def _to_response(exercise: Exercise) -> ExerciseResponse:
    return ExerciseResponse(
        id=exercise.id,
        name=exercise.name,
        description=exercise.description,
        equipment_name=exercise.equipment_name,
        movement_category=exercise.movement_category,
        exercise_type=exercise.exercise_type,
        is_warmup_suitable=exercise.is_warmup_suitable,
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
