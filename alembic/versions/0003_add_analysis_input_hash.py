"""add input_hash to analyses

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-01 00:00:02.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check whether *column* already exists in *table* (SQLite)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        if not _column_exists("analyses", "input_hash"):
            batch_op.add_column(sa.Column("input_hash", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.drop_column("input_hash")
