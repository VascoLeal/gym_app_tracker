"""create exercise library tables

Revision ID: 4e68959d9986
Revises: 9447ccaf7e2c
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa

revision = "4e68959d9986"
down_revision = "9447ccaf7e2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
            "equipment_id",
            sa.Integer(),
            sa.ForeignKey("equipment.id"),
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
            "is_warmup_suitable", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_exercises_name", "exercises", ["name"], unique=True)

    op.create_table(
        "exercise_muscles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False
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
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False
        ),
        sa.Column(
            "set_type_id", sa.Integer(), sa.ForeignKey("set_types.id"), nullable=False
        ),
        sa.UniqueConstraint("exercise_id", "set_type_id"),
    )


def downgrade() -> None:
    op.drop_table("exercise_set_types")
    op.drop_table("exercise_muscles")
    op.drop_index("ix_exercises_name", table_name="exercises")
    op.drop_table("exercises")
    op.drop_table("set_types")
    op.drop_table("equipment")
    op.drop_table("muscles")
