"""Seed the CMS catalog + automation rule needed to test the
case.created -> n8n notification flow end-to-end.

Creates (idempotent):

  1. n8n_workflows row: registers the existing n8n webhook in CMS so
     automation rules can reference it by id.
  2. automation_rules row: trigger_event=case.created, conditions=[]
     (fires on every case), actions=[{trigger_n8n_workflow,
     workflow_id=<#1's id>, recipient_email=<address>}].

After running this + creating a case in the UI, CMS publishes
case.created -> AutomationEngine matches the rule -> POSTs to the
n8n webhook -> n8n sends the email via the Hostinger SMTP credential
already wired in.

Run: python3 scripts/seed_test_automation.py
"""
from __future__ import annotations

import os
import sys
import uuid
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import Json


N8N_WEBHOOK_URL = "https://cms.local/webhook/notify-email-on-case-created"
N8N_WORKFLOW_NAME = "notify-email-on-case-created"
N8N_INTERNAL_ID = "IFxWqIEU0k6tjlIs"  # the id assigned by n8n at creation
RECIPIENT_EMAIL = "tecnologia@andresjgsalzate.com"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = "backend/.env"
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k] = v.strip('"').strip("'")
    return env


def _connect():
    url = _load_env().get("DATABASE_URL", "")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not url:
        url = "postgresql://cms_user:cms_password@localhost:5433/cms_dev"
    return psycopg2.connect(url)


@contextmanager
def _tx(conn):
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _pick_admin_user(cur) -> str:
    """Find any admin/superuser to attribute as creator of seed rows.

    Falls back to the first user in the table. created_by_id is a FK
    that we need *something* valid in, but the value isn't semantically
    important for an auto-seeded rule.
    """
    cur.execute("SELECT id FROM users ORDER BY created_at ASC LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise SystemExit("No users in DB -- bootstrap a user first")
    return row[0]


def _seed_n8n_workflow_catalog(cur, admin_user_id: str) -> str:
    """Register the n8n webhook in the CMS catalog. Returns the catalog
    row id (UUID) -- this is what the automation rule will reference.
    """
    cur.execute(
        "SELECT id FROM n8n_workflows WHERE tenant_id IS NULL AND name = %s",
        (N8N_WORKFLOW_NAME,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    wid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO n8n_workflows
          (id, tenant_id, name, description, workflow_url, is_active,
           requires_approval, allowed_role_ids,
           n8n_workflow_id, created_by_user_id, created_at, updated_at)
        VALUES
          (%s, NULL, %s, %s, %s, true,
           false, NULL,
           %s, %s, NOW(), NOW())
        """,
        (
            wid, N8N_WORKFLOW_NAME,
            "Sends an email when a new case is created (test workflow).",
            N8N_WEBHOOK_URL,
            N8N_INTERNAL_ID, admin_user_id,
        ),
    )
    return wid


def _seed_automation_rule(
    cur, admin_user_id: str, workflow_catalog_id: str
) -> str:
    """Create the rule that wires case.created -> trigger_n8n_workflow.

    Conditions are intentionally empty: every case-created event fires
    this rule (we're testing the whole loop, not filtering). To narrow
    the scope later, add a condition like:
      {"field": "service_catalog_item_id", "operator": "equals",
       "value": "<some-uuid>"}
    """
    rule_name = "Test: notify email on case.created"
    cur.execute(
        "SELECT id FROM automation_rules WHERE tenant_id IS NULL AND name = %s",
        (rule_name,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    rid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO automation_rules
          (id, name, description, trigger_event,
           conditions, actions, condition_logic,
           is_active, execution_count,
           created_by_id, created_at, updated_at, tenant_id)
        VALUES
          (%s, %s, %s, %s,
           %s, %s, %s,
           true, 0,
           %s, NOW(), NOW(), NULL)
        """,
        (
            rid, rule_name,
            "Fires on every case.created event. Posts the enriched case "
            "payload to the notify-email n8n webhook. Smoke test for the "
            "CMS->n8n automation loop.",
            "case.created",
            Json([]),
            Json([
                {
                    "action_type": "trigger_n8n_workflow",
                    "params": {
                        "workflow_id": workflow_catalog_id,
                        "recipient_email": RECIPIENT_EMAIL,
                    },
                }
            ]),
            "AND",
            admin_user_id,
        ),
    )
    return rid


def main() -> None:
    conn = _connect()
    try:
        with _tx(conn) as cur:
            admin_id = _pick_admin_user(cur)
            print(f"Admin user_id (for created_by): {admin_id}")
            wf_catalog_id = _seed_n8n_workflow_catalog(cur, admin_id)
            print(f"n8n_workflows row: {wf_catalog_id}")
            rule_id = _seed_automation_rule(cur, admin_id, wf_catalog_id)
            print(f"automation_rules row: {rule_id}")
            print()
            print("Seed complete. Create a case in the UI to trigger the flow:")
            print("  1. UI: /cases -> Nuevo caso -> guardar")
            print("  2. Backend logs should show: 'trigger_n8n_workflow: posted to...'")
            print(
                f"  3. Mailbox {RECIPIENT_EMAIL} receives the notification email"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
