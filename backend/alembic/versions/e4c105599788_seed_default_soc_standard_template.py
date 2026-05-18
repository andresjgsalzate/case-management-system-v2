"""seed default soc_standard template

Revision ID: e4c105599788
Revises: 793d56bc51de
Create Date: 2026-05-18 10:16:21.715849

Sub-spec 08 Task 12: seed a GLOBAL (``tenant_id IS NULL``) ``soc_standard``
alert-report template + its first immutable version. Master spec §7 Phase 3
acceptance lists 8 sections operators expect in any SOC report; this
template wires them up in the canonical order so new tenants get a working
default without admin setup.

Block params match the Pydantic schemas defined in
``alert_reports/application/blocks_catalog.py`` (Task 3). The strict
schemas (``signature``, ``image``, ``text``) reject unknown keys, so the
seed uses the canonical param names from the catalog.

The template is marked ``is_default=True`` so when an operator clicks
"Exportar PDF" without choosing a template, this is what they get.
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa


revision: str = 'e4c105599788'
down_revision: Union[str, None] = '793d56bc51de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUIDs so the seed is idempotent / reproducible.
TEMPLATE_ID = "00000000-0000-0000-0000-aaaaaaaaaaaa"
VERSION_ID = "00000000-0000-0000-0000-bbbbbbbbbbbb"

BLOCKS = [
    {"type": "alert_metadata", "params": {
        "show_repeticiones": True,
        "show_tlp": True,
    }},
    {"type": "priority_calculation", "params": {
        "show_formula_name": True,
        "show_inputs_table": True,
    }},
    {"type": "triage_analysis", "params": {
        "show_taxonomy_chain": True,
    }},
    {"type": "evidence_grid", "params": {
        "include_forensic_hunts": True,
        "include_user_attachments": True,
        "include_iocs": False,
    }},
    {"type": "forensic_artifacts_list", "params": {
        "show_chain_of_custody": True,
    }},
    {"type": "behavior_relation", "params": {}},
    {"type": "mitre_techniques", "params": {
        "include_table": True,
    }},
    {"type": "recommendations", "params": {
        "default_recommendations": [
            "Aislar el host afectado de la red",
            "Rotar credenciales del usuario comprometido",
            "Revisar accesos a sistemas críticos",
        ],
        "show_default_if_empty": True,
    }},
    {"type": "signature", "params": {
        "signers": [
            {"role": "soc_lead", "label": "SOC Lead"},
            {"role": "client", "label": "Cliente"},
        ],
    }},
]

HEADER_CONFIG = {
    "show_logo": True,
    "show_classification": True,
    "show_case_metadata_table": True,
    "title_template": "DESCRIPCIÓN GENERAL DE LA GESTIÓN DE LA ALERTA",
}

FOOTER_CONFIG = {
    "show_page_numbers": True,
    "show_classification_stamp": True,
    "footer_text": "Confidencial — uso interno",
    "show_generation_timestamp": True,
}


def upgrade() -> None:
    conn = op.get_bind()

    # Idempotent: skip if already seeded.
    existing = conn.execute(sa.text(
        "SELECT 1 FROM alert_report_templates WHERE id = :id LIMIT 1"
    ), {"id": TEMPLATE_ID}).fetchone()
    if existing:
        return

    # 1. Insert template head WITHOUT current_version_id (FK target doesn't
    #    exist yet). Updated to point at v1 after the version is inserted.
    conn.execute(sa.text(
        "INSERT INTO alert_report_templates "
        "(id, tenant_id, name, description, code, "
        "current_version_id, current_version_number, "
        "is_default, is_active, "
        "created_by_user_id, created_at, updated_at) "
        "VALUES (:id, NULL, :name, :description, 'soc_standard', "
        "NULL, 0, true, true, NULL, NOW(), NOW())"
    ), {
        "id": TEMPLATE_ID,
        "name": "Reporte SOC estándar",
        "description": (
            "Plantilla global con las 8 secciones del Sub-spec 08 §7 "
            "(alert_metadata, priority_calculation, triage_analysis, "
            "evidence_grid, forensic_artifacts_list, behavior_relation, "
            "mitre_techniques, recommendations, signature)."
        ),
    })

    # 2. Insert v1.
    conn.execute(sa.text(
        "INSERT INTO alert_report_template_versions "
        "(id, template_id, version, name_snapshot, "
        "header_config, footer_config, blocks, css_overrides, "
        "created_by_user_id, created_at, change_summary) "
        "VALUES (:id, :tid, 1, :name, "
        "CAST(:header AS json), CAST(:footer AS json), "
        "CAST(:blocks AS json), NULL, NULL, NOW(), "
        "'Versión inicial sembrada con la migración default-soc-template')"
    ), {
        "id": VERSION_ID,
        "tid": TEMPLATE_ID,
        "name": "Reporte SOC estándar",
        "header": json.dumps(HEADER_CONFIG, ensure_ascii=False),
        "footer": json.dumps(FOOTER_CONFIG, ensure_ascii=False),
        "blocks": json.dumps(BLOCKS, ensure_ascii=False),
    })

    # 3. Point the head at v1.
    conn.execute(sa.text(
        "UPDATE alert_report_templates "
        "SET current_version_id = :vid, current_version_number = 1, "
        "updated_at = NOW() "
        "WHERE id = :tid"
    ), {"vid": VERSION_ID, "tid": TEMPLATE_ID})


def downgrade() -> None:
    op.execute(
        f"UPDATE alert_report_templates "
        f"SET current_version_id = NULL WHERE id = '{TEMPLATE_ID}'"
    )
    op.execute(
        f"DELETE FROM alert_report_template_versions "
        f"WHERE id = '{VERSION_ID}'"
    )
    op.execute(
        f"DELETE FROM alert_report_templates WHERE id = '{TEMPLATE_ID}'"
    )
