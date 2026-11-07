"""Troubleshooting feedback: engineers' reports on whether a recommendation worked.

Additive only (one new table). Existing data is not changed.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-07 13:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'troubleshooting_feedback',
        sa.Column('troubleshooting_session_id', sa.Uuid(), nullable=False),
        sa.Column('guide_node_id', sa.Uuid(), nullable=False),
        sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
        sa.Column('attempted', sa.Boolean(), nullable=False),
        sa.Column('outcome', sa.String(length=30), nullable=False),
        sa.Column('equipment_identifier', sa.String(length=100), nullable=True),
        sa.Column('firmware_version', sa.String(length=100), nullable=True),
        sa.Column('environment_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('engineer_notes', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.String(length=30), server_default=sa.text("'self_reported'"),
                  nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('edit_token_hash', sa.String(length=64), nullable=False),
        sa.Column('revision', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('revisions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"),
                  nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("outcome IN ('resolved', 'not_resolved', 'partially_resolved', 'unknown', 'not_attempted')",
                           name=op.f('ck_troubleshooting_feedback_feedback_outcome')),
        sa.CheckConstraint("verification_status IN ('self_reported', 'independently_verified')",
                           name=op.f('ck_troubleshooting_feedback_feedback_verification_status')),
        sa.CheckConstraint("attempted = (outcome <> 'not_attempted')",
                           name=op.f('ck_troubleshooting_feedback_feedback_attempt_consistent')),
        sa.ForeignKeyConstraint(['guide_node_id'], ['guide_nodes.id'],
                                name='fk_feedback_guide_node', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'],
                                name='fk_feedback_knowledge_item',
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['troubleshooting_session_id'], ['troubleshooting_sessions.id'],
                                name='fk_feedback_session',
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_troubleshooting_feedback')),
        sa.UniqueConstraint('troubleshooting_session_id', 'guide_node_id', 'knowledge_item_id',
                            name='uq_feedback_session_node_knowledge'),
    )
    op.create_index(op.f('ix_troubleshooting_feedback_knowledge_item_id'), 'troubleshooting_feedback',
                    ['knowledge_item_id'], unique=False)
    op.create_index(op.f('ix_troubleshooting_feedback_outcome'), 'troubleshooting_feedback', ['outcome'],
                    unique=False)
    op.create_index(op.f('ix_troubleshooting_feedback_troubleshooting_session_id'), 'troubleshooting_feedback',
                    ['troubleshooting_session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_troubleshooting_feedback_troubleshooting_session_id'), table_name='troubleshooting_feedback')
    op.drop_index(op.f('ix_troubleshooting_feedback_outcome'), table_name='troubleshooting_feedback')
    op.drop_index(op.f('ix_troubleshooting_feedback_knowledge_item_id'), table_name='troubleshooting_feedback')
    op.drop_table('troubleshooting_feedback')
