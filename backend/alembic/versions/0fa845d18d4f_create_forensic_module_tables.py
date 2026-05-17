"""create forensic module tables

Revision ID: 0fa845d18d4f
Revises: b56fda7a38c6
Create Date: 2026-05-17 09:45:44.214464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fa845d18d4f'
down_revision: Union[str, None] = 'b56fda7a38c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'forensic_artifacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('artifact_type', sa.String(length=20), nullable=False),
        sa.Column('supported_os', sa.JSON(), nullable=False),
        sa.Column('parameters_schema', sa.JSON(), nullable=True),
        sa.Column('is_featured', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_destructive', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('requires_evidence_handling', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('default_timeout_seconds', sa.Integer(), server_default='1800', nullable=False),
        sa.Column('category', sa.String(length=80), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sync_source', sa.String(length=40), server_default='velociraptor_api', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.CheckConstraint(
            "artifact_type IN ('CLIENT', 'SERVER', 'NOTEBOOK', 'CLIENT_EVENT', 'SERVER_EVENT')",
            name='ck_forensic_artifact_type',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_forensic_artifact_tenant_name'),
    )
    op.create_index('ix_forensic_artifact_featured_category', 'forensic_artifacts', ['is_featured', 'category'], unique=False)
    op.create_index(op.f('ix_forensic_artifacts_artifact_type'), 'forensic_artifacts', ['artifact_type'], unique=False)
    op.create_index(op.f('ix_forensic_artifacts_category'), 'forensic_artifacts', ['category'], unique=False)
    op.create_index(op.f('ix_forensic_artifacts_is_featured'), 'forensic_artifacts', ['is_featured'], unique=False)
    op.create_index(op.f('ix_forensic_artifacts_name'), 'forensic_artifacts', ['name'], unique=False)
    op.create_index(op.f('ix_forensic_artifacts_tenant_id'), 'forensic_artifacts', ['tenant_id'], unique=False)

    op.create_table(
        'forensic_hunts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=True),
        sa.Column('artifact_id', sa.String(length=36), nullable=False),
        sa.Column('artifact_name', sa.String(length=300), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('target_clients', sa.JSON(), nullable=False),
        sa.Column('target_label', sa.String(length=500), nullable=True),
        sa.Column('velo_hunt_id', sa.String(length=80), nullable=True),
        sa.Column('velo_org_id', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('launched_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('launched_by_n8n_run_id', sa.String(length=36), nullable=True),
        sa.Column('launched_via', sa.String(length=20), nullable=False),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('result_hash', sa.String(length=64), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('approval_request_id', sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "launched_via IN ('ui_direct', 'ui_via_n8n', 'automation_n8n', 'manual_n8n')",
            name='ck_forensic_hunt_launched_via',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'starting', 'running', 'completed', 'failed', 'timeout', 'cancelled')",
            name='ck_forensic_hunt_status',
        ),
        sa.CheckConstraint(
            'launched_by_user_id IS NOT NULL OR launched_by_n8n_run_id IS NOT NULL',
            name='ck_forensic_hunt_has_launcher',
        ),
        sa.ForeignKeyConstraint(['approval_request_id'], ['approval_requests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['artifact_id'], ['forensic_artifacts.id']),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['launched_by_n8n_run_id'], ['playbook_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['launched_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_forensic_hunt_case_started', 'forensic_hunts', ['case_id', 'started_at'], unique=False)
    op.create_index('ix_forensic_hunt_tenant_status_started', 'forensic_hunts', ['tenant_id', 'status', 'started_at'], unique=False)
    op.create_index(op.f('ix_forensic_hunts_approval_request_id'), 'forensic_hunts', ['approval_request_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunts_artifact_id'), 'forensic_hunts', ['artifact_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunts_case_id'), 'forensic_hunts', ['case_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunts_launched_by_n8n_run_id'), 'forensic_hunts', ['launched_by_n8n_run_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunts_tenant_id'), 'forensic_hunts', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunts_velo_hunt_id'), 'forensic_hunts', ['velo_hunt_id'], unique=False)

    op.create_table(
        'forensic_hunt_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('hunt_id', sa.String(length=36), nullable=False),
        sa.Column('velo_client_id', sa.String(length=80), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('os', sa.String(length=80), nullable=True),
        sa.Column('output_summary', sa.JSON(), nullable=True),
        sa.Column('output_total_rows', sa.Integer(), server_default='0', nullable=False),
        sa.Column('attachments_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('row_hash', sa.String(length=64), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('velo_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'collecting', 'completed', 'failed', 'timeout')",
            name='ck_forensic_hunt_result_status',
        ),
        sa.ForeignKeyConstraint(['hunt_id'], ['forensic_hunts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hunt_id', 'velo_client_id', name='uq_hunt_client'),
    )
    op.create_index('ix_forensic_hunt_result_hunt_status', 'forensic_hunt_results', ['hunt_id', 'status'], unique=False)
    op.create_index(op.f('ix_forensic_hunt_results_hunt_id'), 'forensic_hunt_results', ['hunt_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunt_results_velo_client_id'), 'forensic_hunt_results', ['velo_client_id'], unique=False)

    op.create_table(
        'forensic_hunt_attachments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('hunt_id', sa.String(length=36), nullable=False),
        sa.Column('hunt_result_id', sa.String(length=36), nullable=True),
        sa.Column('attachment_id', sa.String(length=36), nullable=False),
        sa.Column('artifact_name', sa.String(length=300), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('is_immutable', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['attachment_id'], ['case_attachments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['hunt_id'], ['forensic_hunts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['hunt_result_id'], ['forensic_hunt_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hunt_id', 'attachment_id', name='uq_hunt_attachment'),
    )
    op.create_index('ix_forensic_hunt_attachment_hash', 'forensic_hunt_attachments', ['sha256_hash'], unique=False)
    op.create_index(op.f('ix_forensic_hunt_attachments_attachment_id'), 'forensic_hunt_attachments', ['attachment_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunt_attachments_hunt_id'), 'forensic_hunt_attachments', ['hunt_id'], unique=False)
    op.create_index(op.f('ix_forensic_hunt_attachments_hunt_result_id'), 'forensic_hunt_attachments', ['hunt_result_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_forensic_hunt_attachments_hunt_result_id'), table_name='forensic_hunt_attachments')
    op.drop_index(op.f('ix_forensic_hunt_attachments_hunt_id'), table_name='forensic_hunt_attachments')
    op.drop_index(op.f('ix_forensic_hunt_attachments_attachment_id'), table_name='forensic_hunt_attachments')
    op.drop_index('ix_forensic_hunt_attachment_hash', table_name='forensic_hunt_attachments')
    op.drop_table('forensic_hunt_attachments')

    op.drop_index(op.f('ix_forensic_hunt_results_velo_client_id'), table_name='forensic_hunt_results')
    op.drop_index(op.f('ix_forensic_hunt_results_hunt_id'), table_name='forensic_hunt_results')
    op.drop_index('ix_forensic_hunt_result_hunt_status', table_name='forensic_hunt_results')
    op.drop_table('forensic_hunt_results')

    op.drop_index(op.f('ix_forensic_hunts_velo_hunt_id'), table_name='forensic_hunts')
    op.drop_index(op.f('ix_forensic_hunts_tenant_id'), table_name='forensic_hunts')
    op.drop_index(op.f('ix_forensic_hunts_launched_by_n8n_run_id'), table_name='forensic_hunts')
    op.drop_index(op.f('ix_forensic_hunts_case_id'), table_name='forensic_hunts')
    op.drop_index(op.f('ix_forensic_hunts_artifact_id'), table_name='forensic_hunts')
    op.drop_index(op.f('ix_forensic_hunts_approval_request_id'), table_name='forensic_hunts')
    op.drop_index('ix_forensic_hunt_tenant_status_started', table_name='forensic_hunts')
    op.drop_index('ix_forensic_hunt_case_started', table_name='forensic_hunts')
    op.drop_table('forensic_hunts')

    op.drop_index(op.f('ix_forensic_artifacts_tenant_id'), table_name='forensic_artifacts')
    op.drop_index(op.f('ix_forensic_artifacts_name'), table_name='forensic_artifacts')
    op.drop_index(op.f('ix_forensic_artifacts_is_featured'), table_name='forensic_artifacts')
    op.drop_index(op.f('ix_forensic_artifacts_category'), table_name='forensic_artifacts')
    op.drop_index(op.f('ix_forensic_artifacts_artifact_type'), table_name='forensic_artifacts')
    op.drop_index('ix_forensic_artifact_featured_category', table_name='forensic_artifacts')
    op.drop_table('forensic_artifacts')
