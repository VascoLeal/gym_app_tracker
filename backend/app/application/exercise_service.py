from dataclasses import dataclass, field

from sqlalchemy.orm import Session, selectinload

from app.domain.exercise import Exercise, MuscleContribution
from app.infrastructure.exercise_models import (
    EquipmentModel,
    ExerciseModel,
    ExerciseMuscleModel,
    ExerciseSetTypeModel,
    ExerciseTempoModel,
    ExerciseTypeModel,
    MovementCategoryModel,
    MuscleModel,
    SetTypeModel,
    TempoModel,
)


class DuplicateExerciseName(Exception):
    pass


class ExerciseNotFound(Exception):
    pass


class UnknownReferenceValue(Exception):
    """A name that doesn't exist in one of the reference tables (equipment,
    movement category, exercise type, muscle, set type, tempo). Distinct
    from ExerciseNotFound — this is about a submitted value, not an id."""

    def __init__(self, kind: str, value: str):
        super().__init__(f"Unknown {kind}: '{value}'")


@dataclass
class MuscleContributionInput:
    muscle_name: str
    contribution: float


@dataclass
class ExerciseInput:
    name: str
    description: str
    equipment_name: str
    movement_category: str
    exercise_type: str
    notes: str
    muscles: list[MuscleContributionInput] = field(default_factory=list)
    supported_set_types: list[str] = field(default_factory=list)
    supported_tempos: list[str] = field(default_factory=list)


def _to_domain(row: ExerciseModel) -> Exercise:
    return Exercise(
        id=row.id,
        name=row.name,
        description=row.description,
        equipment_name=row.equipment.name,
        movement_category=row.movement_category.name,
        exercise_type=row.exercise_type.name,
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
        selectinload(ExerciseModel.muscle_links).selectinload(ExerciseMuscleModel.muscle),
        selectinload(ExerciseModel.set_type_links).selectinload(ExerciseSetTypeModel.set_type),
        selectinload(ExerciseModel.tempo_links).selectinload(ExerciseTempoModel.tempo),
    )


def list_exercises(db: Session) -> list[Exercise]:
    rows = _base_query(db).order_by(ExerciseModel.name).all()
    return [_to_domain(row) for row in rows]


def get_exercise(db: Session, exercise_id: int) -> Exercise | None:
    row = _base_query(db).filter(ExerciseModel.id == exercise_id).first()
    return _to_domain(row) if row else None


def _lookup_id(db: Session, model, name: str, kind: str) -> int:
    row = db.query(model).filter(model.name == name).first()
    if row is None:
        raise UnknownReferenceValue(kind, name)
    return row.id


def _sync_associations(db: Session, exercise_id: int, data: ExerciseInput) -> None:
    for muscle in data.muscles:
        muscle_id = _lookup_id(db, MuscleModel, muscle.muscle_name, "muscle")
        db.add(
            ExerciseMuscleModel(
                exercise_id=exercise_id, muscle_id=muscle_id, contribution=muscle.contribution
            )
        )
    for set_type_name in data.supported_set_types:
        set_type_id = _lookup_id(db, SetTypeModel, set_type_name, "set type")
        db.add(ExerciseSetTypeModel(exercise_id=exercise_id, set_type_id=set_type_id))
    for tempo_name in data.supported_tempos:
        tempo_id = _lookup_id(db, TempoModel, tempo_name, "tempo")
        db.add(ExerciseTempoModel(exercise_id=exercise_id, tempo_id=tempo_id))


def create_exercise(db: Session, data: ExerciseInput) -> Exercise:
    existing = db.query(ExerciseModel).filter(ExerciseModel.name == data.name).first()
    if existing is not None:
        raise DuplicateExerciseName(data.name)

    exercise = ExerciseModel(
        name=data.name,
        description=data.description,
        equipment_id=_lookup_id(db, EquipmentModel, data.equipment_name, "equipment"),
        movement_category_id=_lookup_id(
            db, MovementCategoryModel, data.movement_category, "movement category"
        ),
        exercise_type_id=_lookup_id(db, ExerciseTypeModel, data.exercise_type, "exercise type"),
        notes=data.notes,
    )
    db.add(exercise)
    db.flush()

    _sync_associations(db, exercise.id, data)

    db.commit()
    return get_exercise(db, exercise.id)  # type: ignore[return-value]


def edit_exercise(db: Session, exercise_id: int, data: ExerciseInput) -> Exercise:
    exercise = db.query(ExerciseModel).filter(ExerciseModel.id == exercise_id).first()
    if exercise is None:
        raise ExerciseNotFound(exercise_id)

    if data.name != exercise.name:
        duplicate = (
            db.query(ExerciseModel)
            .filter(ExerciseModel.name == data.name, ExerciseModel.id != exercise_id)
            .first()
        )
        if duplicate is not None:
            raise DuplicateExerciseName(data.name)

    exercise.name = data.name
    exercise.description = data.description
    exercise.equipment_id = _lookup_id(db, EquipmentModel, data.equipment_name, "equipment")
    exercise.movement_category_id = _lookup_id(
        db, MovementCategoryModel, data.movement_category, "movement category"
    )
    exercise.exercise_type_id = _lookup_id(db, ExerciseTypeModel, data.exercise_type, "exercise type")
    exercise.notes = data.notes

    # Full replace of the muscle/set-type/tempo associations rather than a
    # diff — the authoring form always submits the complete set, and these
    # tables are small enough that delete-and-recreate is simpler than
    # tracking individual adds/removes (contrast with prescriptions' sets,
    # which get edited piecemeal because they carry their own history).
    db.query(ExerciseMuscleModel).filter(ExerciseMuscleModel.exercise_id == exercise_id).delete()
    db.query(ExerciseSetTypeModel).filter(ExerciseSetTypeModel.exercise_id == exercise_id).delete()
    db.query(ExerciseTempoModel).filter(ExerciseTempoModel.exercise_id == exercise_id).delete()
    db.flush()

    _sync_associations(db, exercise_id, data)

    db.commit()
    return get_exercise(db, exercise_id)  # type: ignore[return-value]
