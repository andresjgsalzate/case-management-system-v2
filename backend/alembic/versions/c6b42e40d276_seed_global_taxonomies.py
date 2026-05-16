"""seed global taxonomies

Revision ID: c6b42e40d276
Revises: f54597421e0e
Create Date: 2026-05-15 14:15:11.311270

Sub-spec 02 Task 6: seeds ~37 hierarchical global taxonomies per spec §4.2.

Structure: 9 roots + 3 mid-level + 25 leaves. tenant_id = NULL (global).
All deterministic UUIDs via uuid5(NAMESPACE_SOC02, "tuic:" + tuic_code).

managed_by_team_id resolved at runtime from the 'Incidentes - SOC' global team
(seeded in revision f54597421e0e). created_by resolved from the first
admin/super-admin user found; if none exist, the migration aborts cleanly.
"""
import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6b42e40d276'
down_revision: Union[str, None] = 'f54597421e0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NAMESPACE = uuid.UUID("00000000-0000-5000-8000-000000000002")


def _tax_id(tuic_code: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"tuic:{tuic_code}"))


# (tuic_code, name, attack_type, attack_subtype, parent_tuic, default_case_type,
#  requires_ticket, triage_mode, tlp_default, mitre_techniques)
# parent_tuic = None for roots
ROOTS: list[tuple] = [
    ("CODE-MALICIOUS",      "Código Malicioso",  "Código Malicioso", None,        None, "event",    False, "auto", "amber", []),
    ("SOCIAL-ENGINEERING",  "Ingeniería Social", "Ingeniería Social", None,       None, "event",    False, "auto", "amber", []),
    ("INTRUSION",           "Intrusión",         "Intrusión",         None,       None, "event",    False, "auto", "amber", []),
    ("RECONNAISSANCE",      "Reconocimiento",    "Reconocimiento",    None,       None, "event",    False, "auto", "green", []),
    ("AVAILABILITY",        "Disponibilidad",    "Disponibilidad",    None,       None, "event",    False, "auto", "amber", []),
    ("DATA-EXFILTRATION",   "Exfiltración",      "Exfiltración",      None,       None, "incident", True,  "auto", "red",   []),
    ("INSIDER-THREAT",      "Amenaza Interna",   "Amenaza Interna",   None,       None, "incident", True,  "auto", "red",   []),
    ("VULNERABILITY",       "Vulnerabilidad",    "Vulnerabilidad",    None,       None, "event",    False, "auto", "amber", []),
    ("ANOMALOUS-BEHAVIOR",  "Comportamiento Anómalo", "Comportamiento Anómalo", None, None, "event", False, "auto", "amber", []),
]

# Mid-level (parent set to a root)
MIDS: list[tuple] = [
    ("RANSOMWARE",          "Ransomware",        "Código Malicioso", "Ransomware",        "CODE-MALICIOUS",     "incident", True,  "auto", "red",   ["T1486"]),
    ("PHISHING",            "Phishing",          "Ingeniería Social", "Phishing",         "SOCIAL-ENGINEERING", "incident", True,  "auto", "amber", ["T1566"]),
    ("BRUTE-FORCE",         "Brute Force",       "Intrusión",         "Brute Force",      "INTRUSION",          "event",    True,  "auto", "amber", ["T1110"]),
]

# Leaves
LEAVES: list[tuple] = [
    # CODE-MALICIOUS branches
    ("RANSOM-LOCKBIT",      "Ransomware LockBit","Código Malicioso", "Ransomware - LockBit",  "RANSOMWARE",      "incident", True,  "auto", "red",   ["T1486", "T1490"]),
    ("RANSOM-BLACKCAT",     "Ransomware BlackCat","Código Malicioso","Ransomware - BlackCat", "RANSOMWARE",      "incident", True,  "auto", "red",   ["T1486", "T1490"]),
    ("RANSOM-CONTI",        "Ransomware Conti",  "Código Malicioso", "Ransomware - Conti",    "RANSOMWARE",      "incident", True,  "auto", "red",   ["T1486", "T1490"]),
    ("TROJAN",              "Trojan",            "Código Malicioso", "Trojan",                "CODE-MALICIOUS",  "incident", True,  "auto", "red",   ["T1055"]),
    ("WORM",                "Worm",              "Código Malicioso", "Worm",                  "CODE-MALICIOUS",  "incident", True,  "auto", "red",   ["T1210"]),
    ("ROOTKIT",             "Rootkit",           "Código Malicioso", "Rootkit",               "CODE-MALICIOUS",  "incident", True,  "auto", "red",   ["T1014"]),
    # SOCIAL-ENGINEERING branches
    ("PHISH-MAIL",          "Phishing por Email","Ingeniería Social", "Phishing - Email",     "PHISHING",        "incident", True,  "auto", "amber", ["T1566.001"]),
    ("PHISH-SMS",           "Phishing por SMS",  "Ingeniería Social", "Phishing - Smishing",  "PHISHING",        "incident", True,  "auto", "amber", ["T1566.002"]),
    ("PHISH-VOICE",         "Phishing por Voz",  "Ingeniería Social", "Phishing - Vishing",   "PHISHING",        "event",    True,  "auto", "amber", ["T1566.004"]),
    ("BEC",                 "Business Email Compromise", "Ingeniería Social", "BEC",          "SOCIAL-ENGINEERING", "incident", True,  "auto", "red",   ["T1566.003"]),
    ("PRETEXTING",          "Pretexting",        "Ingeniería Social", "Pretexting",           "SOCIAL-ENGINEERING", "event",  False, "auto", "amber", []),
    # INTRUSION branches
    ("BRUTE-AUTH-FAIL",     "Brute Force - Auth Failures", "Intrusión", "Auth Failures",      "BRUTE-FORCE",     "event",    True,  "auto", "amber", ["T1110.001"]),
    ("BRUTE-CRED-STUFFING", "Credential Stuffing", "Intrusión",       "Credential Stuffing",  "BRUTE-FORCE",     "incident", True,  "auto", "red",   ["T1110.004"]),
    ("EXPLOITATION",        "Exploitation",      "Intrusión",         "Exploitation",         "INTRUSION",       "incident", True,  "auto", "red",   ["T1190"]),
    ("LATERAL-MOVEMENT",    "Lateral Movement",  "Intrusión",         "Lateral Movement",     "INTRUSION",       "incident", True,  "auto", "red",   ["T1021"]),
    # RECONNAISSANCE branches
    ("PORT-SCAN",           "Port Scan",         "Reconocimiento",    "Port Scan",            "RECONNAISSANCE",  "event",    False, "auto", "green", ["T1046"]),
    ("ASSET-DISCOVERY",     "Asset Discovery",   "Reconocimiento",    "Asset Discovery",      "RECONNAISSANCE",  "event",    False, "auto", "green", ["T1592"]),
    ("INFO-GATHERING",      "Information Gathering", "Reconocimiento", "Information Gathering","RECONNAISSANCE", "event",    False, "auto", "green", ["T1589"]),
    # AVAILABILITY branches
    ("DDOS",                "DDoS",              "Disponibilidad",    "Distributed Denial of Service", "AVAILABILITY", "incident", True, "auto", "red",   ["T1498"]),
    ("DOS",                 "DoS",               "Disponibilidad",    "Denial of Service",    "AVAILABILITY",    "incident", True,  "auto", "amber", ["T1499"]),
    # DATA-EXFILTRATION branches
    ("DLP-CONFIDENTIAL",        "DLP - Confidencial", "Exfiltración", "Confidential Data",      "DATA-EXFILTRATION", "incident", True, "auto", "red", ["T1041"]),
    ("DLP-PERSONAL-DATA",       "DLP - Datos Personales", "Exfiltración", "Personal Data",     "DATA-EXFILTRATION", "incident", True, "auto", "red", ["T1041"]),
    ("DLP-INTELLECTUAL-PROPERTY","DLP - Propiedad Intelectual", "Exfiltración", "IP",          "DATA-EXFILTRATION", "incident", True, "auto", "red", ["T1041"]),
    # INSIDER-THREAT branches
    ("INSIDER-MISUSE",      "Insider Misuse",    "Amenaza Interna",   "Misuse of Access",     "INSIDER-THREAT",  "incident", True,  "auto", "red",   ["T1078"]),
    ("INSIDER-EXFIL",       "Insider Exfiltration","Amenaza Interna", "Exfil by Insider",     "INSIDER-THREAT",  "incident", True,  "auto", "red",   ["T1052"]),
    # VULNERABILITY branches
    ("VULN-CRITICAL-MISSING-PATCH", "Crítico - Parche Faltante", "Vulnerabilidad", "Missing Critical Patch", "VULNERABILITY", "event", True, "auto", "amber", []),
    ("VULN-MISCONFIG",      "Misconfiguración",  "Vulnerabilidad",    "Misconfiguration",     "VULNERABILITY",   "event",    True,  "auto", "amber", []),
    ("VULN-EOL-SOFTWARE",   "EOL Software",      "Vulnerabilidad",    "End of Life Software", "VULNERABILITY",   "event",    True,  "auto", "amber", []),
    # ANOMALOUS-BEHAVIOR branches
    ("LOGIN-GEO-UNUSUAL",   "Login Geo Inusual", "Comportamiento Anómalo", "Unusual Login Geo", "ANOMALOUS-BEHAVIOR", "event", True, "auto", "amber", ["T1078.004"]),
    ("PRIVILEGE-ESCALATION","Privilege Escalation", "Comportamiento Anómalo", "Privilege Escalation", "ANOMALOUS-BEHAVIOR", "incident", True, "auto", "red", ["T1068"]),
]


def _resolve_managed_team_id(conn) -> str | None:
    row = conn.execute(sa.text(
        "SELECT id FROM teams WHERE tenant_id IS NULL AND name = 'Incidentes - SOC' LIMIT 1"
    )).fetchone()
    return row[0] if row else None


def _resolve_system_user_id(conn) -> str | None:
    """First user from a Super Admin / Admin role, deterministic by created_at."""
    row = conn.execute(sa.text(
        "SELECT u.id FROM users u "
        "JOIN roles r ON r.id = u.role_id "
        "WHERE r.tenant_id IS NULL AND r.name IN ('Super Admin', 'Admin') "
        "ORDER BY u.created_at ASC LIMIT 1"
    )).fetchone()
    return row[0] if row else None


def _insert_taxonomy(
    conn, *, tuic_code, name, attack_type, attack_subtype, parent_id,
    default_case_type, requires_ticket, triage_mode, tlp_default,
    mitre_techniques, managed_by_team_id, created_by,
) -> None:
    existing = conn.execute(sa.text(
        "SELECT 1 FROM security_taxonomies "
        "WHERE tenant_id IS NULL AND tuic_code = :code LIMIT 1"
    ), {"code": tuic_code}).fetchone()
    if existing:
        return
    conn.execute(sa.text(
        "INSERT INTO security_taxonomies "
        "(id, tenant_id, tuic_code, name, description, parent_id, "
        " attack_type, attack_subtype, managed_by_team_id, "
        " default_case_type, requires_ticket, triage_mode, "
        " triage_timeout_seconds, tlp_default, mitre_techniques, "
        " is_active, created_at, updated_at, created_by) "
        "VALUES (:id, NULL, :code, :name, NULL, :parent_id, "
        "        :atype, :asub, :team, "
        "        :case_type, :req_ticket, :triage, "
        "        300, :tlp, CAST(:mitre AS json), "
        "        TRUE, NOW(), NOW(), :created_by)"
    ), {
        "id": _tax_id(tuic_code), "code": tuic_code, "name": name,
        "parent_id": parent_id, "atype": attack_type, "asub": attack_subtype,
        "team": managed_by_team_id, "case_type": default_case_type,
        "req_ticket": requires_ticket, "triage": triage_mode,
        "tlp": tlp_default, "mitre": json.dumps(mitre_techniques),
        "created_by": created_by,
    })


def upgrade() -> None:
    conn = op.get_bind()
    team_id = _resolve_managed_team_id(conn)
    user_id = _resolve_system_user_id(conn)
    if not user_id:
        raise RuntimeError(
            "Cannot seed taxonomies: no Super Admin / Admin user found. "
            "Run user seed first."
        )

    # Pass 1: roots (no parent)
    for (code, name, atype, asub, _parent, case_type, req, triage, tlp, mitre) in ROOTS:
        _insert_taxonomy(
            conn, tuic_code=code, name=name, attack_type=atype, attack_subtype=asub,
            parent_id=None, default_case_type=case_type, requires_ticket=req,
            triage_mode=triage, tlp_default=tlp, mitre_techniques=mitre,
            managed_by_team_id=team_id, created_by=user_id,
        )

    # Pass 2: mids (parent = a root)
    for (code, name, atype, asub, parent_code, case_type, req, triage, tlp, mitre) in MIDS:
        _insert_taxonomy(
            conn, tuic_code=code, name=name, attack_type=atype, attack_subtype=asub,
            parent_id=_tax_id(parent_code) if parent_code else None,
            default_case_type=case_type, requires_ticket=req, triage_mode=triage,
            tlp_default=tlp, mitre_techniques=mitre,
            managed_by_team_id=team_id, created_by=user_id,
        )

    # Pass 3: leaves
    for (code, name, atype, asub, parent_code, case_type, req, triage, tlp, mitre) in LEAVES:
        _insert_taxonomy(
            conn, tuic_code=code, name=name, attack_type=atype, attack_subtype=asub,
            parent_id=_tax_id(parent_code) if parent_code else None,
            default_case_type=case_type, requires_ticket=req, triage_mode=triage,
            tlp_default=tlp, mitre_techniques=mitre,
            managed_by_team_id=team_id, created_by=user_id,
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Delete in reverse order: leaves → mids → roots (FK parent_id SET NULL on parent delete,
    # but we'd rather drop in clean topological order).
    all_codes = (
        [c for (c, *_) in LEAVES]
        + [c for (c, *_) in MIDS]
        + [c for (c, *_) in ROOTS]
    )
    for code in all_codes:
        conn.execute(
            sa.text(
                "DELETE FROM security_taxonomies "
                "WHERE tenant_id IS NULL AND id = :id"
            ),
            {"id": _tax_id(code)},
        )
