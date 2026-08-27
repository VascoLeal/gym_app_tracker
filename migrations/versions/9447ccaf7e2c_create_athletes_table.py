"""create athletes table

Revision ID: 9447ccaf7e2c
Revises:
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "9447ccaf7e2c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athletes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_athletes_email", "athletes", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_athletes_email", table_name="athletes")
    op.drop_table("athletes")
