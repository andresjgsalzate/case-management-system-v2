# Single-use anti-replay for `request_approval` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A replayed `request_approval` n8n callback must not create a second pending `ApprovalRequest` for the same playbook run, and must not error on a legitimate n8n retry.

**Architecture:** CMS-side idempotency keyed on `playbook_run_id`, in two layers: an application pre-check in `_action_request_approval` that returns the existing pending approval as a noop, backed by a unique partial DB index `approval_requests(playbook_run_id) WHERE status='pending'` that handles the check-then-insert race (caught and converted to the same noop).

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (async, asyncpg), Alembic, FastAPI, pytest. Postgres in `cms_postgres` (user `cms_user`, db `cms_dev`, port 5433).

**Spec:** `docs/specs/2026-06-11-single-use-approval-anti-replay.md`

**Run/env notes:**
- Bring up DB: `docker compose up -d postgres redis`.
- Run a single test from the repo root: `backend/venv/Scripts/python.exe -m pytest <path>::<test> -q`.
- `test_n8n_bridge.py` tests use the real DB (`create_async_engine(env["DATABASE_URL"])` + `asyncio.run`). They are in the e2e group; run them directly, not via the unit group.

---

## File Structure

- **Modify** `backend/src/modules/n8n_bridge/infrastructure/models.py` — add the unique partial `Index` to `ApprovalRequestModel.__table_args__` (keeps the model in sync with the DB; one responsibility: the ORM mapping).
- **Create** `backend/alembic/versions/<generated>_approval_pending_unique_index.py` — the migration that applies the index to the DB.
- **Modify** `backend/src/modules/n8n_bridge/application/use_cases.py:557` (`_action_request_approval`) — the idempotency pre-check + race catch.
- **Modify** `backend/tests/test_n8n_bridge.py` — new tests next to `test_action_request_approval_creates_pending_row` (line 877).

---

## Task 1: Unique partial index (DB backstop + model sync)

**Files:**
- Modify: `backend/src/modules/n8n_bridge/infrastructure/models.py` (`ApprovalRequestModel`)
- Create: `backend/alembic/versions/<generated>_approval_pending_unique_index.py`
- Test: `backend/tests/test_n8n_bridge.py`

- [ ] **Step 1: Write the failing test (the index rejects a duplicate pending row)**

Add to `backend/tests/test_n8n_bridge.py` (place it after `test_action_request_approval_creates_pending_row`, ~line 933):

```python
def test_pending_approval_unique_per_run_index_rejects_duplicate():
    """The DB enforces at most one pending approval per playbook_run_id."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t
    from sqlalchemy.exc import IntegrityError

    tenant_id = f"t-appr-uniq-{_uuid.uuid4().hex[:8]}"
    secret = "uniq-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                async def _insert_pending():
                    # All NOT NULL columns must be supplied: a raw INSERT
                    # bypasses the Python-side `created_at` default, and
                    # requested_by_workflow / resume_url are NOT NULL.
                    await session.execute(_t(
                        "INSERT INTO approval_requests "
                        "(id, tenant_id, case_id, playbook_run_id, "
                        "requested_action, action_category, "
                        "requested_by_workflow, resume_url, status, "
                        "timeout_at, context_payload, created_at) "
                        "VALUES (:id, :tid, :cid, :rid, 'a', 'c', "
                        "'https://n8n.test/wf', 'https://n8n.test/resume', "
                        "'pending', NOW(), CAST('{}' AS json), NOW())"
                    ), {
                        "id": str(_uuid.uuid4()), "tid": tenant_id,
                        "cid": case_id, "rid": run_id,
                    })

                await _insert_pending()
                await session.commit()

                raised = False
                try:
                    await _insert_pending()
                    await session.commit()
                except IntegrityError:
                    raised = True
                    await session.rollback()

                await _cleanup_n8n_tenant(session, tenant_id)
                await session.commit()
                return raised
        finally:
            await engine.dispose()

    assert _aio.run(_go()) is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_n8n_bridge.py::test_pending_approval_unique_per_run_index_rejects_duplicate -q`
Expected: FAIL — both inserts succeed (`raised` stays `False`), so `assert ... is True` fails. (The index does not exist yet.)

- [ ] **Step 3: Add the index to the model**

In `backend/src/modules/n8n_bridge/infrastructure/models.py`: `Index` is already imported, but the lowercase `text` function is NOT — add it to the existing `from sqlalchemy import (...)` block (e.g. after `Text,`):

```python
    Text,
    UniqueConstraint,
    text,
)
```

Then append the new index to `ApprovalRequestModel`'s existing `__table_args__` tuple (which already holds two `CheckConstraint`s and two `Index`es). Add this entry after `Index("ix_approval_tenant_status_created", ...)`:

```python
        Index(
            "ux_approval_requests_pending_per_run",
            "playbook_run_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
```

- [ ] **Step 4: Generate the migration skeleton**

Run from `backend/`:
`PYTHONPATH=<repo-root> venv/Scripts/python.exe -m alembic revision -m "approval pending unique index"`
This creates a file under `backend/alembic/versions/` with `down_revision = 'a1f2e3d4c5b6'` (the current head) already filled in. Note the generated path.

- [ ] **Step 5: Fill in the migration body**

Edit the generated file's `upgrade`/`downgrade` (leave the `revision`/`down_revision` header as generated):

```python
def upgrade() -> None:
    op.create_index(
        "ux_approval_requests_pending_per_run",
        "approval_requests",
        ["playbook_run_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_approval_requests_pending_per_run",
        table_name="approval_requests",
    )
```

Note: `playbook_run_id` is nullable; Postgres treats NULLs as distinct, so non-playbook approvals are unaffected. If `alembic upgrade` errors with a unique-violation, the dev DB already holds duplicate pending approvals for one run — delete the extras first (`DELETE FROM approval_requests a USING approval_requests b WHERE a.ctid < b.ctid AND a.playbook_run_id = b.playbook_run_id AND a.status='pending' AND b.status='pending';`) then re-run.

- [ ] **Step 6: Apply the migration**

Run from `backend/`: `PYTHONPATH=<repo-root> venv/Scripts/python.exe -m alembic upgrade head`
Expected: completes without error; `alembic heads` shows the new revision.

- [ ] **Step 7: Run the test to verify it passes**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_n8n_bridge.py::test_pending_approval_unique_per_run_index_rejects_duplicate -q`
Expected: PASS (second insert raises `IntegrityError`).

- [ ] **Step 8: Commit**

```bash
git add backend/src/modules/n8n_bridge/infrastructure/models.py backend/alembic/versions backend/tests/test_n8n_bridge.py
git commit -m "feat(n8n): unique partial index for pending approvals per run"
```

---

## Task 2: Application-level idempotency in `_action_request_approval`

**Files:**
- Modify: `backend/src/modules/n8n_bridge/application/use_cases.py:557` (`_action_request_approval`)
- Test: `backend/tests/test_n8n_bridge.py`

- [ ] **Step 1: Write the failing test (replay → noop, single row)**

Add to `backend/tests/test_n8n_bridge.py`:

```python
def test_request_approval_replay_is_idempotent_noop():
    """A replayed request_approval callback returns the existing approval as a
    noop and creates no second pending row."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-appr-replay-{_uuid.uuid4().hex[:8]}"
    secret = "replay-secret"
    payload = {
        "requested_action": "Aislar host PC-FIN-04",
        "action_category": "host_quarantine",
        "resume_url": "https://n8n.test/webhook-waiting/replay-1",
        "timeout_minutes": 30,
    }

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)
                body, headers = _hmac_callback(session, secret, "request_approval", payload)

                uc = _make_uc(session)
                first = await uc.handle_callback(
                    action="request_approval", payload=payload,
                    playbook_run_id=run_id, request_body=body,
                    request_headers=headers,
                )
                second = await uc.handle_callback(
                    action="request_approval", payload=payload,
                    playbook_run_id=run_id, request_body=body,
                    request_headers=headers,
                )
                count = (await session.execute(_t(
                    "SELECT count(*) FROM approval_requests "
                    "WHERE playbook_run_id = :rid AND status = 'pending'"
                ), {"rid": run_id})).scalar_one()
                await _cleanup_n8n_tenant(session, tenant_id)
                return first, second, count
        finally:
            await engine.dispose()

    first, second, count = _aio.run(_go())
    assert first["ok"] is True
    assert second["ok"] is True
    assert second.get("noop") is True
    assert second["approval_id"] == first["approval_id"]
    assert count == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_n8n_bridge.py::test_request_approval_replay_is_idempotent_noop -q`
Expected: FAIL — without the pre-check the second call inserts a second pending row, so `count == 2` and `second.get("noop")` is `None`. (Depending on transaction timing the second insert may instead raise `IntegrityError` now that Task 1's index exists — either way the test fails until Step 3.)

- [ ] **Step 3: Add the idempotency pre-check + race catch**

In `backend/src/modules/n8n_bridge/application/use_cases.py`, edit `_action_request_approval`. First confirm the imports at the top of the file include `from sqlalchemy import select` (it does, line ~19) and add `from sqlalchemy.exc import IntegrityError` if absent. Then change the body so the pre-check runs before building the model and the insert is wrapped in a savepoint:

Replace the existing tail of the method (from `approval = ApprovalRequestModel(` through the final `return`) with:

```python
        # Idempotency: a replayed request_approval callback (n8n echoes the
        # same body/HMAC/JWT, or retries on network failure) must not create a
        # second pending approval for this run. Return the existing one.
        existing = (await self.db.execute(
            select(ApprovalRequestModel).where(
                ApprovalRequestModel.playbook_run_id == run.id,
                ApprovalRequestModel.status == "pending",
            )
        )).scalar_one_or_none()
        if existing is not None:
            return {
                "ok": True,
                "noop": True,
                "approval_id": existing.id,
                "timeout_at": existing.timeout_at.isoformat(),
            }

        approval = ApprovalRequestModel(
            tenant_id=case.tenant_id,
            case_id=case.id,
            playbook_run_id=run.id,
            requested_action=requested_action,
            action_category=action_category,
            context_payload=payload.get("context") or {},
            requested_by_workflow=run.workflow_url,
            resume_url=resume_url,
            resume_hmac_secret_encrypted=resume_secret_encrypted,
            status="pending",
            timeout_at=timeout_at,
        )
        try:
            async with self.db.begin_nested():
                self.db.add(approval)
                await self.db.flush()
        except IntegrityError:
            # Lost the check-then-insert race to a concurrent replay; the
            # savepoint rolled back, so return the row the winner created.
            winner = (await self.db.execute(
                select(ApprovalRequestModel).where(
                    ApprovalRequestModel.playbook_run_id == run.id,
                    ApprovalRequestModel.status == "pending",
                )
            )).scalar_one()
            return {
                "ok": True,
                "noop": True,
                "approval_id": winner.id,
                "timeout_at": winner.timeout_at.isoformat(),
            }
        return {
            "ok": True,
            "approval_id": approval.id,
            "timeout_at": timeout_at.isoformat(),
        }
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_n8n_bridge.py::test_request_approval_replay_is_idempotent_noop -q`
Expected: PASS (`count == 1`, `second.noop is True`, same `approval_id`).

- [ ] **Step 5: Write the re-request-after-decision test**

Add to `backend/tests/test_n8n_bridge.py`:

```python
def test_request_approval_allowed_again_after_decision():
    """Once the prior approval is no longer pending, a new request_approval for
    the same run creates a fresh pending approval (index only constrains pending)."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-appr-again-{_uuid.uuid4().hex[:8]}"
    secret = "again-secret"
    payload = {
        "requested_action": "Aislar host",
        "action_category": "host_quarantine",
        "resume_url": "https://n8n.test/webhook-waiting/again-1",
    }

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)
                body, headers = _hmac_callback(session, secret, "request_approval", payload)
                uc = _make_uc(session)

                first = await uc.handle_callback(
                    action="request_approval", payload=payload,
                    playbook_run_id=run_id, request_body=body,
                    request_headers=headers,
                )
                # Resolve the first approval so it's no longer pending.
                await session.execute(_t(
                    "UPDATE approval_requests SET status = 'rejected' "
                    "WHERE id = :id"
                ), {"id": first["approval_id"]})
                await session.commit()

                second = await uc.handle_callback(
                    action="request_approval", payload=payload,
                    playbook_run_id=run_id, request_body=body,
                    request_headers=headers,
                )
                await _cleanup_n8n_tenant(session, tenant_id)
                return first, second
        finally:
            await engine.dispose()

    first, second = _aio.run(_go())
    assert second.get("noop") is None
    assert second["approval_id"] != first["approval_id"]
```

- [ ] **Step 6: Run the re-request test to verify it passes**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_n8n_bridge.py::test_request_approval_allowed_again_after_decision -q`
Expected: PASS (a fresh approval id, no noop).

- [ ] **Step 7: Run the full n8n_bridge module to check for regressions**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_n8n_bridge.py -q`
Expected: all pass, including the pre-existing `test_action_request_approval_creates_pending_row` (single call still returns a non-noop approval with `timeout_at`).

- [ ] **Step 8: Commit**

```bash
git add backend/src/modules/n8n_bridge/application/use_cases.py backend/tests/test_n8n_bridge.py
git commit -m "feat(n8n): idempotent request_approval to block destructive-action replay"
```

---

## Final verification

- [ ] Run the e2e group to confirm nothing else regressed:
  `backend/venv/Scripts/python.exe -m pytest backend/tests/test_n8n_bridge.py backend/tests/test_n8n_bridge_integration.py -q`
  Expected: all pass.
- [ ] Confirm the spec's testing section is fully covered: replay→noop (Task 2 Step 1), retry safety (same test asserts `ok`), re-request after decision (Task 2 Step 5), index backstop (Task 1 Step 1), regression (Task 2 Step 7).
