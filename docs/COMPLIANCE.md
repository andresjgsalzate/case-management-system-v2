# Compliance — Compensating Controls

This document records compensating controls in effect while specific
parts of the CMS run on configurations that don't natively satisfy a
SOC2 / ISO27001 requirement. Each entry includes the scope, the
control statement, when it became effective, and the criterion that
retires it.

The intent is to leave an audit trail an external assessor can read
without spelunking through Slack history.

---

## 1. n8n editor — single-admin model

**Status:** Active
**Effective date:** 2026-05-22
**Sub-spec:** `2026-05-19-n8n-iframe-embed-design.md` §3.9
**Plan:** `2026-05-19-n8n-iframe-embed.md` Phase 4

### Scope

n8n is embedded in CMS via the `/n8n` iframe route (sub-spec 09).
On the **Community plan** n8n has no per-user audit log and no role
model — every editor action is attributed to a single OS-level user.

If multiple admins were granted editor access, an assessor reviewing
the n8n change history could not tell which human actor made a given
modification. That fails SOC2 CC6.1 (Logical Access — Identification
and Authentication) and ISO27001 A.9.4.1 (Information Access
Restriction).

### Control statement

Only **one** named user holds the CMS permission
`n8n_editor:access`. All other admins propose workflow changes
through the **Workflow Change Request** tracker at
`/settings/workflow-change-requests`.

Each WCR row captures:

- `requested_by` — the admin proposing the change
- `proposed_change` — JSON description of the modification
- `reviewed_by` + `reviewed_at` + `review_notes` — the single editor's
  decision and rationale
- `implemented_at` + `implemented_in_workflow_url` — link to the
  realised workflow once applied

The WCR audit trail therefore reconstructs who proposed, who
approved, and who applied every n8n change, independent of n8n's
own (single-user) history.

The role/permission grant is enforced at three layers:

1. Alembic seed `a09b4d3e7f12_seed_n8n_editor_permission.py` grants
   `n8n_editor:access` only to the **Super Admin** role.
2. The CMS frontend gates the `/n8n` route and all deep-link buttons
   via `usePermissionGuard` / `useHasPermission`.
3. The backend `PermissionChecker` re-validates the permission on
   every API call against the same DB rows.

### Evidence

- Permission grants:
  ```sql
  SELECT r.name, p.module, p.action
  FROM permissions p JOIN roles r ON r.id = p.role_id
  WHERE p.module IN ('n8n_editor', 'workflow_change_requests')
  ORDER BY r.name, p.module, p.action;
  ```
- Activity log:
  ```sql
  SELECT requested_by, status, requested_at, reviewed_by, reviewed_at,
         implemented_at, implemented_in_workflow_url
  FROM workflow_change_requests
  ORDER BY requested_at DESC;
  ```
- Source: `backend/src/modules/workflow_change_requests/` +
  `frontend/app/(dashboard)/settings/workflow-change-requests/`.

### Retirement criterion

The control retires automatically when **all** of the following hold:

1. An n8n Enterprise license is activated
   (`N8N_LICENSE_ACTIVATION_KEY` set in `docker-compose.prod.yml`).
2. n8n's native OIDC integration is enabled
   (`N8N_USER_MANAGEMENT_AUTH_PROVIDER=oidc`,
   `N8N_USER_MANAGEMENT_DISABLED=false`).
3. n8n's audit log feature is enabled
   (`N8N_AUDIT_LOG_ENABLED=true`).

Once those three are live, n8n itself emits per-user audit events
and the compensating control is no longer needed. At that point:

- Update the **Status** line above to "Retired" with the retirement date.
- Optionally extend the `n8n_editor:access` permission to additional
  roles via the UI.
- The `workflow_change_requests` module can stay in place for tracking
  cross-team workflow changes — its purpose shifts from compliance to
  change-management hygiene.

### Audit trail of this document

- 2026-05-22 — Initial publication. Single Super Admin role holds
  `n8n_editor:access`. WCR tracker live.

Append a new line each time the control's status, scope, or
retirement criteria change.
