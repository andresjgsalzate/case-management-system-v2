"""create n8n_bridge module

Revision ID: 5969cc00a74f
Revises: 7fc159a525e6
Create Date: 2026-05-16

Sub-spec 05 Task 1: 3 tables for n8n bridge.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5969cc00a74f'
down_revision: Union[str, None] = '7fc159a525e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'playbook_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_url', sa.String(length=500), nullable=False),
        sa.Column('workflow_id', sa.String(length=100), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('triggered_by', sa.String(length=40), nullable=False),
        sa.Column('triggered_by_user', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='triggered', nullable=False),
        sa.Column('last_callback_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('callback_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('n8n_execution_id', sa.String(length=100), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('trigger_payload', sa.JSON(), nullable=False),
        sa.Column('final_decision', sa.String(length=40), nullable=True),
        sa.Column('final_decision_data', sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('triggered', 'running', 'completed', 'failed', "
            "'timeout', 'cancelled')",
            name='ck_playbook_run_status',
        ),
        sa.CheckConstraint(
            "triggered_by IN ('auto_triage', 'automation_rule', 'manual', "
            "'approval_resume')",
            name='ck_playbook_run_triggered_by',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by_user'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_playbook_runs_tenant_id'), 'playbook_runs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_playbook_runs_case_id'), 'playbook_runs', ['case_id'], unique=False)
    op.create_index(op.f('ix_playbook_runs_workflow_id'), 'playbook_runs', ['workflow_id'], unique=False)
    op.create_index('ix_playbook_run_case_triggered', 'playbook_runs', ['case_id', 'triggered_at'], unique=False)
    op.create_index('ix_playbook_run_status_triggered', 'playbook_runs', ['status', 'triggered_at'], unique=False)

    op.create_table(
        'approval_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('playbook_run_id', sa.String(length=36), nullable=True),
        sa.Column('requested_action', sa.String(length=500), nullable=False),
        sa.Column('action_category', sa.String(length=50), nullable=False),
        sa.Column('context_payload', sa.JSON(), nullable=False),
        sa.Column('requested_by_workflow', sa.String(length=200), nullable=False),
        sa.Column('resume_url', sa.String(length=500), nullable=False),
        sa.Column('resume_hmac_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('approver_user_id', sa.String(length=36), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_reason', sa.Text(), nullable=True),
        sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resume_attempted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resume_succeeded', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('resume_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'timeout', 'cancelled')",
            name='ck_approval_status',
        ),
        sa.CheckConstraint(
            "(status = 'pending') OR (decided_at IS NOT NULL)",
            name='ck_approval_decided_consistency',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['playbook_run_id'], ['playbook_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approver_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_approval_requests_tenant_id'), 'approval_requests', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_approval_requests_case_id'), 'approval_requests', ['case_id'], unique=False)
    op.create_index(op.f('ix_approval_requests_playbook_run_id'), 'approval_requests', ['playbook_run_id'], unique=False)
    op.create_index('ix_approval_status_timeout', 'approval_requests', ['status', 'timeout_at'], unique=False)
    op.create_index('ix_approval_tenant_status_created', 'approval_requests', ['tenant_id', 'status', 'created_at'], unique=False)

    op.create_table(
        'playbook_run_callbacks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('playbook_run_id', sa.String(length=36), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['playbook_run_id'], ['playbook_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_playbook_run_callbacks_playbook_run_id'), 'playbook_run_callbacks', ['playbook_run_id'], unique=False)
    op.create_index(op.f('ix_playbook_run_callbacks_received_at'), 'playbook_run_callbacks', ['received_at'], unique=False)
    op.create_index('ix_callback_run_received', 'playbook_run_callbacks', ['playbook_run_id', 'received_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_callback_run_received', table_name='playbook_run_callbacks')
    op.drop_index(op.f('ix_playbook_run_callbacks_received_at'), table_name='playbook_run_callbacks')
    op.drop_index(op.f('ix_playbook_run_callbacks_playbook_run_id'), table_name='playbook_run_callbacks')
    op.drop_table('playbook_run_callbacks')

    op.drop_index('ix_approval_tenant_status_created', table_name='approval_requests')
    op.drop_index('ix_approval_status_timeout', table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_playbook_run_id'), table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_case_id'), table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_tenant_id'), table_name='approval_requests')
    op.drop_table('approval_requests')

    op.drop_index('ix_playbook_run_status_triggered', table_name='playbook_runs')
    op.drop_index('ix_playbook_run_case_triggered', table_name='playbook_runs')
    op.drop_index(op.f('ix_playbook_runs_workflow_id'), table_name='playbook_runs')
    op.drop_index(op.f('ix_playbook_runs_case_id'), table_name='playbook_runs')
    op.drop_index(op.f('ix_playbook_runs_tenant_id'), table_name='playbook_runs')
    op.drop_table('playbook_runs')
