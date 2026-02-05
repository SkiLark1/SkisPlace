"""Add performance indexes

Revision ID: a1b2c3d4e5f6
Revises: ee76edde8104
Create Date: 2026-05-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ee76edde8104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        op.f('ix_projects_client_id'), 'projects', ['client_id'], unique=False
    )
    op.create_index(
        op.f('ix_usage_events_project_id'),
        'usage_events',
        ['project_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_error_events_project_id'),
        'error_events',
        ['project_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_error_events_project_id'), table_name='error_events')
    op.drop_index(op.f('ix_usage_events_project_id'), table_name='usage_events')
    op.drop_index(op.f('ix_projects_client_id'), table_name='projects')
