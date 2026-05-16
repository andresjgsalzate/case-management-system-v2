"""create prioritization module

Revision ID: 3e2c2ec1cb76
Revises: c6b42e40d276
Create Date: 2026-05-15 21:10:38.582050

Sub-spec 03 Task 1 — creates 6 tables for the prioritization engine.

Excludes unrelated drift detected by autogenerate (legacy indexes, etc.) —
that drift belongs to other phases and should be reconciled in dedicated
migrations, not as a side-effect of Sub-spec 03.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e2c2ec1cb76'
down_revision: Union[str, None] = 'c6b42e40d276'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── prioritization_criteria ──────────────────────────────────────────
    op.create_table(
        'prioritization_criteria',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data_source', sa.String(length=40), nullable=False),
        sa.Column('source_field_key', sa.String(length=100), nullable=True),
        sa.Column('missing_data_strategy', sa.String(length=20),
                  server_default='use_default', nullable=False),
        sa.Column('default_value', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(missing_data_strategy != 'use_default') OR "
            "(default_value IS NOT NULL)",
            name='ck_criterion_default_when_use_default',
        ),
        sa.CheckConstraint(
            "data_source IN ('taxonomy_field', 'asset_field', "
            "'case_custom_value', 'manual_input', 'derived')",
            name='ck_criterion_data_source',
        ),
        sa.CheckConstraint(
            "missing_data_strategy IN ('use_default', 'skip', 'error')",
            name='ck_criterion_missing_strategy',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_criterion_tenant_code'),
    )
    op.create_index(
        op.f('ix_prioritization_criteria_tenant_id'),
        'prioritization_criteria', ['tenant_id'], unique=False,
    )

    # ── prioritization_scales ────────────────────────────────────────────
    op.create_table(
        'prioritization_scales',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('criterion_id', sa.String(length=36), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=False),
        sa.Column('numeric_value', sa.Integer(), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(
            ['criterion_id'], ['prioritization_criteria.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'criterion_id', 'numeric_value', name='uq_scale_criterion_value',
        ),
    )
    op.create_index(
        op.f('ix_prioritization_scales_criterion_id'),
        'prioritization_scales', ['criterion_id'], unique=False,
    )

    # ── prioritization_formulas ──────────────────────────────────────────
    op.create_table(
        'prioritization_formulas',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('logical_key', sa.String(length=100), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('superseded_by_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(
            ['superseded_by_id'], ['prioritization_formulas.id'],
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'logical_key', 'version',
            name='uq_formula_tenant_key_version',
        ),
    )
    op.create_index(
        op.f('ix_prioritization_formulas_logical_key'),
        'prioritization_formulas', ['logical_key'], unique=False,
    )
    op.create_index(
        op.f('ix_prioritization_formulas_tenant_id'),
        'prioritization_formulas', ['tenant_id'], unique=False,
    )
    # Partial unique: only one active formula per (tenant_id, logical_key)
    op.create_index(
        'ux_formula_active',
        'prioritization_formulas', ['tenant_id', 'logical_key'],
        unique=True, postgresql_where=sa.text('is_active = true'),
    )

    # ── prioritization_formula_criteria ──────────────────────────────────
    op.create_table(
        'prioritization_formula_criteria',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('formula_id', sa.String(length=36), nullable=False),
        sa.Column('criterion_id', sa.String(length=36), nullable=False),
        sa.Column('weight', sa.Numeric(3, 2), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.CheckConstraint(
            'weight > 0 AND weight <= 1',
            name='ck_formula_criterion_weight_range',
        ),
        sa.ForeignKeyConstraint(
            ['criterion_id'], ['prioritization_criteria.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['formula_id'], ['prioritization_formulas.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'formula_id', 'criterion_id', name='uq_formula_criterion',
        ),
    )
    op.create_index(
        op.f('ix_prioritization_formula_criteria_criterion_id'),
        'prioritization_formula_criteria', ['criterion_id'], unique=False,
    )
    op.create_index(
        op.f('ix_prioritization_formula_criteria_formula_id'),
        'prioritization_formula_criteria', ['formula_id'], unique=False,
    )

    # ── prioritization_thresholds ────────────────────────────────────────
    op.create_table(
        'prioritization_thresholds',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('formula_id', sa.String(length=36), nullable=False),
        sa.Column('min_value', sa.Numeric(4, 2), nullable=False),
        sa.Column('max_value', sa.Numeric(4, 2), nullable=False),
        sa.Column('priority_id', sa.String(length=36), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.CheckConstraint('min_value <= max_value', name='ck_threshold_min_le_max'),
        sa.CheckConstraint(
            'min_value >= 0 AND max_value <= 100', name='ck_threshold_range',
        ),
        sa.ForeignKeyConstraint(
            ['formula_id'], ['prioritization_formulas.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['priority_id'], ['case_priorities.id'], ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_prioritization_thresholds_formula_id'),
        'prioritization_thresholds', ['formula_id'], unique=False,
    )

    # ── case_priority_calculations ───────────────────────────────────────
    op.create_table(
        'case_priority_calculations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('formula_id', sa.String(length=36), nullable=False),
        sa.Column('formula_version', sa.Integer(), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=False),
        sa.Column('weighted_sum', sa.Numeric(5, 2), nullable=False),
        sa.Column('resulting_priority_id', sa.String(length=36), nullable=False),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('triggered_by', sa.String(length=40), nullable=False),
        sa.Column('triggered_by_user', sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "triggered_by IN ('case_created', 'taxonomy_changed', "
            "'asset_changed', 'manual_recalculation', 'formula_promoted')",
            name='ck_calc_triggered_by',
        ),
        sa.ForeignKeyConstraint(
            ['case_id'], ['cases.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['formula_id'], ['prioritization_formulas.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['resulting_priority_id'], ['case_priorities.id'],
        ),
        sa.ForeignKeyConstraint(
            ['triggered_by_user'], ['users.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_case_priority_calculations_calculated_at'),
        'case_priority_calculations', ['calculated_at'], unique=False,
    )
    op.create_index(
        op.f('ix_case_priority_calculations_case_id'),
        'case_priority_calculations', ['case_id'], unique=False,
    )
    op.create_index(
        'ix_calc_case_calculated_at',
        'case_priority_calculations', ['case_id', 'calculated_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_calc_case_calculated_at', table_name='case_priority_calculations',
    )
    op.drop_index(
        op.f('ix_case_priority_calculations_case_id'),
        table_name='case_priority_calculations',
    )
    op.drop_index(
        op.f('ix_case_priority_calculations_calculated_at'),
        table_name='case_priority_calculations',
    )
    op.drop_table('case_priority_calculations')

    op.drop_index(
        op.f('ix_prioritization_thresholds_formula_id'),
        table_name='prioritization_thresholds',
    )
    op.drop_table('prioritization_thresholds')

    op.drop_index(
        op.f('ix_prioritization_formula_criteria_formula_id'),
        table_name='prioritization_formula_criteria',
    )
    op.drop_index(
        op.f('ix_prioritization_formula_criteria_criterion_id'),
        table_name='prioritization_formula_criteria',
    )
    op.drop_table('prioritization_formula_criteria')

    op.drop_index(
        'ux_formula_active', table_name='prioritization_formulas',
        postgresql_where=sa.text('is_active = true'),
    )
    op.drop_index(
        op.f('ix_prioritization_formulas_tenant_id'),
        table_name='prioritization_formulas',
    )
    op.drop_index(
        op.f('ix_prioritization_formulas_logical_key'),
        table_name='prioritization_formulas',
    )
    op.drop_table('prioritization_formulas')

    op.drop_index(
        op.f('ix_prioritization_scales_criterion_id'),
        table_name='prioritization_scales',
    )
    op.drop_table('prioritization_scales')

    op.drop_index(
        op.f('ix_prioritization_criteria_tenant_id'),
        table_name='prioritization_criteria',
    )
    op.drop_table('prioritization_criteria')
