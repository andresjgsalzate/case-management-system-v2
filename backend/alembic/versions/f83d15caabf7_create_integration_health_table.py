"""create integration_health table

Revision ID: f83d15caabf7
Revises: 8b07eaf67e71
Create Date: 2026-05-16

Sub-spec 06 Task 1: single table for per-source 5-minute health snapshots.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f83d15caabf7'
down_revision: Union[str, None] = '8b07eaf67e71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'integration_health',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('events_received_5min', sa.Integer(), nullable=False),
        sa.Column('events_processed_5min', sa.Integer(), nullable=False),
        sa.Column('events_failed_5min', sa.Integer(), nullable=False),
        sa.Column('avg_latency_ms_5min', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('extra_metrics', sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('healthy', 'degraded', 'down')",
            name='ck_int_health_status',
        ),
        sa.ForeignKeyConstraint(
            ['source_id'], ['integration_sources.id'], ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_integration_health_source_id'),
        'integration_health', ['source_id'], unique=False,
    )
    op.create_index(
        op.f('ix_integration_health_recorded_at'),
        'integration_health', ['recorded_at'], unique=False,
    )
    op.create_index(
        'ix_int_health_source_recorded',
        'integration_health', ['source_id', 'recorded_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_int_health_source_recorded', table_name='integration_health',
    )
    op.drop_index(
        op.f('ix_integration_health_recorded_at'),
        table_name='integration_health',
    )
    op.drop_index(
        op.f('ix_integration_health_source_id'),
        table_name='integration_health',
    )
    op.drop_table('integration_health')
