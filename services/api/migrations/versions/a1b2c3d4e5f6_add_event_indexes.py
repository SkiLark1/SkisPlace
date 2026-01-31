"""add_event_indexes

Revision ID: a1b2c3d4e5f6
Revises: c3b27c1d1650
Create Date: 2026-01-23 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c3b27c1d1650"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Usage Events indexes
    op.create_index(
        op.f("ix_usage_events_project_id"), "usage_events", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_usage_events_module_id"), "usage_events", ["module_id"], unique=False
    )
    op.create_index(
        op.f("ix_usage_events_timestamp"), "usage_events", ["timestamp"], unique=False
    )

    # Error Events indexes
    op.create_index(
        op.f("ix_error_events_project_id"), "error_events", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_error_events_timestamp"), "error_events", ["timestamp"], unique=False
    )


def downgrade() -> None:
    # Error Events indexes
    op.drop_index(op.f("ix_error_events_timestamp"), table_name="error_events")
    op.drop_index(op.f("ix_error_events_project_id"), table_name="error_events")

    # Usage Events indexes
    op.drop_index(op.f("ix_usage_events_timestamp"), table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_module_id"), table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_project_id"), table_name="usage_events")
