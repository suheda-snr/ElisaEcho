"""Integration state and events (Slack connector).

Additive only: creates integration_state and integration_events. No secrets are stored.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07 08:56:37.536648+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('integration_events',
    sa.Column('integration', sa.String(length=40), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('level', sa.String(length=10), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('channel_id', sa.String(length=64), nullable=True),
    sa.Column('thread_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_integration_events'))
    )
    op.create_index('ix_integration_events_integration_created_at', 'integration_events', ['integration', 'created_at'], unique=False)
    op.create_table('integration_state',
    sa.Column('name', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('connection_mode', sa.String(length=40), nullable=True),
    sa.Column('workspace_id', sa.String(length=64), nullable=True),
    sa.Column('workspace_name', sa.String(length=200), nullable=True),
    sa.Column('bot_user_id', sa.String(length=64), nullable=True),
    sa.Column('connected', sa.Boolean(), nullable=False),
    sa.Column('credentials_verified', sa.Boolean(), nullable=False),
    sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_ingested_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('name', name=op.f('pk_integration_state'))
    )


def downgrade() -> None:
    op.drop_table('integration_state')
    op.drop_index('ix_integration_events_integration_created_at', table_name='integration_events')
    op.drop_table('integration_events')
