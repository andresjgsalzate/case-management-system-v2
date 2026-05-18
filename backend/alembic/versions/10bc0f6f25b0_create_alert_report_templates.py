"""create alert_report_templates + versions + generated_reports

Revision ID: 10bc0f6f25b0
Revises: 742f55a16be3
Create Date: 2026-05-17 20:50:30.903107

Sub-spec 08 Task 1. Three tables with a circular FK between
``alert_report_templates.current_version_id`` and
``alert_report_template_versions.id`` — resolved via ``use_alter=True``
which defers the constraint creation until after both tables exist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10bc0f6f25b0'
down_revision: Union[str, None] = '742f55a16be3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alert_report_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('current_version_id', sa.String(length=36), nullable=True),
        sa.Column('current_version_number', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(
            ['current_version_id'],
            ['alert_report_template_versions.id'],
            name='fk_alert_report_template_current_version',
            use_alter=True,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'code',
            name='uq_alert_report_template_tenant_code',
        ),
    )
    op.create_index(
        op.f('ix_alert_report_templates_tenant_id'),
        'alert_report_templates', ['tenant_id'], unique=False,
    )
    op.create_index(
        'ux_alert_report_template_default_per_tenant',
        'alert_report_templates', ['tenant_id'], unique=True,
        postgresql_where=sa.text('is_default IS TRUE AND is_active IS TRUE'),
    )

    op.create_table(
        'alert_report_template_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name_snapshot', sa.String(length=200), nullable=False),
        sa.Column('header_config', sa.JSON(), nullable=False),
        sa.Column('footer_config', sa.JSON(), nullable=False),
        sa.Column('blocks', sa.JSON(), nullable=False),
        sa.Column('css_overrides', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(
            ['template_id'], ['alert_report_templates.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'template_id', 'version', name='uq_template_version',
        ),
    )
    op.create_index(
        op.f('ix_alert_report_template_versions_template_id'),
        'alert_report_template_versions', ['template_id'], unique=False,
    )
    op.create_index(
        'ix_template_version_template_created',
        'alert_report_template_versions',
        ['template_id', 'created_at'], unique=False,
    )

    op.create_table(
        'case_generated_reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=False),
        sa.Column('template_version_id', sa.String(length=36), nullable=False),
        sa.Column('template_version_number', sa.Integer(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('generated_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('generated_by_n8n_run_id', sa.String(length=36), nullable=True),
        sa.Column('generated_via', sa.String(length=20), nullable=False),
        sa.Column('attachment_id', sa.String(length=36), nullable=False),
        sa.Column('pdf_sha256', sa.String(length=64), nullable=False),
        sa.Column('pdf_size_bytes', sa.Integer(), nullable=False),
        sa.Column('data_snapshot', sa.JSON(), nullable=False),
        sa.Column('generation_context', sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "generated_via IN ('manual_ui', 'n8n_api')",
            name='ck_generated_report_via',
        ),
        sa.CheckConstraint(
            'generated_by_user_id IS NOT NULL OR '
            'generated_by_n8n_run_id IS NOT NULL',
            name='ck_generated_report_has_actor',
        ),
        sa.ForeignKeyConstraint(
            ['attachment_id'], ['case_attachments.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['generated_by_n8n_run_id'], ['playbook_runs.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['template_id'], ['alert_report_templates.id']),
        sa.ForeignKeyConstraint(
            ['template_version_id'],
            ['alert_report_template_versions.id'],
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_case_generated_reports_case_id'),
        'case_generated_reports', ['case_id'], unique=False,
    )
    op.create_index(
        op.f('ix_case_generated_reports_tenant_id'),
        'case_generated_reports', ['tenant_id'], unique=False,
    )
    op.create_index(
        'ix_generated_report_case_generated',
        'case_generated_reports',
        ['case_id', 'generated_at'], unique=False,
    )
    op.create_index(
        'ix_generated_report_tenant_generated',
        'case_generated_reports',
        ['tenant_id', 'generated_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_generated_report_tenant_generated',
        table_name='case_generated_reports',
    )
    op.drop_index(
        'ix_generated_report_case_generated',
        table_name='case_generated_reports',
    )
    op.drop_index(
        op.f('ix_case_generated_reports_tenant_id'),
        table_name='case_generated_reports',
    )
    op.drop_index(
        op.f('ix_case_generated_reports_case_id'),
        table_name='case_generated_reports',
    )
    op.drop_table('case_generated_reports')

    op.drop_index(
        'ix_template_version_template_created',
        table_name='alert_report_template_versions',
    )
    op.drop_index(
        op.f('ix_alert_report_template_versions_template_id'),
        table_name='alert_report_template_versions',
    )
    op.drop_table('alert_report_template_versions')

    op.drop_index(
        'ux_alert_report_template_default_per_tenant',
        table_name='alert_report_templates',
        postgresql_where=sa.text('is_default IS TRUE AND is_active IS TRUE'),
    )
    op.drop_index(
        op.f('ix_alert_report_templates_tenant_id'),
        table_name='alert_report_templates',
    )
    op.drop_table('alert_report_templates')
