"""create integrations module

Revision ID: 272dad9e3794
Revises: e67c8c85446a
Create Date: 2026-05-16

Sub-spec 04 Task 1: 4 tables for inbound integrations & Wazuh adapter.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '272dad9e3794'
down_revision: Union[str, None] = 'e67c8c85446a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── integration_sources ─────────────────────────────────────────────
    op.create_table(
        'integration_sources',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('source_type', sa.String(length=40), nullable=False),
        sa.Column('auth_method', sa.String(length=20), nullable=False),
        sa.Column('auth_secret_encrypted', sa.Text(), nullable=False),
        sa.Column('auth_header_name', sa.String(length=50), nullable=True),
        sa.Column('default_service_item_id', sa.String(length=36), nullable=True),
        sa.Column('default_priority_id', sa.String(length=36), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True),
        sa.Column('last_event_received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_event_processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_events_received', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_events_failed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "auth_method IN ('hmac', 'api_key', 'bearer', 'none')",
            name='ck_source_auth_method',
        ),
        sa.CheckConstraint(
            "source_type IN ('wazuh', 'splunk', 'sentinel', 'crowdstrike', "
            "'qradar', 'wazuh_velociraptor', 'custom')",
            name='ck_source_type',
        ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(
            ['default_priority_id'], ['case_priorities.id'], ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['default_service_item_id'], ['service_catalog_items.id'],
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_integration_sources_tenant_id'),
        'integration_sources', ['tenant_id'], unique=False,
    )
    op.create_index(
        'ix_source_tenant_active',
        'integration_sources', ['tenant_id', 'is_active'], unique=False,
    )

    # ── integration_mappings ────────────────────────────────────────────
    op.create_table(
        'integration_mappings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('target_field', sa.String(length=100), nullable=False),
        sa.Column('json_path', sa.String(length=300), nullable=False),
        sa.Column('transform', sa.String(length=50), nullable=True),
        sa.Column('default_value', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(
            ['source_id'], ['integration_sources.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'source_id', 'target_field', name='uq_mapping_source_field',
        ),
    )
    op.create_index(
        op.f('ix_integration_mappings_source_id'),
        'integration_mappings', ['source_id'], unique=False,
    )

    # ── wazuh_rule_to_taxonomy_map ─────────────────────────────────────
    op.create_table(
        'wazuh_rule_to_taxonomy_map',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('source_id', sa.String(length=36), nullable=True),
        sa.Column('match_strategy', sa.String(length=30), nullable=False),
        sa.Column('match_value', sa.JSON(), nullable=False),
        sa.Column('taxonomy_id', sa.String(length=36), nullable=False),
        sa.Column('priority_order', sa.Integer(), server_default='100', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.CheckConstraint(
            "match_strategy IN ('rule_id', 'rule_groups_any', 'rule_groups_all', "
            "'level_min', 'level_range')",
            name='ck_wazuh_map_strategy',
        ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(
            ['source_id'], ['integration_sources.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['taxonomy_id'], ['security_taxonomies.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_wazuh_map_tenant_active_priority',
        'wazuh_rule_to_taxonomy_map',
        ['tenant_id', 'is_active', 'priority_order'],
        unique=False,
    )
    op.create_index(
        op.f('ix_wazuh_rule_to_taxonomy_map_source_id'),
        'wazuh_rule_to_taxonomy_map', ['source_id'], unique=False,
    )
    op.create_index(
        op.f('ix_wazuh_rule_to_taxonomy_map_taxonomy_id'),
        'wazuh_rule_to_taxonomy_map', ['taxonomy_id'], unique=False,
    )
    op.create_index(
        op.f('ix_wazuh_rule_to_taxonomy_map_tenant_id'),
        'wazuh_rule_to_taxonomy_map', ['tenant_id'], unique=False,
    )

    # ── inbound_events ──────────────────────────────────────────────────
    op.create_table(
        'inbound_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_attempted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed', 'duplicate')",
            name='ck_inbound_status',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(
            ['source_id'], ['integration_sources.id'], ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_inbound_events_case_id'),
        'inbound_events', ['case_id'], unique=False,
    )
    op.create_index(
        op.f('ix_inbound_events_idempotency_key'),
        'inbound_events', ['idempotency_key'], unique=True,
    )
    op.create_index(
        op.f('ix_inbound_events_next_retry_at'),
        'inbound_events', ['next_retry_at'], unique=False,
    )
    op.create_index(
        op.f('ix_inbound_events_received_at'),
        'inbound_events', ['received_at'], unique=False,
    )
    op.create_index(
        op.f('ix_inbound_events_source_id'),
        'inbound_events', ['source_id'], unique=False,
    )
    op.create_index(
        op.f('ix_inbound_events_tenant_id'),
        'inbound_events', ['tenant_id'], unique=False,
    )
    op.create_index(
        'ix_inbound_status_next_retry',
        'inbound_events', ['status', 'next_retry_at'], unique=False,
    )
    op.create_index(
        'ix_inbound_tenant_received',
        'inbound_events', ['tenant_id', 'received_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_inbound_tenant_received', table_name='inbound_events')
    op.drop_index('ix_inbound_status_next_retry', table_name='inbound_events')
    op.drop_index(op.f('ix_inbound_events_tenant_id'), table_name='inbound_events')
    op.drop_index(op.f('ix_inbound_events_source_id'), table_name='inbound_events')
    op.drop_index(op.f('ix_inbound_events_received_at'), table_name='inbound_events')
    op.drop_index(op.f('ix_inbound_events_next_retry_at'), table_name='inbound_events')
    op.drop_index(op.f('ix_inbound_events_idempotency_key'), table_name='inbound_events')
    op.drop_index(op.f('ix_inbound_events_case_id'), table_name='inbound_events')
    op.drop_table('inbound_events')

    op.drop_index(
        op.f('ix_wazuh_rule_to_taxonomy_map_tenant_id'),
        table_name='wazuh_rule_to_taxonomy_map',
    )
    op.drop_index(
        op.f('ix_wazuh_rule_to_taxonomy_map_taxonomy_id'),
        table_name='wazuh_rule_to_taxonomy_map',
    )
    op.drop_index(
        op.f('ix_wazuh_rule_to_taxonomy_map_source_id'),
        table_name='wazuh_rule_to_taxonomy_map',
    )
    op.drop_index(
        'ix_wazuh_map_tenant_active_priority',
        table_name='wazuh_rule_to_taxonomy_map',
    )
    op.drop_table('wazuh_rule_to_taxonomy_map')

    op.drop_index(
        op.f('ix_integration_mappings_source_id'),
        table_name='integration_mappings',
    )
    op.drop_table('integration_mappings')

    op.drop_index('ix_source_tenant_active', table_name='integration_sources')
    op.drop_index(
        op.f('ix_integration_sources_tenant_id'),
        table_name='integration_sources',
    )
    op.drop_table('integration_sources')
