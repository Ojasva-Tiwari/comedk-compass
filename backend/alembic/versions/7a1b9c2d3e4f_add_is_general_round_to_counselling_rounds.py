"""add_is_general_round_to_counselling_rounds

Revision ID: 7a1b9c2d3e4f
Revises: 5f20cbd3e7fc
Create Date: 2026-10-01 21:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a1b9c2d3e4f'
down_revision: Union[str, Sequence[str], None] = '5f20cbd3e7fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('counselling_rounds')]
    if 'is_general_round' not in columns:
        op.add_column(
            'counselling_rounds',
            sa.Column('is_general_round', sa.Boolean(), server_default=sa.text('true'), nullable=False)
        )


def downgrade() -> None:
    op.drop_column('counselling_rounds', 'is_general_round')
