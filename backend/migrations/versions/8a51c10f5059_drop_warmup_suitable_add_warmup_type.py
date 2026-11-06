"""drop is_warmup_suitable, add warmup exercise type, reset muscle taxonomy

Revision ID: 8a51c10f5059
Revises: 23b2d973ba4a
Create Date: 2026-08-29

exercise_types' schema is unchanged, but its data is cleared and reinserted
fresh (compound/isolation/warmup) rather than assuming compound/isolation
already exist — a migration shouldn't depend on a previous seed script
having run first.

muscles' schema is unchanged (id, name, muscle_group) — only its DATA is
being reset to the new consistent-granularity taxonomy. Its rows are
cleared here rather than migrated in place, same rationale as migration
23b2d973ba4a: only seed/demo data exists so far.

exercises loses the is_warmup_suitable column — that job is now split
between exercise_type="warmup" and supported_set_types containing
"warmup_set". Its three link tables are dropped/recreated only because
they carry a foreign key to exercises.id, not because their own shape
changed.
"""

from alembic import op
import sqlalchemy as sa

revision = "8a51c10f5059"
down_revision = "23b2d973ba4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Children of exercises must go before exercises itself.
    op.drop_table("exercise_tempos")
    op.drop_table("exercise_set_types")
    op.drop_table("exercise_muscles")
    op.drop_table("exercises")

    # muscles has no FK relationship left pointing at it now that
    # exercise_muscles is gone — safe to clear and reseed with the new
    # taxonomy without touching its schema.
    op.execute(sa.text("DELETE FROM muscles"))

    # exercise_types: don't assume compound/isolation are already seeded
    # (they might not be, e.g. on a fresh database) — clear and insert all
    # three fresh, same rationale as muscles above.
    op.execute(sa.text("DELETE FROM exercise_types"))
    op.execute(
        sa.text(
            "INSERT INTO exercise_types (name) VALUES "
            "('compound'), ('isolation'), ('warmup')"
        )
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
            "movement_category_id", sa.Integer(),
            sa.ForeignKey("movement_categories.id"), nullable=False,
        ),
        sa.Column(
            "exercise_type_id", sa.Integer(), sa.ForeignKey("exercise_types.id"),
            nullable=False,
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

    op.execute(sa.text("DELETE FROM exercise_types WHERE name = 'warmup'"))
    op.execute(sa.text("DELETE FROM muscles"))

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
