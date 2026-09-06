"""add target_weight to set_prescriptions

Revision ID: e283d0385b2b
Revises: 4585e1284fc4
Create Date: 2026-08-31

Non-destructive, same as the previous migration — real data exists.
target_weight is nullable and left NULL for every existing row: there's
no sound way to backfill a number that was never tracked, and NULL
correctly means "no recommendation available," same as it will for any
future week the progression engine can't generate one for.
"""

from alembic import op
import sqlalchemy as sa

revision = "e283d0385b2b"
down_revision = "4585e1284fc4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("set_prescriptions") as batch_op:
        batch_op.add_column(sa.Column("target_weight", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("set_prescriptions") as batch_op:
        batch_op.drop_column("target_weight")
