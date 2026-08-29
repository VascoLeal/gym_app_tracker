from sqlalchemy.orm import Session, selectinload

from app.domain.exercise import Exercise, MuscleContribution
from app.infrastructure.exercise_models import ExerciseModel


def _to_domain(row: ExerciseModel) -> Exercise:
    return Exercise(
        id=row.id,
        name=row.name,
        description=row.description,
        equipment_name=row.equipment.name,
        movement_category=row.movement_category.name,
        exercise_type=row.exercise_type.name,
        is_warmup_suitable=row.is_warmup_suitable,
        notes=row.notes,
        muscles=[
            MuscleContribution(
                muscle_name=link.muscle.name, contribution=link.contribution
            )
            for link in row.muscle_links
        ],
        supported_set_types=[link.set_type.name for link in row.set_type_links],
        supported_tempos=[link.tempo.name for link in row.tempo_links],
    )


def _base_query(db: Session):
    return db.query(ExerciseModel).options(
        selectinload(ExerciseModel.equipment),
        selectinload(ExerciseModel.movement_category),
        selectinload(ExerciseModel.exercise_type),
        selectinload(ExerciseModel.muscle_links),
        selectinload(ExerciseModel.set_type_links),
        selectinload(ExerciseModel.tempo_links),
    )


def list_exercises(db: Session) -> list[Exercise]:
    rows = _base_query(db).order_by(ExerciseModel.name).all()
    return [_to_domain(row) for row in rows]


def get_exercise(db: Session, exercise_id: int) -> Exercise | None:
    row = _base_query(db).filter(ExerciseModel.id == exercise_id).first()
    return _to_domain(row) if row else None
