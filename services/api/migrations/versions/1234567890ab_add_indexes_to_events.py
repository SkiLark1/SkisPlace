"""add_indexes_to_events

Revision ID: 1234567890ab
Revises: c3b27c1d1650
Create Date: 2026-02-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1234567890ab'
down_revision: Union[str, None] = 'c3b27c1d1650'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Usage Events
    op.create_index(
        op.f("ix_usage_events_project_id"),
        "usage_events",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_usage_events_timestamp"),
        "usage_events",
        ["timestamp"],
        unique=False,
    )

    # Error Events
    op.create_index(
        op.f("ix_error_events_project_id"),
        "error_events",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_error_events_timestamp"),
        "error_events",
        ["timestamp"],
        unique=False,
    )


def downgrade() -> None:
    # Error Events
    op.drop_index(op.f('ix_error_events_timestamp'), table_name='error_events')
    op.drop_index(op.f('ix_error_events_project_id'), table_name='error_events')

    # Usage Events
    op.drop_index(op.f('ix_usage_events_timestamp'), table_name='usage_events')
    op.drop_index(op.f('ix_usage_events_project_id'), table_name='usage_events')
