"""cleanup stale SLA breaches on closed/archived cases

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-04-24

One-shot data migration: limpia is_breached=true que el antiguo job dejó marcado
en SLAs de casos ya archivados o en estados finales. A partir de esta migración,
el nuevo check_sla_breaches ya no los volverá a marcar.
"""
from alembic import op


revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Limpia SLA de casos archivados
    op.execute("""
        UPDATE sla_records sr
        SET is_breached = false,
            breached_at = NULL
        FROM cases c
        WHERE c.id = sr.case_id
          AND c.is_archived = true
          AND sr.is_breached = true
    """)
    # Limpia SLA de casos en estados finales (ej. Cerrado)
    op.execute("""
        UPDATE sla_records sr
        SET is_breached = false,
            breached_at = NULL
        FROM cases c
        JOIN case_statuses cs ON cs.id = c.status_id
        WHERE c.id = sr.case_id
          AND cs.is_final = true
          AND sr.is_breached = true
    """)


def downgrade() -> None:
    # Los datos corregidos no son reconstruibles — los valores previos eran
    # incorrectos. Downgrade no-op.
    pass
