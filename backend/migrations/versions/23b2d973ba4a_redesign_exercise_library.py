"""redesign exercise library: contribution weights, tempo, category/type tables

Revision ID: 23b2d973ba4a
Revises: 4e68959d9986
Create Date: 2026-08-28

Drops and recreates the exercise-library tables rather than altering them
in place. Safe here because only seed/demo data exists in these tables so
far — no real athlete-entered content to lose. Once that's no longer true,
schema changes here should switch to data-preserving ALTER migrations.
"""

from alembic import op
import sqlalchemy as sa

revision = "23b2d973ba4a"
down_revision = "4e68959d9986"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- drop, children first ---
    op.drop_table("exercise_set_types")
    op.drop_table("exercise_muscles")
    op.drop_table("exercises")
    op.drop_table("set_types")
    op.drop_table("equipment")
    op.drop_table("muscles")

    # --- recreate reference tables (muscles/equipment/set_types unchanged
    #     in shape; movement_categories/exercise_types/tempos are new) ---
    op.create_table(
        "muscles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("muscle_group", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "set_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "tempos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "movement_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "exercise_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )

    # --- exercises: no more rep_range columns; category/type are now FKs ---
    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "equipment_id", sa.Integer(), sa.ForeignKey("equipment.id"),
            nullable=False,
        ),
        sa.Column(
            "movement_category_id", sa.Integer(),
            sa.ForeignKey("movement_categories.id"), nullable=False,
        ),
        sa.Column(
            "exercise_type_id", sa.Integer(), sa.ForeignKey("exercise_types.id"),
            nullable=False,
        ),
        sa.Column(
            "is_warmup_suitable", sa.Boolean(), nullable=False,
            server_default="false",
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_exercises_name", "exercises", ["name"], unique=True)

    # --- exercise_muscles: contribution weight instead of role enum ---
    op.create_table(
        "exercise_muscles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"),
            nullable=False,
        ),
        sa.Column(
            "muscle_id", sa.Integer(), sa.ForeignKey("muscles.id"), nullable=False
        ),
        sa.Column("contribution", sa.Float(), nullable=False),
        sa.UniqueConstraint("exercise_id", "muscle_id"),
    )

    op.create_table(
        "exercise_set_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"),
            nullable=False,
        ),
        sa.Column(
            "set_type_id", sa.Integer(), sa.ForeignKey("set_types.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("exercise_id", "set_type_id"),
    )

    op.create_table(
        "exercise_tempos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"),
            nullable=False,
        ),
        sa.Column(
            "tempo_id", sa.Integer(), sa.ForeignKey("tempos.id"), nullable=False
        ),
        sa.UniqueConstraint("exercise_id", "tempo_id"),
    )


def downgrade() -> None:
    op.drop_table("exercise_tempos")
    op.drop_table("exercise_set_types")
    op.drop_table("exercise_muscles")
    op.drop_index("ix_exercises_name", table_name="exercises")
    op.drop_table("exercises")
    op.drop_table("exercise_types")
    op.drop_table("movement_categories")
    op.drop_table("tempos")
    op.drop_table("set_types")
    op.drop_table("equipment")
    op.drop_table("muscles")

    # Restore the previous (migration 4e68959d9986) shape.
    op.create_table(
        "muscles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("muscle_group", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "set_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "equipment_id", sa.Integer(), sa.ForeignKey("equipment.id"),
            nullable=False,
        ),
        sa.Column(
            "movement_category",
            sa.Enum(
                "push", "pull", "squat", "hinge", "lunge", "carry", "rotation",
                "other", name="movement_category", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "exercise_type",
            sa.Enum(
                "compound", "isolation", name="exercise_type",
                native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column("rep_range_min", sa.Integer(), nullable=False),
        sa.Column("rep_range_max", sa.Integer(), nullable=False),
        sa.Column(
            "is_warmup_suitable", sa.Boolean(), nullable=False,
            server_default="false",
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_exercises_name", "exercises", ["name"], unique=True)
    op.create_table(
        "exercise_muscles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"),
            nullable=False,
        ),
        sa.Column(
            "muscle_id", sa.Integer(), sa.ForeignKey("muscles.id"), nullable=False
        ),
        sa.Column(
            "role",
            sa.Enum(
                "primary", "secondary", name="muscle_role",
                native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.UniqueConstraint("exercise_id", "muscle_id"),
    )
    op.create_table(
        "exercise_set_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"),
            nullable=False,
        ),
        sa.Column(
            "set_type_id", sa.Integer(), sa.ForeignKey("set_types.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("exercise_id", "set_type_id"),
    )
