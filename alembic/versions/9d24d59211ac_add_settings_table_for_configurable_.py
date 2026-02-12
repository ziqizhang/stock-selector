"""Add settings table for configurable scoring weights

Revision ID: 9d24d59211ac
Revises: 0003
Create Date: 2026-02-12 16:31:01.000584
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d24d59211ac'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create settings table for user preferences
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.Text(), nullable=False, unique=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    
    # Create index on key for fast lookups
    op.create_index('idx_settings_key', 'settings', ['key'])


def downgrade() -> None:
    # Drop settings table
    op.drop_index('idx_settings_key', table_name='settings')
    op.drop_table('settings')
