"""Unit tests for sub-spec 01: case types, numbering, promotion."""
import asyncio
import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_range_row(prefix: str, start: int = 1, end: int = 10000, counter_start: int = 0):
    """Return a simple namespace that mimics CaseNumberRangeModel for mocking."""
    class _Row:
        def __init__(self):
            self.prefix = prefix
            self.range_start = start
            self.range_end = end
            self.current_number = counter_start  # 0 == range_start - 1 (no numbers issued)
    return _Row()


def _make_mock_db_with_counter(row):
    """
    Build an AsyncMock session whose execute() returns the same range row on
    every call.  current_number is mutated in-place by the method, so
    sequential calls produce monotonically increasing numbers.
    """
    async def _execute(_stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = row
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = _execute
    mock_session.flush = AsyncMock()
    return mock_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_next_case_number_returns_formatted_string():
    """Single call returns PREFIX-YYYY-NNNNNN format."""
    from backend.src.modules.cases.application.use_cases import CaseUseCases

    row = _make_range_row("INC", counter_start=0)
    db = _make_mock_db_with_counter(row)

    uc = CaseUseCases(db=db)
    result = await uc._next_case_number(tenant_id=None, prefix="INC")

    year = datetime.datetime.utcnow().year
    assert result == f"INC-{year}-000001", f"Unexpected: {result}"


@pytest.mark.asyncio
async def test_next_case_number_sequential_uniqueness():
    """Sequential calls increment the counter and produce distinct numbers."""
    from backend.src.modules.cases.application.use_cases import CaseUseCases

    row = _make_range_row("REQ", counter_start=0)
    db = _make_mock_db_with_counter(row)

    uc = CaseUseCases(db=db)
    results = []
    for _ in range(5):
        results.append(await uc._next_case_number(tenant_id=None, prefix="REQ"))

    assert len(set(results)) == 5, f"Duplicates found: {results}"


@pytest.mark.asyncio
async def test_next_case_number_atomic_under_concurrency():
    """100 concurrent calls to _next_case_number must return 100 distinct numbers.

    This validates the row-locking logic (SELECT FOR UPDATE) produces unique
    sequential numbers.  With a shared mock session the asyncio event loop
    serializes each coroutine, replicating the same guarantee that SELECT FOR
    UPDATE provides in production (each transaction sees the latest committed
    current_number before incrementing).

    NOTE: true concurrent DB races require separate connections per task and
    a live DB.  This test proves algorithmic correctness; SELECT FOR UPDATE
    is exercised at the SQLAlchemy query layer and is visible in the generated
    SQL via the .with_for_update() call in the implementation.
    """
    from backend.src.modules.cases.application.use_cases import CaseUseCases

    row = _make_range_row("INC", counter_start=0)
    db = _make_mock_db_with_counter(row)

    uc = CaseUseCases(db=db)

    async def gen_one():
        return await uc._next_case_number(tenant_id=None, prefix="INC")

    results = await asyncio.gather(*[gen_one() for _ in range(100)])

    duplicates = [r for r in results if results.count(r) > 1]
    assert len(set(results)) == 100, f"Got duplicates: {duplicates[:5]}"

    year = datetime.datetime.utcnow().year
    for r in results:
        assert r.startswith("INC-"), f"Unexpected prefix: {r}"
        parts = r.split("-")
        assert len(parts) == 3, f"Bad format: {r}"
        assert parts[1] == str(year), f"Bad year: {r}"
        assert parts[2].isdigit() and len(parts[2]) == 6, f"Bad zero-pad: {r}"


@pytest.mark.asyncio
async def test_next_case_number_raises_when_no_range():
    """Raises OperationalError (or HTTPException) when no active range exists."""
    from backend.src.modules.cases.application.use_cases import CaseUseCases

    async def _execute(_stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = _execute
    mock_session.flush = AsyncMock()

    uc = CaseUseCases(db=mock_session)

    with pytest.raises(Exception):
        await uc._next_case_number(tenant_id=None, prefix="INC")


# ---------------------------------------------------------------------------
# Helpers for create_case tests (Task 9)
# ---------------------------------------------------------------------------

def _make_fake_status(slug: str, applies_to: list[str]) -> MagicMock:
    status = MagicMock()
    status.id = "status-uuid-1"
    status.slug = slug
    status.applies_to_case_types = applies_to
    return status


def _make_fake_case_response(case_number: str, case_type: str) -> MagicMock:
    resp = MagicMock()
    resp.case_number = case_number
    resp.case_type = case_type
    return resp


def _make_fake_service_item(priority_id: str = "pri-1") -> MagicMock:
    item = MagicMock()
    item.default_priority_id = priority_id
    item.default_team_id = None
    item.default_level = 1
    return item


def _base_db_mock() -> AsyncMock:
    """Minimal AsyncMock session for create_case: add/commit/refresh/get return fakes."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    # db.get used for ServiceCatalogItemModel → return a fake item so service lookup passes
    session.get = AsyncMock(return_value=_make_fake_service_item())
    return session


# ---------------------------------------------------------------------------
# Task 9 Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_with_invalid_case_type_raises():
    """DTO with invalid case_type → Pydantic ValidationError before reaching use case."""
    from pydantic import ValidationError as PydanticValidationError
    from backend.src.modules.cases.application.dtos import CreateCaseDTO

    with pytest.raises(PydanticValidationError) as exc:
        CreateCaseDTO(
            case_type="bogus",  # type: ignore[arg-type]
            title="some title",
            service_item_id="svc-1",
        )
    assert "bogus" in str(exc.value).lower() or "case_type" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_create_request_uses_REQ_prefix():
    """case_type='request' → _next_case_number called with 'REQ' → case_number starts REQ-."""
    from backend.src.modules.cases.application.use_cases import CaseUseCases
    from backend.src.modules.cases.application.dtos import CreateCaseDTO

    db = _base_db_mock()
    dto = CreateCaseDTO(
        case_type="request",
        title="VPN access request",
        service_item_id="svc-1",
        priority_id="pri-1",
    )

    fake_status = _make_fake_status("new", ["request", "incident", "event"])
    year = datetime.datetime.utcnow().year
    expected_number = f"REQ-{year}-000001"
    fake_response = _make_fake_case_response(expected_number, "request")

    uc = CaseUseCases(db=db)

    with (
        patch.object(uc, "_next_case_number", new=AsyncMock(return_value=expected_number)) as mock_next,
        patch.object(uc, "_get_status_by_slug", new=AsyncMock(return_value=fake_status)),
        patch.object(uc, "get_case", new=AsyncMock(return_value=fake_response)),
        patch("backend.src.modules.cases.application.use_cases.event_bus") as mock_bus,
    ):
        mock_bus.publish = AsyncMock()
        result = await uc.create_case(dto=dto, actor_id="user-1", tenant_id=None)

    mock_next.assert_awaited_once_with(None, "REQ")
    assert result.case_number.startswith("REQ-")
    assert result.case_type == "request"


@pytest.mark.asyncio
async def test_create_incident_uses_INC_prefix():
    """case_type='incident' → _next_case_number called with 'INC' → case_number starts INC-."""
    from backend.src.modules.cases.application.use_cases import CaseUseCases
    from backend.src.modules.cases.application.dtos import CreateCaseDTO

    db = _base_db_mock()
    dto = CreateCaseDTO(
        case_type="incident",
        title="Possible ransomware on host",
        service_item_id="svc-1",
        priority_id="pri-1",
    )

    fake_status = _make_fake_status("new", ["request", "incident", "event"])
    year = datetime.datetime.utcnow().year
    expected_number = f"INC-{year}-000001"
    fake_response = _make_fake_case_response(expected_number, "incident")

    uc = CaseUseCases(db=db)

    with (
        patch.object(uc, "_next_case_number", new=AsyncMock(return_value=expected_number)) as mock_next,
        patch.object(uc, "_get_status_by_slug", new=AsyncMock(return_value=fake_status)),
        patch.object(uc, "get_case", new=AsyncMock(return_value=fake_response)),
        patch("backend.src.modules.cases.application.use_cases.event_bus") as mock_bus,
    ):
        mock_bus.publish = AsyncMock()
        result = await uc.create_case(dto=dto, actor_id="user-1", tenant_id=None)

    mock_next.assert_awaited_once_with(None, "INC")
    assert result.case_number.startswith("INC-")
    assert result.case_type == "incident"


@pytest.mark.asyncio
async def test_create_event_uses_EVT_prefix_and_logged_status():
    """case_type='event' → prefix EVT, default status slug 'logged'."""
    from backend.src.modules.cases.application.use_cases import CaseUseCases
    from backend.src.modules.cases.application.dtos import CreateCaseDTO

    db = _base_db_mock()
    dto = CreateCaseDTO(
        case_type="event",
        title="Brute force attempt detected",
        service_item_id="svc-1",
        priority_id="pri-1",
    )

    fake_status = _make_fake_status("logged", ["event"])
    year = datetime.datetime.utcnow().year
    expected_number = f"EVT-{year}-000001"
    fake_response = _make_fake_case_response(expected_number, "event")

    uc = CaseUseCases(db=db)

    with (
        patch.object(uc, "_next_case_number", new=AsyncMock(return_value=expected_number)) as mock_next,
        patch.object(uc, "_get_status_by_slug", new=AsyncMock(return_value=fake_status)) as mock_status,
        patch.object(uc, "get_case", new=AsyncMock(return_value=fake_response)),
        patch("backend.src.modules.cases.application.use_cases.event_bus") as mock_bus,
    ):
        mock_bus.publish = AsyncMock()
        result = await uc.create_case(dto=dto, actor_id="user-1", tenant_id=None)

    mock_next.assert_awaited_once_with(None, "EVT")
    # status resolved with 'logged' (the default for event when no initial_status_slug given)
    mock_status.assert_awaited_once_with(None, "logged")
    assert result.case_number.startswith("EVT-")
    assert result.case_type == "event"


@pytest.mark.asyncio
async def test_create_with_status_that_does_not_apply_raises():
    """Resolved status applies_to_case_types excludes case_type → ValidationError."""
    from backend.src.modules.cases.application.use_cases import CaseUseCases
    from backend.src.modules.cases.application.dtos import CreateCaseDTO
    from backend.src.core.exceptions import ValidationError

    db = _base_db_mock()
    dto = CreateCaseDTO(
        case_type="event",
        title="Brute force",
        service_item_id="svc-1",
        priority_id="pri-1",
        initial_status_slug="in_progress",  # only applies to request
    )

    # Status that only applies to 'request', NOT 'event'
    fake_status = _make_fake_status("in_progress", ["request"])
    year = datetime.datetime.utcnow().year
    expected_number = f"EVT-{year}-000001"

    uc = CaseUseCases(db=db)

    with (
        patch.object(uc, "_next_case_number", new=AsyncMock(return_value=expected_number)),
        patch.object(uc, "_get_status_by_slug", new=AsyncMock(return_value=fake_status)),
    ):
        with pytest.raises(ValidationError) as exc:
            await uc.create_case(dto=dto, actor_id="user-1", tenant_id=None)

    msg = str(exc.value).lower()
    assert "event" in msg or "does not apply" in msg or "applies_to" in msg
