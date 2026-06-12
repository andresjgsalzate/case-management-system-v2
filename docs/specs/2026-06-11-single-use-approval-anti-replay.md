# Single-use anti-replay for `request_approval` callbacks

Status: approved (2026-06-11) — ready for implementation plan.

## Context

When an n8n playbook needs operator sign-off for a destructive forensic
action (e.g. launching a Velociraptor hunt), it calls back into CMS with the
`request_approval` action. `_action_request_approval`
(`backend/src/modules/n8n_bridge/application/use_cases.py:557`) persists a
pending `ApprovalRequestModel` linked to the `playbook_run_id`.

The callback is authenticated by HMAC (always) plus an optional case-scoped
JWT. Both are **replayable within the token TTL**: the same callback body,
HMAC signature and JWT can be re-sent. `_action_request_approval` has **no
idempotency guard**, so a replayed `request_approval` callback creates a
*second* pending approval for the same run — duplicating the destructive
governance flow.

The case-scoped callback JWT is intentionally multi-use (echoed on every
callback of a run: `add_note`, `update_*`, `request_approval`, …), so
"single-use" cannot apply to the token wholesale. It must target the one
action with destructive consequence: `request_approval`.

## Goal

A replayed `request_approval` callback must not create a second pending
`ApprovalRequest` for the same playbook run, and must not error on a
legitimate n8n network retry.

Non-goals: anti-replay on benign actions (`add_note`, `update_*`,
`set_pending_triage_complete`); a generic nonce/consumed-token store; any
change to n8n workflow templates; changes to `jwt_helper`.

## Design

CMS-controlled idempotency keyed on `playbook_run_id`. Two layers (defense in
depth):

1. **Application layer** — `_action_request_approval` checks for an existing
   `pending` approval for `run.id` before inserting.
2. **Database layer** — a unique partial index
   `approval_requests (playbook_run_id) WHERE status = 'pending'` is the
   backstop for the check-then-insert race (two concurrent replays both pass
   the application check).

This needs no n8n change, no new table, and does not touch `jwt_helper` — the
threat is closed at the system of record, which does not have to trust n8n to
generate unique nonces (a replayed callback would replay any nonce too).

### Behaviour on duplicate: idempotent noop

If a pending approval already exists for the run, return the existing one
rather than raising:

```
{"ok": True, "noop": True, "approval_id": <existing>, "timeout_at": <existing>}
```

Rationale:
- n8n retries callbacks on network failure; a legitimate retry must not fail.
- Mirrors `_action_record_decision`, which already returns a noop on a
  re-delivered terminal callback.
- Anti-replay is still effective: no new approval row, no re-triggered flow.

### Components

1. **Alembic migration** — add the unique partial index. `playbook_run_id` is
   nullable; Postgres excludes NULLs from unique indexes, so approvals created
   by other (non-playbook) paths are unaffected.
2. **`_action_request_approval`** — pre-check for an existing pending approval
   for `run.id`; if found, return it as a noop. Wrap the insert/flush so a
   `IntegrityError` from the unique index (concurrent replay that passed the
   pre-check) is caught, the transaction recovered, and the existing approval
   returned as a noop.
3. **Tests** (see below).

## Semantics and limits (explicit)

- "single-use" means **one pending approval per playbook run**.
- Re-requesting approval after the prior one is `approved` / `rejected` /
  `timeout` is allowed — the index only constrains `pending` rows.
- A single run requesting two *distinct* approvals concurrently is blocked.
  This is an accepted limitation (no known playbook does this; revisit with a
  `(playbook_run_id, requested_action)` key if a real case appears).

## Testing

- Replay: calling `request_approval` twice for the same run yields exactly one
  pending `ApprovalRequest`; the second returns `noop=True` with the same
  `approval_id`.
- Retry safety: the noop path returns success (not an error).
- Re-request after decision: once the first approval is non-pending, a new
  `request_approval` for the same run creates a fresh pending approval.
- Race backstop: the unique partial index rejects a concurrent second insert
  (covered by the `IntegrityError` handling path).
- Regression: existing `request_approval` tests still pass (single call →
  one pending row).

## Out of scope / future

- Generic per-callback nonce (`consumed_action_nonces` table) — heavier and
  couples to n8n; only worth it if benign callbacks ever need anti-replay.
- `jwt_helper` single-use jti — not needed for this threat.
