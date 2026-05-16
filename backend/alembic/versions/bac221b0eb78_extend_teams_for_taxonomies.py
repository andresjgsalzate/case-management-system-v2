"""extend teams for taxonomies

Revision ID: bac221b0eb78
Revises: ca11c000da30
Create Date: 2026-05-15 08:51:43.011053

Sub-spec 02 Task 2: adds team_category + is_notification_only to teams.

Excludes unrelated drift detected by autogenerate (smtp_config, email_templates,
case_resolution_requests, etc.) — that drift belongs to other phases and should
be reconciled in dedicated migrations, not as a side-effect of Sub-spec 02.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bac221b0eb78'
down_revision: Union[str, None] = 'ca11c000da30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'teams',
        sa.Column('team_category', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'teams',
        sa.Column(
            'is_notification_only', sa.Boolean(),
            server_default='false', nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('teams', 'is_notification_only')
    op.drop_column('teams', 'team_category')
