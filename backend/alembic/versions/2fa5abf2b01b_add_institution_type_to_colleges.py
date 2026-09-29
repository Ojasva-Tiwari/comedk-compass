"""add_institution_type_to_colleges

Revision ID: 2fa5abf2b01b
Revises: 48219ca4aa58
Create Date: 2026-09-29 16:43:22.349067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fa5abf2b01b'
down_revision: Union[str, Sequence[str], None] = '48219ca4aa58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'colleges',
        sa.Column('institution_type', sa.String(length=50), server_default='ENGINEERING', nullable=False)
    )
    op.create_check_constraint(
        'chk_colleges_institution_type',
        'colleges',
        "institution_type IN ('ENGINEERING', 'ARCHITECTURE', 'MEDICAL', 'DENTAL')"
    )
    op.create_index('idx_colleges_institution_type', 'colleges', ['institution_type'], unique=False)

    # Backfill based on official source context
    # 1. Architecture institutions from official Member Institutions Architecture table
    arch_codes = (
        'E002', 'E008', 'E029', 'E054', 'E163', 'E168', 'E169',
        'E175', 'E176', 'E178', 'E181', 'E189', 'E193', 'E213'
    )
    op.execute(
        f"UPDATE colleges SET institution_type = 'ARCHITECTURE' WHERE code IN {arch_codes}"
    )

    # 2. Dental institutions from official Member Institutions Dental table
    op.execute(
        "UPDATE colleges SET institution_type = 'DENTAL' WHERE code LIKE 'D%'"
    )

    # 3. Medical institutions from official Member Institutions Medical table
    op.execute(
        "UPDATE colleges SET institution_type = 'MEDICAL' WHERE code LIKE 'M%'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('chk_colleges_institution_type', 'colleges', type_='check')
    op.drop_index('idx_colleges_institution_type', table_name='colleges')
    op.drop_column('colleges', 'institution_type')

