"""Troubleshooting guides and sessions.

Additive only: creates troubleshooting_guides, guide_nodes, guide_edges, node_evidence,
troubleshooting_sessions and session_steps. Existing tables and data are not touched.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07 05:30:56.111237+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('troubleshooting_guides',
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('problem_description', sa.Text(), nullable=False),
    sa.Column('equipment_identifier', sa.String(length=100), nullable=True),
    sa.Column('status', sa.Enum('ready', 'insufficient_evidence', name='guide_status', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('status_reason', sa.Text(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('model_name', sa.String(length=100), nullable=True),
    sa.Column('source_knowledge_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('conflicts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('uncertainties', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('validation_notes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_troubleshooting_guides'))
    )
    op.create_index(op.f('ix_troubleshooting_guides_status'), 'troubleshooting_guides', ['status'], unique=False)
    op.create_table('guide_nodes',
    sa.Column('guide_id', sa.Uuid(), nullable=False),
    sa.Column('node_key', sa.String(length=40), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('node_type', sa.Enum('start', 'question', 'diagnostic', 'recommendation', 'resolution', 'escalation', name='guide_node_type', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('question', sa.Text(), nullable=True),
    sa.Column('expected_answers', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('applicability_conditions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('knowledge_item_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('approval_status', sa.Enum('unreviewed', 'approved', 'rejected', name='node_approval_status', native_enum=False, create_constraint=True, length=40), nullable=True),
    sa.Column('support_level', sa.Enum('approved', 'confirmed_in_conversation', 'suggested', 'conflicting', 'none', name='support_level', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('requires_manual_verification', sa.Boolean(), nullable=False),
    sa.Column('conflict_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['guide_id'], ['troubleshooting_guides.id'], name=op.f('fk_guide_nodes_guide_id_troubleshooting_guides'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_guide_nodes')),
    sa.UniqueConstraint('guide_id', 'node_key', name=op.f('uq_guide_nodes_guide_id_node_key'))
    )
    op.create_index(op.f('ix_guide_nodes_guide_id'), 'guide_nodes', ['guide_id'], unique=False)
    op.create_table('guide_edges',
    sa.Column('guide_id', sa.Uuid(), nullable=False),
    sa.Column('source_node_id', sa.Uuid(), nullable=False),
    sa.Column('target_node_id', sa.Uuid(), nullable=False),
    sa.Column('answer_label', sa.String(length=100), nullable=False),
    sa.Column('condition', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['guide_id'], ['troubleshooting_guides.id'], name=op.f('fk_guide_edges_guide_id_troubleshooting_guides'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_node_id'], ['guide_nodes.id'], name=op.f('fk_guide_edges_source_node_id_guide_nodes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_node_id'], ['guide_nodes.id'], name=op.f('fk_guide_edges_target_node_id_guide_nodes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_guide_edges')),
    sa.UniqueConstraint('source_node_id', 'answer_label', name=op.f('uq_guide_edges_source_node_id_answer_label'))
    )
    op.create_index(op.f('ix_guide_edges_guide_id'), 'guide_edges', ['guide_id'], unique=False)
    op.create_index(op.f('ix_guide_edges_target_node_id'), 'guide_edges', ['target_node_id'], unique=False)
    op.create_table('troubleshooting_sessions',
    sa.Column('guide_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('in_progress', 'resolved', 'unresolved', name='session_status', native_enum=False, create_constraint=True, length=40), server_default='in_progress', nullable=False),
    sa.Column('current_node_id', sa.Uuid(), nullable=True),
    sa.Column('outcome_summary', sa.Text(), nullable=True),
    sa.Column('action_taken', sa.Text(), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['current_node_id'], ['guide_nodes.id'], name=op.f('fk_troubleshooting_sessions_current_node_id_guide_nodes'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['guide_id'], ['troubleshooting_guides.id'], name=op.f('fk_troubleshooting_sessions_guide_id_troubleshooting_guides'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_troubleshooting_sessions'))
    )
    op.create_index(op.f('ix_troubleshooting_sessions_guide_id'), 'troubleshooting_sessions', ['guide_id'], unique=False)
    op.create_index(op.f('ix_troubleshooting_sessions_status'), 'troubleshooting_sessions', ['status'], unique=False)
    op.create_table('session_steps',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('step_type', sa.Enum('answer', 'observation', 'back', 'complete', name='session_step_type', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('node_id', sa.Uuid(), nullable=True),
    sa.Column('answer_label', sa.String(length=100), nullable=True),
    sa.Column('target_node_id', sa.Uuid(), nullable=True),
    sa.Column('observation', sa.Text(), nullable=True),
    sa.Column('action_taken', sa.Text(), nullable=True),
    sa.Column('superseded', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['node_id'], ['guide_nodes.id'], name=op.f('fk_session_steps_node_id_guide_nodes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_id'], ['troubleshooting_sessions.id'], name=op.f('fk_session_steps_session_id_troubleshooting_sessions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_node_id'], ['guide_nodes.id'], name=op.f('fk_session_steps_target_node_id_guide_nodes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_session_steps')),
    sa.UniqueConstraint('session_id', 'sequence', name=op.f('uq_session_steps_session_id_sequence'))
    )
    op.create_index(op.f('ix_session_steps_session_id'), 'session_steps', ['session_id'], unique=False)
    op.create_table('node_evidence',
    sa.Column('node_id', sa.Uuid(), nullable=False),
    sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
    sa.Column('message_id', sa.Uuid(), nullable=False),
    sa.Column('evidence_type', sa.Enum('problem_report', 'attempted_fix', 'suggested_solution', 'confirmed_resolution', 'applicability_condition', name='node_evidence_type', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], name=op.f('fk_node_evidence_knowledge_item_id_knowledge_items'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], name=op.f('fk_node_evidence_message_id_messages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['node_id'], ['guide_nodes.id'], name=op.f('fk_node_evidence_node_id_guide_nodes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_node_evidence')),
    sa.UniqueConstraint('node_id', 'message_id', name=op.f('uq_node_evidence_node_id_message_id'))
    )
    op.create_index(op.f('ix_node_evidence_knowledge_item_id'), 'node_evidence', ['knowledge_item_id'], unique=False)
    op.create_index(op.f('ix_node_evidence_message_id'), 'node_evidence', ['message_id'], unique=False)
    op.create_index(op.f('ix_node_evidence_node_id'), 'node_evidence', ['node_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_node_evidence_node_id'), table_name='node_evidence')
    op.drop_index(op.f('ix_node_evidence_message_id'), table_name='node_evidence')
    op.drop_index(op.f('ix_node_evidence_knowledge_item_id'), table_name='node_evidence')
    op.drop_table('node_evidence')
    op.drop_index(op.f('ix_session_steps_session_id'), table_name='session_steps')
    op.drop_table('session_steps')
    op.drop_index(op.f('ix_troubleshooting_sessions_status'), table_name='troubleshooting_sessions')
    op.drop_index(op.f('ix_troubleshooting_sessions_guide_id'), table_name='troubleshooting_sessions')
    op.drop_table('troubleshooting_sessions')
    op.drop_index(op.f('ix_guide_edges_target_node_id'), table_name='guide_edges')
    op.drop_index(op.f('ix_guide_edges_guide_id'), table_name='guide_edges')
    op.drop_table('guide_edges')
    op.drop_index(op.f('ix_guide_nodes_guide_id'), table_name='guide_nodes')
    op.drop_table('guide_nodes')
    op.drop_index(op.f('ix_troubleshooting_guides_status'), table_name='troubleshooting_guides')
    op.drop_table('troubleshooting_guides')
