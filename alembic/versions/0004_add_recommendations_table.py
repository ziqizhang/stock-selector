"""Add recommendations table for backtest tracking

Revision ID: 0004
Revises: 9d24d59211ac
Create Date: 2026-02-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '9d24d59211ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recommendations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.Text(), sa.ForeignKey('tickers.symbol', ondelete='CASCADE'), nullable=False),
        sa.Column('recommendation', sa.Text(), nullable=False),
        sa.Column('overall_score', sa.REAL(), nullable=False),
        sa.Column('price_at_rec', sa.REAL(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index('idx_recommendations_symbol', 'recommendations', ['symbol'])
    op.create_index('idx_recommendations_created_at', 'recommendations', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_recommendations_created_at', table_name='recommendations')
    op.drop_index('idx_recommendations_symbol', table_name='recommendations')
    op.drop_table('recommendations')
