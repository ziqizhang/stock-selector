"""add market and resolved_symbol to tickers

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check whether *column* already exists in *table* (SQLite)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    with op.batch_alter_table("tickers") as batch_op:
        if not _column_exists("tickers", "market"):
            batch_op.add_column(
                sa.Column("market", sa.Text(), server_default=sa.text("'US'"))
            )
        if not _column_exists("tickers", "resolved_symbol"):
            batch_op.add_column(sa.Column("resolved_symbol", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("tickers") as batch_op:
        batch_op.drop_column("resolved_symbol")
        batch_op.drop_column("market")
