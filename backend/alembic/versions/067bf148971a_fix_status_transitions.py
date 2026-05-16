"""fix case status allowed_transitions

Revision ID: 067bf148971a
Revises: edc560328b53
Create Date: 2026-04-15

Remove 'closed' from 'open' and 'pending' allowed_transitions so that
only 'resolved' can transition to 'closed'.
"""
import json
from alembic import op
import sqlalchemy as sa

revision = "067bf148971a"
down_revision = "edc560328b53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # open: ["in_progress", "closed"] → ["in_progress"]
    conn.execute(
        sa.text(
            "UPDATE case_statuses SET allowed_transitions = :t WHERE slug = 'open' AND tenant_id IS NULL"
        ),
        {"t": json.dumps(["in_progress"])},
    )

    # pending: ["in_progress", "closed"] → ["in_progress", "open"]
    conn.execute(
        sa.text(
            "UPDATE case_statuses SET allowed_transitions = :t WHERE slug = 'pending' AND tenant_id IS NULL"
        ),
        {"t": json.dumps(["in_progress", "open"])},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE case_statuses SET allowed_transitions = :t WHERE slug = 'open' AND tenant_id IS NULL"
        ),
        {"t": json.dumps(["in_progress", "closed"])},
    )
    conn.execute(
        sa.text(
            "UPDATE case_statuses SET allowed_transitions = :t WHERE slug = 'pending' AND tenant_id IS NULL"
        ),
        {"t": json.dumps(["in_progress", "closed"])},
    )
