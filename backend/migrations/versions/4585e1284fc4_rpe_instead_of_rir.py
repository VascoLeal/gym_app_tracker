"""RPE instead of RIR, deload strategy 'none', simplify set performance

Revision ID: 4585e1284fc4
Revises: f6eb9b3d3076
Create Date: 2026-08-30

Non-destructive, unlike several earlier migrations — real mesocycle/week/
session data now exists (the author has actually trained through this),
so this uses ALTER-style operations (via batch_alter_table for SQLite
compatibility) and backfills existing rows rather than dropping tables.

- weeks: adds target_rpe (nullable), backfilled for existing weeks using
  the same 7->10 ramp formula the app uses going forward (duplicated here
  rather than imported from app code, since migrations should stay
  correct independent of future code changes).
- deload_strategies: adds "none" as a new row WITHOUT touching existing
  rows/ids — deload_strategy_id on mesocycles is a live FK, so a
  delete-and-reinsert here (like earlier migrations used) would silently
  break every existing mesocycle's reference.
- set_prescriptions: drops target_rir — RPE targets now live on Week,
  computed once per week rather than entered per set.
- set_performances: drops set_type_id/tempo_id/partial_reps, renames
  actual_rir -> actual_rpe, widens actual_reps to Float so a partial rep
  is e.g. 8.5 instead of a separate field, and adds an optional free-text
  notes column for anything that doesn't fit weight/reps/RPE.
"""

from alembic import op
import sqlalchemy as sa

revision = "4585e1284fc4"
down_revision = "f6eb9b3d3076"
branch_labels = None
depends_on = None


def _compute_week_target_rpes(number_of_weeks: int, deload_strategy_name: str) -> dict[int, float | None]:
    has_deload_week = deload_strategy_name in ("rest", "reduced_load")
    non_deload_weeks = number_of_weeks - 1 if has_deload_week else number_of_weeks

    targets: dict[int, float | None] = {}
    for week_number in range(1, non_deload_weeks + 1):
        week_index = week_number - 1
        if non_deload_weeks == 1:
            rpe = 10.0
        else:
            rpe = 7 + 3 * week_index / (non_deload_weeks - 1)
        targets[week_number] = float(round(rpe))

    if has_deload_week:
        targets[number_of_weeks] = None

    return targets


def upgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("weeks") as batch_op:
        batch_op.add_column(sa.Column("target_rpe", sa.Float(), nullable=True))

    # --- backfill target_rpe for existing weeks ---
    mesocycles = sa.table(
        "mesocycles",
        sa.column("id", sa.Integer),
        sa.column("number_of_weeks", sa.Integer),
        sa.column("deload_strategy_id", sa.Integer),
    )
    deload_strategies = sa.table(
        "deload_strategies", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    weeks = sa.table(
        "weeks",
        sa.column("id", sa.Integer),
        sa.column("mesocycle_id", sa.Integer),
        sa.column("week_number", sa.Integer),
        sa.column("target_rpe", sa.Float),
    )

    strategy_name_by_id = {
        row.id: row.name for row in conn.execute(sa.select(deload_strategies))
    }

    for mesocycle_row in conn.execute(sa.select(mesocycles)):
        strategy_name = strategy_name_by_id.get(mesocycle_row.deload_strategy_id)
        if strategy_name is None:
            continue
        targets = _compute_week_target_rpes(mesocycle_row.number_of_weeks, strategy_name)
        for week_number, target in targets.items():
            conn.execute(
                weeks.update()
                .where(weeks.c.mesocycle_id == mesocycle_row.id)
                .where(weeks.c.week_number == week_number)
                .values(target_rpe=target)
            )

    # --- add "none" deload strategy without disturbing existing rows/ids ---
    existing_strategy_names = set(strategy_name_by_id.values())
    if "none" not in existing_strategy_names:
        conn.execute(deload_strategies.insert().values(name="none"))

    # --- set_prescriptions: RPE targets now live on Week, not per-set ---
    with op.batch_alter_table("set_prescriptions") as batch_op:
        batch_op.drop_column("target_rir")

    # --- set_performances: simplify to weight/reps/RPE only, plus an
    # optional free-text note for anything that doesn't fit those three ---
    with op.batch_alter_table("set_performances") as batch_op:
        batch_op.drop_column("set_type_id")
        batch_op.drop_column("tempo_id")
        batch_op.drop_column("partial_reps")
        batch_op.alter_column("actual_rir", new_column_name="actual_rpe")
        batch_op.alter_column("actual_reps", type_=sa.Float())
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("set_performances") as batch_op:
        batch_op.drop_column("notes")
        batch_op.alter_column("actual_reps", type_=sa.Integer())
        batch_op.alter_column("actual_rpe", new_column_name="actual_rir")
        batch_op.add_column(sa.Column("partial_reps", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tempo_id", sa.Integer(), sa.ForeignKey("tempos.id")))
        batch_op.add_column(sa.Column("set_type_id", sa.Integer(), sa.ForeignKey("set_types.id")))

    with op.batch_alter_table("set_prescriptions") as batch_op:
        batch_op.add_column(sa.Column("target_rir", sa.Float(), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM deload_strategies WHERE name = 'none'"))

    with op.batch_alter_table("weeks") as batch_op:
        batch_op.drop_column("target_rpe")
