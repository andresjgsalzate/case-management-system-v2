"""triage module: 4 tables (case_triages + 3 catalog tables)

Revision ID: e2a7c3f9b1d4
Revises: d9a8c1f6e4b2
Create Date: 2026-05-24

Backend foundation for the SOC triage feature (docs/specs/triage.md
phase 2). Adds:

  - triage_tool_types      — catalog: FW Externo, EDR, ... (xlsx Herramientas)
  - triage_tool_actions    — catalog: Monitoreo, Bloqueo
  - triage_sla_policies    — catalog: priority -> notification SLA minutes
  - case_triages           — main: one row per triage revision of a case

case_triages stores a snapshot of the case at triage time (case_title_snapshot,
case_tenant_name_snapshot) to avoid drift if the case is later edited; the
calculated_priority_id + calculated_sla_minutes are denormalised for fast
reporting without re-running the prioritization formula.

UNIQUE (case_id, version) lets callers fetch the latest by ORDER BY version DESC.

All catalog tables follow the tenant_id NULL = global pattern used throughout.
"""
from alembic import op
import sqlalchemy as sa


revision = "e2a7c3f9b1d4"
down_revision = "d9a8c1f6e4b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── triage_tool_types ───────────────────────────────────────────
    op.create_table(
        "triage_tool_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tool_type_tenant_name"),
    )

    # ── triage_tool_actions ─────────────────────────────────────────
    op.create_table(
        "triage_tool_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tool_action_tenant_name"),
    )

    # ── triage_sla_policies ─────────────────────────────────────────
    op.create_table(
        "triage_sla_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column(
            "priority_id", sa.String(36),
            sa.ForeignKey("case_priorities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # NULL = N/A (used for Falso Positivo).
        sa.Column("sla_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id", "priority_id", name="uq_sla_policy_tenant_priority"
        ),
    )

    # ── case_triages (main) ─────────────────────────────────────────
    op.create_table(
        "case_triages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id", sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "triaged_by_user_id", sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "triaged_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),

        # Snapshots of fields that may drift after triage. Kept verbatim so
        # historical reports show what the analyst actually saw.
        sa.Column("case_title_snapshot", sa.String(500), nullable=False),
        sa.Column("case_tenant_name_snapshot", sa.String(200), nullable=True),

        # Classification (sub_taxonomy_id is the leaf; parent inferred from it)
        sa.Column(
            "sub_taxonomy_id", sa.String(36),
            sa.ForeignKey("security_taxonomies.id"),
            nullable=False,
        ),

        # Fixed enums (Pydantic Literal enforced app-side; CHECK enforced DB-side)
        sa.Column("alert_severity", sa.String(20), nullable=False),
        sa.Column("context_origin_type", sa.String(20), nullable=False),
        sa.Column("asset_criticality", sa.String(20), nullable=False),

        # Parameterised catalog FKs
        sa.Column(
            "tool_type_id", sa.String(36),
            sa.ForeignKey("triage_tool_types.id"),
            nullable=True,
        ),
        sa.Column(
            "tool_action_id", sa.String(36),
            sa.ForeignKey("triage_tool_actions.id"),
            nullable=True,
        ),

        # Free-form fields
        sa.Column("context_origin_detail", sa.String(500), nullable=True),
        sa.Column("related_asset", sa.String(500), nullable=True),
        sa.Column("alert_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("alert_repetitions", sa.Integer(), nullable=False, server_default="1"),

        # Narratives
        sa.Column("analysis_narrative", sa.Text(), nullable=True),
        sa.Column("behavior_narrative", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.Text(), nullable=True),

        # Semantic attachments (point to existing case_attachments rows)
        sa.Column(
            "evidence_attachment_id", sa.String(36),
            sa.ForeignKey("case_attachments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "behavior_attachment_id", sa.String(36),
            sa.ForeignKey("case_attachments.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Calculation result (denormalised for fast list/reporting)
        sa.Column(
            "calculated_priority_id", sa.String(36),
            sa.ForeignKey("case_priorities.id"),
            nullable=True,
        ),
        sa.Column(
            "calculated_score", sa.Numeric(precision=4, scale=2), nullable=True
        ),
        sa.Column("calculated_sla_minutes", sa.Integer(), nullable=True),

        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),

        sa.UniqueConstraint("case_id", "version", name="uq_triage_case_version"),
        sa.CheckConstraint(
            "alert_severity IN ('critico', 'alto', 'medio', 'bajo', 'falso_positivo')",
            name="ck_triage_alert_severity",
        ),
        sa.CheckConstraint(
            "context_origin_type IN ('origen_interno', 'origen_externo')",
            name="ck_triage_context_origin_type",
        ),
        sa.CheckConstraint(
            "asset_criticality IN ('critico', 'alto', 'medio', 'bajo')",
            name="ck_triage_asset_criticality",
        ),
    )


def downgrade() -> None:
    op.drop_table("case_triages")
    op.drop_table("triage_sla_policies")
    op.drop_table("triage_tool_actions")
    op.drop_table("triage_tool_types")
