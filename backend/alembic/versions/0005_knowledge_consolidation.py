"""Knowledge consolidation: groups, members, relationships, per-item state.

Additive only. Knowledge items themselves are not changed.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07 10:24:15.104060+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('knowledge_groups',
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('summary_data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('summary_fingerprint', sa.String(length=64), nullable=True),
    sa.Column('summary_model', sa.String(length=100), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_groups'))
    )
    op.create_table('knowledge_consolidation_state',
    sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('consolidated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_consolidation_state_knowledge_item_id_knowledge_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('knowledge_item_id', name=op.f('pk_knowledge_consolidation_state'))
    )
    op.create_table('knowledge_group_members',
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.Column('knowledge_item_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['knowledge_groups.id'], name=op.f('fk_knowledge_group_members_group_id_knowledge_groups'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['knowledge_item_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_group_members_knowledge_item_id_knowledge_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_group_members')),
    sa.UniqueConstraint('knowledge_item_id', name=op.f('uq_knowledge_group_members_knowledge_item_id'))
    )
    op.create_index(op.f('ix_knowledge_group_members_group_id'), 'knowledge_group_members', ['group_id'], unique=False)
    op.create_table('knowledge_relationships',
    sa.Column('source_knowledge_id', sa.Uuid(), nullable=False),
    sa.Column('target_knowledge_id', sa.Uuid(), nullable=False),
    sa.Column('relationship_type', sa.String(length=40), nullable=False),
    sa.Column('outcome_comparison', sa.String(length=30), nullable=True),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('shared_symptoms', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('shared_equipment', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('unknown_conditions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('source_evidence_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('target_evidence_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('validation_notes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('model_name', sa.String(length=100), nullable=True),
    sa.Column('pair_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("relationship_type IN ('same_problem', 'supporting_evidence', 'same_problem_different_conditions', 'different_outcome', 'potentially_conflicting', 'related_symptoms', 'unrelated')", name=op.f('ck_knowledge_relationships_relationship_type')),
    sa.CheckConstraint('source_knowledge_id < target_knowledge_id', name=op.f('ck_knowledge_relationships_ordered_pair')),
    sa.ForeignKeyConstraint(['source_knowledge_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_relationships_source_knowledge_id_knowledge_items'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_knowledge_id'], ['knowledge_items.id'], name=op.f('fk_knowledge_relationships_target_knowledge_id_knowledge_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_relationships')),
    sa.UniqueConstraint('source_knowledge_id', 'target_knowledge_id', name=op.f('uq_knowledge_relationships_source_knowledge_id_target_knowledge_id'))
    )
    op.create_index(op.f('ix_knowledge_relationships_relationship_type'), 'knowledge_relationships', ['relationship_type'], unique=False)
    op.create_index(op.f('ix_knowledge_relationships_source_knowledge_id'), 'knowledge_relationships', ['source_knowledge_id'], unique=False)
    op.create_index(op.f('ix_knowledge_relationships_target_knowledge_id'), 'knowledge_relationships', ['target_knowledge_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_knowledge_relationships_target_knowledge_id'), table_name='knowledge_relationships')
    op.drop_index(op.f('ix_knowledge_relationships_source_knowledge_id'), table_name='knowledge_relationships')
    op.drop_index(op.f('ix_knowledge_relationships_relationship_type'), table_name='knowledge_relationships')
    op.drop_table('knowledge_relationships')
    op.drop_index(op.f('ix_knowledge_group_members_group_id'), table_name='knowledge_group_members')
    op.drop_table('knowledge_group_members')
    op.drop_table('knowledge_consolidation_state')
    op.drop_table('knowledge_groups')
