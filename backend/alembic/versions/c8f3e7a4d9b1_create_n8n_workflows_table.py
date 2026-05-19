"""create n8n_workflows table

Revision ID: c8f3e7a4d9b1
Revises: e4c105599788
Create Date: 2026-05-19

n8n workflow catalog. Decouples static workflow definitions (name,
URL, RBAC) from runtime execution log (playbook_runs).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8f3e7a4d9b1'
down_revision: Union[str, None] = 'e4c105599788'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'n8n_workflows',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('workflow_url', sa.String(length=500), nullable=False),
        sa.Column(
            'is_active', sa.Boolean(),
            nullable=False, server_default=sa.text('true'),
        ),
        sa.Column(
            'requires_approval', sa.Boolean(),
            nullable=False, server_default=sa.text('false'),
        ),
        sa.Column('allowed_role_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['users.id'], ondelete='SET NULL',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'name', name='uq_n8n_workflow_tenant_name',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_n8n_workflows_tenant_id'),
        'n8n_workflows', ['tenant_id'], unique=False,
    )
    op.create_index(
        'ix_n8n_workflow_tenant_active',
        'n8n_workflows', ['tenant_id', 'is_active'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_n8n_workflow_tenant_active', table_name='n8n_workflows',
    )
    op.drop_index(
        op.f('ix_n8n_workflows_tenant_id'), table_name='n8n_workflows',
    )
    op.drop_table('n8n_workflows')
