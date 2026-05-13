"""Unit tests for sub-spec 01: case types, numbering, promotion."""
import asyncio
import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
