"""create security_taxonomies module

Revision ID: ca11c000da30
Revises: 2d08492eb261
Create Date: 2026-05-15 08:43:11.490961

Sub-spec 02 — creates 4 tables for taxonomies, audit log, notifications, mappings.
Note: prioritization_formula_id is plain String(36); FK constraint added by Sub-spec 03 migration.

This migration intentionally does NOT clean up unrelated drift detected by autogenerate
(removed smtp_config, email_templates, etc.) — that drift belongs to other phases and
should be reconciled in dedicated migrations, not as a side-effect of Sub-spec 02.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca11c000da30'
down_revision: Union[str, None] = '2d08492eb261'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── security_taxonomies ──────────────────────────────────────────────
    op.create_table(
        'security_taxonomies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('tuic_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.String(length=36), nullable=True),
        sa.Column('attack_type', sa.String(length=100), nullable=True),
        sa.Column('attack_subtype', sa.String(length=100), nullable=True),
        sa.Column('internal_impact_context', sa.Text(), nullable=True),
        sa.Column('external_impact_context', sa.Text(), nullable=True),
        sa.Column('managed_by_team_id', sa.String(length=36), nullable=True),
        sa.Column('default_case_type', sa.String(length=20), server_default='event', nullable=False),
        sa.Column('requires_ticket', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('triage_mode', sa.String(length=20), server_default='auto', nullable=False),
        sa.Column('delegated_workflow_id', sa.String(length=100), nullable=True),
        sa.Column('triage_timeout_seconds', sa.Integer(), server_default='300', nullable=False),
        sa.Column('tlp_default', sa.String(length=20), server_default='amber', nullable=False),
        sa.Column('prioritization_formula_id', sa.String(length=36), nullable=True),
        sa.Column('mitre_techniques', sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('forked_from_global_id', sa.String(length=36), nullable=True),
        sa.Column('forked_from_global_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "(triage_mode = 'auto') OR "
            "(triage_mode = 'delegate_to_n8n' AND delegated_workflow_id IS NOT NULL)",
            name='ck_taxonomy_delegate_requires_workflow'
        ),
        sa.CheckConstraint(
            "default_case_type IN ('event', 'incident')",
            name='ck_taxonomy_default_case_type'
        ),
        sa.CheckConstraint(
            "tlp_default IN ('white', 'green', 'amber', 'red')",
            name='ck_taxonomy_tlp'
        ),
        sa.CheckConstraint(
            "triage_mode IN ('auto', 'delegate_to_n8n')",
            name='ck_taxonomy_triage_mode'
        ),
        sa.CheckConstraint(
            '(forked_from_global_id IS NULL AND forked_from_global_at IS NULL) OR '
            '(forked_from_global_id IS NOT NULL AND forked_from_global_at IS NOT NULL)',
            name='ck_taxonomy_fork_consistency'
        ),
        sa.CheckConstraint(
            '(forked_from_global_id IS NULL) OR (tenant_id IS NOT NULL)',
            name='ck_taxonomy_fork_requires_tenant'
        ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['forked_from_global_id'], ['security_taxonomies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['managed_by_team_id'], ['teams.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parent_id'], ['security_taxonomies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'tuic_code', name='uq_taxonomy_tenant_tuic'),
    )
    op.create_index(op.f('ix_security_taxonomies_parent_id'), 'security_taxonomies', ['parent_id'], unique=False)
    op.create_index(op.f('ix_security_taxonomies_tenant_id'), 'security_taxonomies', ['tenant_id'], unique=False)
    op.create_index('ix_taxonomy_parent', 'security_taxonomies', ['parent_id'], unique=False)
    op.create_index('ix_taxonomy_tenant_active', 'security_taxonomies', ['tenant_id', 'is_active'], unique=False)

    # ── security_taxonomies_audit_log ────────────────────────────────────
    op.create_table(
        'security_taxonomies_audit_log',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('taxonomy_id', sa.String(length=36), nullable=False),
        sa.Column('changed_by', sa.String(length=36), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('change_type', sa.String(length=30), nullable=False),
        sa.Column('field_changes', sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "change_type IN ('created', 'updated', 'soft_deleted', "
            "'activated', 'forked', 'refreshed_from_global')",
            name='ck_taxonomy_audit_change_type'
        ),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['taxonomy_id'], ['security_taxonomies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_security_taxonomies_audit_log_changed_at'),
        'security_taxonomies_audit_log', ['changed_at'], unique=False,
    )
    op.create_index(
        op.f('ix_security_taxonomies_audit_log_taxonomy_id'),
        'security_taxonomies_audit_log', ['taxonomy_id'], unique=False,
    )
    op.create_index(
        'ix_taxonomy_audit_taxonomy_changed_at',
        'security_taxonomies_audit_log', ['taxonomy_id', 'changed_at'], unique=False,
    )

    # ── taxonomy_catalog_mappings ────────────────────────────────────────
    op.create_table(
        'taxonomy_catalog_mappings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('taxonomy_id', sa.String(length=36), nullable=False),
        sa.Column('service_catalog_item_id', sa.String(length=36), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('priority_order', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(
            ['service_catalog_item_id'], ['service_catalog_items.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(['taxonomy_id'], ['security_taxonomies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('taxonomy_id', 'service_catalog_item_id', name='uq_taxonomy_catalog_map'),
    )
    op.create_index(
        op.f('ix_taxonomy_catalog_mappings_service_catalog_item_id'),
        'taxonomy_catalog_mappings', ['service_catalog_item_id'], unique=False,
    )
    op.create_index(
        op.f('ix_taxonomy_catalog_mappings_taxonomy_id'),
        'taxonomy_catalog_mappings', ['taxonomy_id'], unique=False,
    )
    op.create_index(
        'ux_taxonomy_default', 'taxonomy_catalog_mappings', ['taxonomy_id'],
        unique=True, postgresql_where=sa.text('is_default = true'),
    )

    # ── taxonomy_notifications ───────────────────────────────────────────
    op.create_table(
        'taxonomy_notifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('taxonomy_id', sa.String(length=36), nullable=False),
        sa.Column('team_id', sa.String(length=36), nullable=False),
        sa.Column('notify_phase', sa.String(length=40), nullable=False),
        sa.Column('notify_channel', sa.String(length=20), server_default='email', nullable=False),
        sa.Column('escalation_minutes', sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "notify_channel IN ('email', 'chat', 'sms', 'all')",
            name='ck_taxonomy_notif_channel'
        ),
        sa.CheckConstraint(
            "notify_phase IN ('triage', 'created', 'critical_priority', "
            "'sla_breach', 'resolved', 'promoted')",
            name='ck_taxonomy_notif_phase'
        ),
        sa.ForeignKeyConstraint(['taxonomy_id'], ['security_taxonomies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'taxonomy_id', 'team_id', 'notify_phase',
            name='uq_taxonomy_notif_tax_team_phase',
        ),
    )
    op.create_index(
        op.f('ix_taxonomy_notifications_taxonomy_id'),
        'taxonomy_notifications', ['taxonomy_id'], unique=False,
    )
    op.create_index(
        op.f('ix_taxonomy_notifications_team_id'),
        'taxonomy_notifications', ['team_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_taxonomy_notifications_team_id'), table_name='taxonomy_notifications')
    op.drop_index(op.f('ix_taxonomy_notifications_taxonomy_id'), table_name='taxonomy_notifications')
    op.drop_table('taxonomy_notifications')

    op.drop_index('ux_taxonomy_default', table_name='taxonomy_catalog_mappings',
                  postgresql_where=sa.text('is_default = true'))
    op.drop_index(op.f('ix_taxonomy_catalog_mappings_taxonomy_id'), table_name='taxonomy_catalog_mappings')
    op.drop_index(op.f('ix_taxonomy_catalog_mappings_service_catalog_item_id'),
                  table_name='taxonomy_catalog_mappings')
    op.drop_table('taxonomy_catalog_mappings')

    op.drop_index('ix_taxonomy_audit_taxonomy_changed_at', table_name='security_taxonomies_audit_log')
    op.drop_index(op.f('ix_security_taxonomies_audit_log_taxonomy_id'),
                  table_name='security_taxonomies_audit_log')
    op.drop_index(op.f('ix_security_taxonomies_audit_log_changed_at'),
                  table_name='security_taxonomies_audit_log')
    op.drop_table('security_taxonomies_audit_log')

    op.drop_index('ix_taxonomy_tenant_active', table_name='security_taxonomies')
    op.drop_index('ix_taxonomy_parent', table_name='security_taxonomies')
    op.drop_index(op.f('ix_security_taxonomies_tenant_id'), table_name='security_taxonomies')
    op.drop_index(op.f('ix_security_taxonomies_parent_id'), table_name='security_taxonomies')
    op.drop_table('security_taxonomies')
