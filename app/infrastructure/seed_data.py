"""
Idempotent seed data. Safe to run repeatedly — checks for existing rows
before inserting.

Still a SMALL, illustrative set of exercises to prove the schema works,
not the real exercise library content.

Muscle taxonomy: muscle_group is one consistent, curated set of real
muscle groups (chest/back/shoulders/biceps/triceps/core/glutes/
quadriceps/hamstrings/calves/tibialis), plus full_body/other as
catch-alls for exercises that don't isolate anything specific. Every
group gets comparable internal granularity via the `name` column — no
group is left as a single flat entry while others get split into parts.
Tibialis is the one deliberate exception: it only gets one named part
(Tibialis Anterior) because that's genuinely the only commonly-trained
part, not because I forgot to split it.
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
from app.infrastructure.mesocycle_models import DeloadStrategyModel

MUSCLES = [
    ("Upper Chest", "chest"), ("Mid Chest", "chest"), ("Lower Chest", "chest"),
    ("Lats", "back"), ("Traps", "back"), ("Rhomboids", "back"),
    ("Front Delts", "shoulders"), ("Lateral Delts", "shoulders"),
    ("Rear Delts", "shoulders"), ("Rotator Cuff", "shoulders"),
    ("Biceps Long Head", "biceps"), ("Biceps Short Head", "biceps"),
    ("Triceps Long Head", "triceps"), ("Triceps Lateral Head", "triceps"),
    ("Triceps Medial Head", "triceps"),
    ("Upper Abs", "core"), ("Lower Abs", "core"), ("Obliques", "core"),
    ("Glute Max", "glutes"), ("Glute Med", "glutes"), ("Glute Min", "glutes"),
    ("Rectus Femoris", "quadriceps"), ("Vastus Lateralis", "quadriceps"),
    ("Vastus Medialis", "quadriceps"),
    ("Biceps Femoris", "hamstrings"), ("Semitendinosus", "hamstrings"),
    ("Semimembranosus", "hamstrings"),
    ("Gastrocnemius", "calves"), ("Soleus", "calves"),
    ("Tibialis Anterior", "tibialis"),
    ("Full Body", "full_body"),
    ("Other", "other"),
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

EXERCISE_TYPES = ["compound", "isolation", "warmup"]

DELOAD_STRATEGIES = ["rest", "reduced_load"]

# (name, equipment, movement_category, exercise_type,
#  [(muscle, contribution), ...], [set_type, ...], [tempo, ...])
EXERCISES = [
    (
        "Barbell Bench Press", "Barbell", "horizontal_push", "compound",
        [("Mid Chest", 1.0), ("Front Delts", 0.4),
         ("Triceps Lateral Head", 0.4), ("Triceps Medial Head", 0.3)],
        ["straight_set", "warmup_set", "drop_set"], ["normal", "paused"],
    ),
    (
        "Incline Barbell Bench Press", "Barbell", "horizontal_push", "compound",
        [("Upper Chest", 1.0), ("Mid Chest", 0.4),
         ("Front Delts", 0.5), ("Triceps Lateral Head", 0.3)],
        ["straight_set", "warmup_set", "drop_set"], ["normal", "paused"],
    ),
    (
        "Barbell Back Squat", "Barbell", "squat_knee_dominant", "compound",
        [("Rectus Femoris", 1.0), ("Vastus Lateralis", 0.9),
         ("Glute Max", 0.5), ("Biceps Femoris", 0.3)],
        ["straight_set", "warmup_set"], ["normal", "paused"],
    ),
    (
        "Lat Pulldown", "Cable Machine", "vertical_pull", "compound",
        [("Lats", 1.0), ("Biceps Long Head", 0.4), ("Biceps Short Head", 0.4)],
        ["straight_set", "warmup_set", "drop_set", "myo_rep_set"], ["normal", "slow"],
    ),
    (
        "Dumbbell Bicep Curl", "Dumbbell", "other", "isolation",
        [("Biceps Short Head", 1.0), ("Biceps Long Head", 0.7)],
        ["straight_set", "drop_set", "myo_rep_set"], ["normal", "slow", "paused"],
    ),
    (
        "Cable Lateral Raise", "Cable Machine", "other", "isolation",
        [("Lateral Delts", 1.0)],
        ["straight_set", "myo_rep_set"], ["normal", "slow"],
    ),
    (
        "Cable Triceps Overhead Extension", "Cable Machine", "other", "isolation",
        [("Triceps Long Head", 1.0), ("Triceps Lateral Head", 0.4),
         ("Triceps Medial Head", 0.4)],
        ["straight_set", "drop_set", "myo_rep_set"], ["normal", "slow"],
    ),
    (
        "Band External Rotation", "Band", "other", "warmup",
        [("Rotator Cuff", 1.0)],
        ["straight_set"], ["normal", "slow"],
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

    if db.query(DeloadStrategyModel).count() == 0:
        db.add_all(DeloadStrategyModel(name=n) for n in DELOAD_STRATEGIES)

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
        name, equipment_name, category_name, type_name,
        muscle_contributions, set_type_names, tempo_names,
    ) in EXERCISES:
        exercise = ExerciseModel(
            name=name,
            equipment_id=equipment_by_name[equipment_name].id,
            movement_category_id=categories_by_name[category_name].id,
            exercise_type_id=types_by_name[type_name].id,
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
