"""drop Program layer, add mesocycle lifecycle fields

Revision ID: 4cfac688f57d
Revises: 5e6f2e63d9f1
Create Date: 2026-08-29

Drops and recreates the whole planning hierarchy rather than an in-place
ALTER, same rationale as the earlier exercise-library migrations: only
seed/demo data existed here so far.

Mesocycle changes: no more program_id (mesocycles belong directly to the
athlete now); added number_of_weeks, deload_strategy_id, status,
sessions_completed. Week's is_deload is now always derived at creation
time (last week only) rather than caller-specified per week, but the
column itself is unchanged.
"""

from alembic import op
import sqlalchemy as sa

revision = "4cfac688f57d"
down_revision = "5e6f2e63d9f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the whole old hierarchy, children first.
    op.drop_table("set_prescriptions")
    op.drop_table("exercise_prescriptions")
    op.drop_table("template_exercises")
    op.drop_table("workout_templates")
    op.drop_table("weeks")
    op.drop_table("mesocycles")
    op.drop_table("programs")

    op.create_table(
        "deload_strategies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "mesocycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("number_of_weeks", sa.Integer(), nullable=False),
        sa.Column(
            "deload_strategy_id", sa.Integer(), sa.ForeignKey("deload_strategies.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("sessions_completed", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "weeks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mesocycle_id", sa.Integer(), sa.ForeignKey("mesocycles.id"), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("is_deload", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("mesocycle_id", "week_number"),
    )

    op.create_table(
        "workout_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mesocycle_id", sa.Integer(), sa.ForeignKey("mesocycles.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("order_in_split", sa.Integer(), nullable=False),
    )

    op.create_table(
        "template_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workout_template_id", sa.Integer(), sa.ForeignKey("workout_templates.id"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("order_in_workout", sa.Integer(), nullable=False),
    )

    op.create_table(
        "exercise_prescriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_exercise_id", sa.Integer(), sa.ForeignKey("template_exercises.id"), nullable=False),
        sa.Column("week_id", sa.Integer(), sa.ForeignKey("weeks.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("template_exercise_id", "week_id"),
    )

    op.create_table(
        "set_prescriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_prescription_id", sa.Integer(), sa.ForeignKey("exercise_prescriptions.id"), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("set_type_id", sa.Integer(), sa.ForeignKey("set_types.id"), nullable=False),
        sa.Column("tempo_id", sa.Integer(), sa.ForeignKey("tempos.id"), nullable=False),
        sa.Column("rep_range_min", sa.Integer(), nullable=False),
        sa.Column("rep_range_max", sa.Integer(), nullable=False),
        sa.Column("target_rir", sa.Float(), nullable=True),
        sa.UniqueConstraint("exercise_prescription_id", "set_number"),
    )


def downgrade() -> None:
    op.drop_table("set_prescriptions")
    op.drop_table("exercise_prescriptions")
    op.drop_table("template_exercises")
    op.drop_table("workout_templates")
    op.drop_table("weeks")
    op.drop_table("mesocycles")
    op.drop_table("deload_strategies")

    op.create_table(
        "programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "mesocycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
    )
    op.create_table(
        "weeks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mesocycle_id", sa.Integer(), sa.ForeignKey("mesocycles.id"), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("is_deload", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("mesocycle_id", "week_number"),
    )
    op.create_table(
        "workout_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mesocycle_id", sa.Integer(), sa.ForeignKey("mesocycles.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("order_in_split", sa.Integer(), nullable=False),
    )
    op.create_table(
        "template_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workout_template_id", sa.Integer(), sa.ForeignKey("workout_templates.id"), nullable=False),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("order_in_workout", sa.Integer(), nullable=False),
    )
    op.create_table(
        "exercise_prescriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_exercise_id", sa.Integer(), sa.ForeignKey("template_exercises.id"), nullable=False),
        sa.Column("week_id", sa.Integer(), sa.ForeignKey("weeks.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("template_exercise_id", "week_id"),
    )
    op.create_table(
        "set_prescriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_prescription_id", sa.Integer(), sa.ForeignKey("exercise_prescriptions.id"), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("set_type_id", sa.Integer(), sa.ForeignKey("set_types.id"), nullable=False),
        sa.Column("tempo_id", sa.Integer(), sa.ForeignKey("tempos.id"), nullable=False),
        sa.Column("rep_range_min", sa.Integer(), nullable=False),
        sa.Column("rep_range_max", sa.Integer(), nullable=False),
        sa.Column("target_rir", sa.Float(), nullable=True),
        sa.UniqueConstraint("exercise_prescription_id", "set_number"),
    )
