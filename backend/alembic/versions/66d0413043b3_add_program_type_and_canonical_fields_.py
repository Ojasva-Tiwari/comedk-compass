"""add_program_type_and_canonical_fields_to_branches

Revision ID: 66d0413043b3
Revises: 2fa5abf2b01b
Create Date: 2026-09-29 17:43:25.961600

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66d0413043b3'
down_revision: Union[str, Sequence[str], None] = '2fa5abf2b01b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('branches', sa.Column('program_type', sa.String(length=50), server_default='ENGINEERING', nullable=False))
    op.add_column('branches', sa.Column('is_canonical', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('branches', sa.Column('canonical_branch_id', sa.UUID(), nullable=True))
    op.create_check_constraint(
        'chk_branches_program_type',
        'branches',
        "program_type IN ('ENGINEERING', 'ARCHITECTURE', 'DESIGN', 'OTHER')"
    )
    op.create_index('idx_branches_program_canonical', 'branches', ['program_type', 'is_canonical'], unique=False)
    op.create_index(op.f('ix_branches_canonical_branch_id'), 'branches', ['canonical_branch_id'], unique=False)
    op.create_index(op.f('ix_branches_is_canonical'), 'branches', ['is_canonical'], unique=False)
    op.create_index(op.f('ix_branches_program_type'), 'branches', ['program_type'], unique=False)
    op.create_foreign_key('fk_branches_canonical_branch_id', 'branches', 'branches', ['canonical_branch_id'], ['id'], ondelete='SET NULL')

def downgrade() -> None:
    op.drop_constraint('fk_branches_canonical_branch_id', 'branches', type_='foreignkey')
    op.drop_constraint('chk_branches_program_type', 'branches', type_='check')
    op.drop_index(op.f('ix_branches_program_type'), table_name='branches')
    op.drop_index(op.f('ix_branches_is_canonical'), table_name='branches')
    op.drop_index(op.f('ix_branches_canonical_branch_id'), table_name='branches')
    op.drop_index('idx_branches_program_canonical', table_name='branches')
    op.drop_column('branches', 'canonical_branch_id')
    op.drop_column('branches', 'is_canonical')
    op.drop_column('branches', 'program_type')
