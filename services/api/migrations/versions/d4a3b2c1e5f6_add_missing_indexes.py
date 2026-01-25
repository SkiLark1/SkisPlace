"""add_missing_indexes

Revision ID: d4a3b2c1e5f6
Revises: c3b27c1d1650
Create Date: 2026-01-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a3b2c1e5f6'
down_revision: Union[str, None] = 'c3b27c1d1650'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Projects
    op.create_index(op.f('ix_projects_client_id'), 'projects', ['client_id'], unique=False)

    # Project Domains
    op.create_index(op.f('ix_project_domains_project_id'), 'project_domains', ['project_id'], unique=False)

    # Api Keys
    op.create_index(op.f('ix_api_keys_project_id'), 'api_keys', ['project_id'], unique=False)

    # Project Modules
    op.create_index(op.f('ix_project_modules_project_id'), 'project_modules', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_modules_module_id'), 'project_modules', ['module_id'], unique=False)

    # Assets
    op.create_index(op.f('ix_assets_project_id'), 'assets', ['project_id'], unique=False)

    # Usage Events
    op.create_index(op.f('ix_usage_events_project_id'), 'usage_events', ['project_id'], unique=False)
    op.create_index(op.f('ix_usage_events_module_id'), 'usage_events', ['module_id'], unique=False)

    # Error Events
    op.create_index(op.f('ix_error_events_project_id'), 'error_events', ['project_id'], unique=False)

    # Epoxy Styles
    op.create_index(op.f('ix_epoxy_styles_project_id'), 'epoxy_styles', ['project_id'], unique=False)
    op.create_index(op.f('ix_epoxy_styles_cover_image_id'), 'epoxy_styles', ['cover_image_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_epoxy_styles_cover_image_id'), table_name='epoxy_styles')
    op.drop_index(op.f('ix_epoxy_styles_project_id'), table_name='epoxy_styles')
    op.drop_index(op.f('ix_error_events_project_id'), table_name='error_events')
    op.drop_index(op.f('ix_usage_events_module_id'), table_name='usage_events')
    op.drop_index(op.f('ix_usage_events_project_id'), table_name='usage_events')
    op.drop_index(op.f('ix_assets_project_id'), table_name='assets')
    op.drop_index(op.f('ix_project_modules_module_id'), table_name='project_modules')
    op.drop_index(op.f('ix_project_modules_project_id'), table_name='project_modules')
    op.drop_index(op.f('ix_api_keys_project_id'), table_name='api_keys')
    op.drop_index(op.f('ix_project_domains_project_id'), table_name='project_domains')
    op.drop_index(op.f('ix_projects_client_id'), table_name='projects')
