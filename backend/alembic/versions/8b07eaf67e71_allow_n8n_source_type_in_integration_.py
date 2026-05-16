"""allow n8n source_type in integration_sources

Revision ID: 8b07eaf67e71
Revises: 538c6aad7c8f
Create Date: 2026-05-16

Sub-spec 05 Task 4: n8n is registered in integration_sources like any other
source, but the original CheckConstraint from Sub-spec 04 didn't include
'n8n'. Recreate it with the extra value.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '8b07eaf67e71'
down_revision: Union[str, None] = '538c6aad7c8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_source_type", "integration_sources", type_="check",
    )
    op.create_check_constraint(
        "ck_source_type", "integration_sources",
        "source_type IN ('wazuh', 'splunk', 'sentinel', 'crowdstrike', "
        "'qradar', 'wazuh_velociraptor', 'n8n', 'custom')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_source_type", "integration_sources", type_="check",
    )
    op.create_check_constraint(
        "ck_source_type", "integration_sources",
        "source_type IN ('wazuh', 'splunk', 'sentinel', 'crowdstrike', "
        "'qradar', 'wazuh_velociraptor', 'custom')",
    )
