"""create workout session / performed exercise / set performance tables

Revision ID: f6eb9b3d3076
Revises: 4cfac688f57d
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa

revision = "f6eb9b3d3076"
down_revision = "4cfac688f57d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mesocycle_id", sa.Integer(), sa.ForeignKey("mesocycles.id"), nullable=False),
        sa.Column("week_id", sa.Integer(), sa.ForeignKey("weeks.id"), nullable=False),
        sa.Column("workout_template_id", sa.Integer(), sa.ForeignKey("workout_templates.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "performed_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workout_session_id", sa.Integer(), sa.ForeignKey("workout_sessions.id"), nullable=False),
        sa.Column("template_exercise_id", sa.Integer(), sa.ForeignKey("template_exercises.id"), nullable=True),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("order_performed", sa.Integer(), nullable=False),
    )

    op.create_table(
        "set_performances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("performed_exercise_id", sa.Integer(), sa.ForeignKey("performed_exercises.id"), nullable=False),
        sa.Column("set_prescription_id", sa.Integer(), sa.ForeignKey("set_prescriptions.id"), nullable=True),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("set_type_id", sa.Integer(), sa.ForeignKey("set_types.id"), nullable=False),
        sa.Column("tempo_id", sa.Integer(), sa.ForeignKey("tempos.id"), nullable=False),
        sa.Column("actual_weight", sa.Float(), nullable=True),
        sa.Column("actual_reps", sa.Integer(), nullable=True),
        sa.Column("partial_reps", sa.Integer(), nullable=True),
        sa.Column("actual_rir", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("set_performances")
    op.drop_table("performed_exercises")
    op.drop_table("workout_sessions")
