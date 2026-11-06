"""Initial communication intelligence schema.

Enables pgvector and creates the tables for communication sources, threads,
messages, knowledge candidates/items, evidence, equipment, incidents, their
association tables and embedding chunks (vector(768), HNSW cosine index).

Revision ID: 0001
Revises: 
Create Date: 2026-11-06 19:05:49.335540+00:00
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector must exist before the vector column is created. IF NOT EXISTS keeps this
    # safe on Tiger Data services where the extension is already enabled.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('communication_sources',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('source_type', sa.Enum('slack', 'teams', 'simulated', name='source_type', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('external_source_id', sa.String(length=255), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_communication_sources')),
    sa.UniqueConstraint('source_type', 'external_source_id', name=op.f('uq_communication_sources_source_type_external_source_id'))
    )
    op.create_table('equipment',
    sa.Column('equipment_identifier', sa.String(length=100), nullable=False),
    sa.Column('equipment_type', sa.String(length=100), nullable=True),
    sa.Column('vendor', sa.String(length=100), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('site_identifier', sa.String(length=100), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_equipment')),
    sa.UniqueConstraint('equipment_identifier', name=op.f('uq_equipment_equipment_identifier'))
    )
    op.create_index(op.f('ix_equipment_site_identifier'), 'equipment', ['site_identifier'], unique=False)
    op.create_table('incidents',
    sa.Column('incident_number', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('open', 'investigating', 'resolved', 'closed', name='incident_status', native_enum=False, create_constraint=True, length=40), server_default='open', nullable=False),
    sa.Column('severity', sa.Enum('critical', 'high', 'medium', 'low', name='incident_severity', native_enum=False, create_constraint=True, length=40), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_incidents')),
    sa.UniqueConstraint('incident_number', name=op.f('uq_incidents_incident_number'))
    )
    op.create_index(op.f('ix_incidents_status'), 'incidents', ['status'], unique=False)
    op.create_table('conversation_threads',
    sa.Column('communication_source_id', sa.Uuid(), nullable=False),
    sa.Column('external_thread_id', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('processing_status', sa.Enum('pending', 'processing', 'processed', 'failed', name='processing_status', native_enum=False, create_constraint=True, length=40), server_default='pending', nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['communication_source_id'], ['communication_sources.id'], name=op.f('fk_conversation_threads_communication_source_id_communication_sources'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_conversation_threads')),
    sa.UniqueConstraint('communication_source_id', 'external_thread_id', name=op.f('uq_conversation_threads_communication_source_id_external_thread_id'))
    )
    op.create_index(op.f('ix_conversation_threads_communication_source_id'), 'conversation_threads', ['communication_source_id'], unique=False)
    op.create_index('ix_conversation_threads_last_message_at', 'conversation_threads', ['last_message_at'], unique=False)
    op.create_index(op.f('ix_conversation_threads_processing_status'), 'conversation_threads', ['processing_status'], unique=False)
    op.create_table('knowledge_candidates',
    sa.Column('thread_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_type', sa.String(length=50), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('detection_status', sa.Enum('detected', 'incomplete', 'rejected', 'accepted', name='detection_status', native_enum=False, create_constraint=True, length=40), server_default='detected', nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('model_name', sa.String(length=100), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)', name=op.f('ck_knowledge_candidates_confidence_range')),
    sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id'], name=op.f('fk_knowledge_candidates_thread_id_conversation_threads'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_candidates'))
    )
    op.create_index(op.f('ix_knowledge_candidates_detection_status'), 'knowledge_candidates', ['detection_status'], unique=False)
    op.create_index(op.f('ix_knowledge_candidates_thread_id'), 'knowledge_candidates', ['thread_id'], unique=False)
    op.create_table('messages',
    sa.Column('thread_id', sa.Uuid(), nullable=False),
    sa.Column('external_message_id', sa.String(length=255), nullable=False),
    sa.Column('author_external_id', sa.String(length=255), nullable=False),
    sa.Column('author_display_name', sa.String(length=200), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('source_url', sa.String(length=2048), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id'], name=op.f('fk_messages_thread_id_conversation_threads'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messages')),
    sa.UniqueConstraint('thread_id', 'external_message_id', name=op.f('uq_messages_thread_id_external_message_id'))
    )
    op.create_index(op.f('ix_messages_author_external_id'), 'messages', ['author_external_id'], unique=False)
    op.create_index('ix_messages_thread_id_sent_at', 'messages', ['thread_id', 'sent_at'], unique=False)
    op.create_table('knowledge_items',
    sa.Column('candidate_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('problem_description', sa.Text(), nullable=False),
    sa.Column('symptoms', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('root_cause', sa.Text(), nullable=True),
    sa.Column('resolution', sa.Text(), nullable=True),
    sa.Column('attempted_actions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('applicability_conditions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('resolution_status', sa.Enum('unknown', 'suggested', 'confirmed_in_conversation', name='resolution_status', native_enum=False, create_constraint=True, length=40), server_default='unknown', nullable=False),
    sa.Column('approval_status', sa.Enum('unreviewed', 'approved', 'rejected', name='approval_status', native_enum=False, create_constraint=True, length=40), server_default='unreviewed', nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['knowledge_candidates.id'], name=op.f('fk_knowledge_items_candidate_id_knowledge_candidates'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_items')),
    sa.UniqueConstraint('candidate_id', name=op.f('uq_knowledge_items_candidate_id'))
    )
    op.create_index(op.f('ix_knowledge_items_approval_status'), 'knowledge_items', ['approval_status'], unique=False)
    op.create_index(op.f('ix_knowledge_items_resolution_status'), 'knowledge_items', ['resolution_status'], unique=False)
    op.create_table('knowledge_chunks',
    sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_chunks_knowledge_item_id_knowledge_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_chunks')),
    sa.UniqueConstraint('knowledge_item_id', 'chunk_index', name=op.f('uq_knowledge_chunks_knowledge_item_id_chunk_index'))
    )
    op.create_index('ix_knowledge_chunks_embedding_hnsw', 'knowledge_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_knowledge_chunks_knowledge_item_id'), 'knowledge_chunks', ['knowledge_item_id'], unique=False)
    op.create_table('knowledge_evidence',
    sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
    sa.Column('message_id', sa.Uuid(), nullable=False),
    sa.Column('evidence_type', sa.Enum('problem_report', 'attempted_fix', 'suggested_solution', 'confirmed_resolution', 'applicability_condition', name='evidence_type', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_evidence_knowledge_item_id_knowledge_items'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], name=op.f('fk_knowledge_evidence_message_id_messages'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_evidence')),
    sa.UniqueConstraint('knowledge_item_id', 'message_id', 'evidence_type', name=op.f('uq_knowledge_evidence_knowledge_item_id_message_id_evidence_type'))
    )
    op.create_index(op.f('ix_knowledge_evidence_knowledge_item_id'), 'knowledge_evidence', ['knowledge_item_id'], unique=False)
    op.create_index(op.f('ix_knowledge_evidence_message_id'), 'knowledge_evidence', ['message_id'], unique=False)
    op.create_table('knowledge_item_equipment',
    sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
    sa.Column('equipment_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id'], name=op.f('fk_knowledge_item_equipment_equipment_id_equipment'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_item_equipment_knowledge_item_id_knowledge_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('knowledge_item_id', 'equipment_id', name=op.f('pk_knowledge_item_equipment'))
    )
    op.create_index(op.f('ix_knowledge_item_equipment_equipment_id'), 'knowledge_item_equipment', ['equipment_id'], unique=False)
    op.create_table('knowledge_item_incidents',
    sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
    sa.Column('incident_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], name=op.f('fk_knowledge_item_incidents_incident_id_incidents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_item_incidents_knowledge_item_id_knowledge_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('knowledge_item_id', 'incident_id', name=op.f('pk_knowledge_item_incidents'))
    )
    op.create_index(op.f('ix_knowledge_item_incidents_incident_id'), 'knowledge_item_incidents', ['incident_id'], unique=False)


def downgrade() -> None:
    # Drops only the tables created above. The `vector` extension is intentionally
    # left installed because other schemas on a shared database may rely on it.
    op.drop_index(op.f('ix_knowledge_item_incidents_incident_id'), table_name='knowledge_item_incidents')
    op.drop_table('knowledge_item_incidents')
    op.drop_index(op.f('ix_knowledge_item_equipment_equipment_id'), table_name='knowledge_item_equipment')
    op.drop_table('knowledge_item_equipment')
    op.drop_index(op.f('ix_knowledge_evidence_message_id'), table_name='knowledge_evidence')
    op.drop_index(op.f('ix_knowledge_evidence_knowledge_item_id'), table_name='knowledge_evidence')
    op.drop_table('knowledge_evidence')
    op.drop_index(op.f('ix_knowledge_chunks_knowledge_item_id'), table_name='knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_embedding_hnsw', table_name='knowledge_chunks', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_items_resolution_status'), table_name='knowledge_items')
    op.drop_index(op.f('ix_knowledge_items_approval_status'), table_name='knowledge_items')
    op.drop_table('knowledge_items')
    op.drop_index('ix_messages_thread_id_sent_at', table_name='messages')
    op.drop_index(op.f('ix_messages_author_external_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_knowledge_candidates_thread_id'), table_name='knowledge_candidates')
    op.drop_index(op.f('ix_knowledge_candidates_detection_status'), table_name='knowledge_candidates')
    op.drop_table('knowledge_candidates')
    op.drop_index(op.f('ix_conversation_threads_processing_status'), table_name='conversation_threads')
    op.drop_index('ix_conversation_threads_last_message_at', table_name='conversation_threads')
    op.drop_index(op.f('ix_conversation_threads_communication_source_id'), table_name='conversation_threads')
    op.drop_table('conversation_threads')
    op.drop_index(op.f('ix_incidents_status'), table_name='incidents')
    op.drop_table('incidents')
    op.drop_index(op.f('ix_equipment_site_identifier'), table_name='equipment')
    op.drop_table('equipment')
    op.drop_table('communication_sources')
