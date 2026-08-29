"""
Idempotent seed data. Safe to run repeatedly — checks for existing rows
before inserting.

Still a SMALL, illustrative set of exercises to prove the schema works,
not the real exercise library content. The two "extension" exercises
(incline bench, triceps overhead extension) are included specifically to
demonstrate the muscle contribution-weighting the schema now supports.
"""

from sqlalchemy.orm import Session

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

MUSCLES = [
    ("Upper Chest", "Chest"),
    ("Mid Chest", "Chest"),
    ("Lower Chest", "Chest"),
    ("Front Delts", "Shoulders"),
    ("Lateral Delts", "Shoulders"),
    ("Rear Delts", "Shoulders"),
    ("Lats", "Back"),
    ("Traps", "Back"),
    ("Biceps Long Head", "Arms"),
    ("Biceps Short Head", "Arms"),
    ("Triceps Long Head", "Arms"),
    ("Triceps Lateral Head", "Arms"),
    ("Triceps Medial Head", "Arms"),
    ("Quads", "Legs"),
    ("Hamstrings", "Legs"),
    ("Glutes", "Legs"),
    ("Calves", "Legs"),
    ("Abs", "Core"),
    ("Full Body", "Full Body"),
    ("Other", "Other"),
]

EQUIPMENT = [
    "Barbell", "Dumbbell", "Cable Machine", "Machine", "Bodyweight",
    "Band", "Bosu", "Kettlebell", "Plate", "Sled", "Other",
]

SET_TYPES = [
    "warmup_set", "straight_set", "super_set", "circuit_set",
    "drop_set", "pyramid_set", "myo_rep_set",
]

TEMPOS = ["normal", "slow", "explosive", "paused"]

MOVEMENT_CATEGORIES = [
    "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
    "squat_knee_dominant", "squat_hip_dominant", "hip_extension",
    "knee_flexion", "other",
]

EXERCISE_TYPES = ["compound", "isolation"]

# (name, equipment, movement_category, exercise_type, warmup_suitable,
#  [(muscle, contribution), ...], [set_type, ...], [tempo, ...])
EXERCISES = [
    (
        "Barbell Bench Press", "Barbell", "horizontal_push", "compound", False,
        [("Mid Chest", 1.0), ("Front Delts", 0.4),
         ("Triceps Lateral Head", 0.4), ("Triceps Medial Head", 0.3)],
        ["straight_set", "warmup_set", "drop_set"], ["normal", "paused"],
    ),
    (
        "Incline Barbell Bench Press", "Barbell", "horizontal_push", "compound", False,
        [("Upper Chest", 1.0), ("Mid Chest", 0.4),
         ("Front Delts", 0.5), ("Triceps Lateral Head", 0.3)],
        ["straight_set", "warmup_set", "drop_set"], ["normal", "paused"],
    ),
    (
        "Barbell Back Squat", "Barbell", "squat_knee_dominant", "compound", False,
        [("Quads", 1.0), ("Glutes", 0.5), ("Hamstrings", 0.3)],
        ["straight_set", "warmup_set"], ["normal", "paused"],
    ),
    (
        "Lat Pulldown", "Cable Machine", "vertical_pull", "compound", True,
        [("Lats", 1.0), ("Biceps Long Head", 0.4), ("Biceps Short Head", 0.4)],
        ["straight_set", "warmup_set", "drop_set", "myo_rep_set"], ["normal", "slow"],
    ),
    (
        "Dumbbell Bicep Curl", "Dumbbell", "other", "isolation", True,
        [("Biceps Short Head", 1.0), ("Biceps Long Head", 0.7)],
        ["straight_set", "drop_set", "myo_rep_set"], ["normal", "slow", "paused"],
    ),
    (
        "Cable Lateral Raise", "Cable Machine", "other", "isolation", True,
        [("Lateral Delts", 1.0)],
        ["straight_set", "myo_rep_set"], ["normal", "slow"],
    ),
    (
        "Cable Triceps Overhead Extension", "Cable Machine", "other", "isolation", True,
        [("Triceps Long Head", 1.0), ("Triceps Lateral Head", 0.4),
         ("Triceps Medial Head", 0.4)],
        ["straight_set", "drop_set", "myo_rep_set"], ["normal", "slow"],
    ),
]


def seed(db: Session) -> None:
    if db.query(MuscleModel).count() == 0:
        db.add_all(MuscleModel(name=n, muscle_group=g) for n, g in MUSCLES)

    if db.query(EquipmentModel).count() == 0:
        db.add_all(EquipmentModel(name=n) for n in EQUIPMENT)

    if db.query(SetTypeModel).count() == 0:
        db.add_all(SetTypeModel(name=n) for n in SET_TYPES)

    if db.query(TempoModel).count() == 0:
        db.add_all(TempoModel(name=n) for n in TEMPOS)

    if db.query(MovementCategoryModel).count() == 0:
        db.add_all(MovementCategoryModel(name=n) for n in MOVEMENT_CATEGORIES)

    if db.query(ExerciseTypeModel).count() == 0:
        db.add_all(ExerciseTypeModel(name=n) for n in EXERCISE_TYPES)

    db.commit()

    if db.query(ExerciseModel).count() > 0:
        return

    muscles_by_name = {m.name: m for m in db.query(MuscleModel).all()}
    equipment_by_name = {e.name: e for e in db.query(EquipmentModel).all()}
    set_types_by_name = {s.name: s for s in db.query(SetTypeModel).all()}
    tempos_by_name = {t.name: t for t in db.query(TempoModel).all()}
    categories_by_name = {c.name: c for c in db.query(MovementCategoryModel).all()}
    types_by_name = {t.name: t for t in db.query(ExerciseTypeModel).all()}

    for (
        name, equipment_name, category_name, type_name, warmup_suitable,
        muscle_contributions, set_type_names, tempo_names,
    ) in EXERCISES:
        exercise = ExerciseModel(
            name=name,
            equipment_id=equipment_by_name[equipment_name].id,
            movement_category_id=categories_by_name[category_name].id,
            exercise_type_id=types_by_name[type_name].id,
            is_warmup_suitable=warmup_suitable,
        )
        db.add(exercise)
        db.flush()

        for muscle_name, contribution in muscle_contributions:
            db.add(ExerciseMuscleModel(
                exercise_id=exercise.id,
                muscle_id=muscles_by_name[muscle_name].id,
                contribution=contribution,
            ))

        for set_type_name in set_type_names:
            db.add(ExerciseSetTypeModel(
                exercise_id=exercise.id,
                set_type_id=set_types_by_name[set_type_name].id,
            ))

        for tempo_name in tempo_names:
            db.add(ExerciseTempoModel(
                exercise_id=exercise.id,
                tempo_id=tempos_by_name[tempo_name].id,
            ))

    db.commit()
