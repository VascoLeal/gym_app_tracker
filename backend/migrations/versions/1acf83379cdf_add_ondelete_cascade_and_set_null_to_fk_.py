"""add ondelete cascade/set null to fk constraints

Revision ID: 1acf83379cdf
Revises: e283d0385b2b
Create Date: 2026-09-14 23:26:33.547473

Fixes a real 500: stop_mesocycle(keep_as_history=False) and
delete_mesocycle both do a plain db.delete(mesocycle), which only cascades
through relationships the ORM actually knows about (weeks,
workout_templates -> their direct children). exercise_prescriptions
(referenced from both weeks and template_exercises) and workout_sessions
(referenced from mesocycles, weeks, and workout_templates) had no ORM
relationship declared in that direction at all, so the ORM never touched
them — Postgres then rejected the DELETE outright with a
ForeignKeyViolation the instant a mesocycle had any prescriptions.

Rather than teach the ORM every one of these paths, this pushes the whole
delete-cascade down to Postgres itself via ON DELETE CASCADE — correct
regardless of which parent row a cascading delete happens to hit first,
which matters here since e.g. workout_sessions is reachable from three
different parents (mesocycle, week, workout_template) that can each be
deleted in any order within the same statement's cascade.

Two FKs get ON DELETE SET NULL instead of CASCADE, deliberately: they're
the two "the plan changed after the fact" columns
(performed_exercises.template_exercise_id,
set_performances.set_prescription_id) — both already nullable, both
already meant "no plan slot behind this" for freeform-added
exercises/sets. Historical performance data should outlive an edited-away
plan, not disappear with it — same reasoning already encoded in each
column's docstring, just not yet enforced at the DB level.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1acf83379cdf'
down_revision = 'e283d0385b2b'
branch_labels = None
depends_on = None

# (constraint_name, table, column, referred_table, ondelete_action)
_FOREIGN_KEYS = [
    ("weeks_mesocycle_id_fkey", "weeks", "mesocycle_id", "mesocycles", "CASCADE"),
    ("workout_templates_mesocycle_id_fkey", "workout_templates", "mesocycle_id", "mesocycles", "CASCADE"),
    ("template_exercises_workout_template_id_fkey", "template_exercises", "workout_template_id", "workout_templates", "CASCADE"),
    ("exercise_prescriptions_week_id_fkey", "exercise_prescriptions", "week_id", "weeks", "CASCADE"),
    ("exercise_prescriptions_template_exercise_id_fkey", "exercise_prescriptions", "template_exercise_id", "template_exercises", "CASCADE"),
    ("set_prescriptions_exercise_prescription_id_fkey", "set_prescriptions", "exercise_prescription_id", "exercise_prescriptions", "CASCADE"),
    ("workout_sessions_mesocycle_id_fkey", "workout_sessions", "mesocycle_id", "mesocycles", "CASCADE"),
    ("workout_sessions_week_id_fkey", "workout_sessions", "week_id", "weeks", "CASCADE"),
    ("workout_sessions_workout_template_id_fkey", "workout_sessions", "workout_template_id", "workout_templates", "CASCADE"),
    ("performed_exercises_workout_session_id_fkey", "performed_exercises", "workout_session_id", "workout_sessions", "CASCADE"),
    ("performed_exercises_template_exercise_id_fkey", "performed_exercises", "template_exercise_id", "template_exercises", "SET NULL"),
    ("set_performances_performed_exercise_id_fkey", "set_performances", "performed_exercise_id", "performed_exercises", "CASCADE"),
    ("set_performances_set_prescription_id_fkey", "set_performances", "set_prescription_id", "set_prescriptions", "SET NULL"),
]


def upgrade() -> None:
    for constraint_name, table, column, referred_table, ondelete in _FOREIGN_KEYS:
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name, table, referred_table, [column], ["id"], ondelete=ondelete
        )


def downgrade() -> None:
    for constraint_name, table, column, referred_table, _ondelete in _FOREIGN_KEYS:
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(constraint_name, table, referred_table, [column], ["id"])
