"""Alert Reports module unit tests."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_models_import_smoke():
    """All 3 alert_reports models import without errors."""
    from backend.src.modules.alert_reports.infrastructure.models import (
        AlertReportTemplateModel,
        AlertReportTemplateVersionModel,
        CaseGeneratedReportModel,
    )
    assert AlertReportTemplateModel.__tablename__ == "alert_report_templates"
    assert (
        AlertReportTemplateVersionModel.__tablename__
        == "alert_report_template_versions"
    )
    assert CaseGeneratedReportModel.__tablename__ == "case_generated_reports"


def _get_real_url():
    from dotenv import dotenv_values
    env = dotenv_values("backend/.env")
    url = env.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not in backend/.env")
    return url


def test_alert_reports_permissions_seeded():
    """6 alert_reports actions present in permissions table after migration."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check():
        engine = create_async_engine(_get_real_url())
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(text(
                    "SELECT DISTINCT action FROM permissions "
                    "WHERE module = 'alert_reports'"
                ))).fetchall()
                return {r[0] for r in rows}
        finally:
            await engine.dispose()

    actions = asyncio.run(_check())
    expected = {
        "read", "generate", "delete",
        "manage_templates", "set_default", "view_versions",
    }
    assert actions == expected, (
        f"Missing: {expected - actions}, Extra: {actions - expected}"
    )


def test_validate_blocks_unknown_type_raises():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.alert_reports.application.blocks_catalog import (
        validate_blocks,
    )
    with pytest.raises(ValidationError, match="unknown"):
        validate_blocks([{"type": "wat", "params": {}}])


def test_validate_text_block_requires_content_template():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.alert_reports.application.blocks_catalog import (
        validate_blocks,
    )
    with pytest.raises(ValidationError):
        validate_blocks([{"type": "text", "params": {"title": "X"}}])


def test_validate_signature_block_requires_signers():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.alert_reports.application.blocks_catalog import (
        validate_blocks,
    )
    with pytest.raises(ValidationError):
        validate_blocks([{"type": "signature", "params": {}}])


def test_validate_image_block_requires_attachment_id():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.alert_reports.application.blocks_catalog import (
        validate_blocks,
    )
    with pytest.raises(ValidationError):
        validate_blocks([{"type": "image", "params": {}}])


def test_validate_blocks_empty_list_passes():
    from backend.src.modules.alert_reports.application.blocks_catalog import (
        validate_blocks,
    )
    validate_blocks([])  # no exception


def test_validate_blocks_valid_payload_passes():
    from backend.src.modules.alert_reports.application.blocks_catalog import (
        validate_blocks,
    )
    validate_blocks([
        {"type": "alert_metadata", "params": {}},
        {"type": "text", "params": {
            "title": "Análisis", "content_template": "{{ case.title }}",
        }},
        {"type": "page_break", "params": {}},
        {"type": "spacer", "params": {"height_px": 30}},
    ])  # no exception


@pytest.mark.asyncio
async def test_create_template_rejects_invalid_blocks():
    """Unknown block type bubbles up before any DB call."""
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    mock_db = AsyncMock()
    uc = AlertReportTemplateUseCases(db=mock_db)
    actor = MagicMock(user_id="u1", role_id="r1", tenant_id="t1")

    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ):
        with pytest.raises(ValidationError, match="unknown"):
            await uc.create_template(
                actor=actor, name="X", code="x",
                header_config={}, footer_config={},
                blocks=[{"type": "nope", "params": {}}],
            )

    # No DB writes when validation fails
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_update_template_no_change_skips_version_insert():
    """Idempotent update: same fields → no new version row added."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    template = MagicMock()
    template.id = "tpl-1"
    template.tenant_id = "t1"
    template.current_version_id = "v-1"
    template.current_version_number = 3
    template.is_default = False
    template.is_active = True

    current_version = MagicMock()
    current_version.name_snapshot = "Original"
    current_version.header_config = {"show_logo": True}
    current_version.footer_config = {}
    current_version.blocks = [{"type": "alert_metadata", "params": {}}]
    current_version.css_overrides = None

    mock_db = AsyncMock()
    uc = AlertReportTemplateUseCases(db=mock_db)
    actor = MagicMock(user_id="u1", role_id="r1", tenant_id="t1")

    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch.object(
        uc, "_load_template_for_update",
        new=AsyncMock(return_value=template),
    ), patch.object(
        uc, "_load_version",
        new=AsyncMock(return_value=current_version),
    ):
        await uc.update_template(
            actor=actor, template_id="tpl-1",
            name="Original",
            header_config={"show_logo": True},
            footer_config={},
            blocks=[{"type": "alert_metadata", "params": {}}],
        )

    # version_number unchanged → no new version inserted
    assert template.current_version_number == 3
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_soft_delete_default_template_raises_business_rule():
    """Cannot soft-delete the tenant's default template."""
    from backend.src.core.exceptions import BusinessRuleError
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    template = MagicMock()
    template.id = "tpl-1"
    template.tenant_id = "t1"
    template.is_default = True
    template.is_active = True

    mock_db = AsyncMock()
    uc = AlertReportTemplateUseCases(db=mock_db)
    actor = MagicMock(user_id="u1", role_id="r1", tenant_id="t1")

    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch.object(
        uc, "_load_template_for_update",
        new=AsyncMock(return_value=template),
    ):
        with pytest.raises(BusinessRuleError, match="default"):
            await uc.soft_delete(actor=actor, template_id="tpl-1")

    # Template stays active
    assert template.is_active is True


@pytest.mark.asyncio
async def test_set_as_default_clears_previous_then_sets_new():
    """set_as_default issues UPDATE clearing old default then sets is_default=True."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    template = MagicMock()
    template.id = "tpl-1"
    template.tenant_id = "t1"
    template.is_default = False
    template.is_active = True

    mock_db = AsyncMock()
    uc = AlertReportTemplateUseCases(db=mock_db)
    actor = MagicMock(user_id="u1", role_id="r1", tenant_id="t1")

    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch.object(
        uc, "_load_template_for_update",
        new=AsyncMock(return_value=template),
    ):
        result = await uc.set_as_default(actor=actor, template_id="tpl-1")

    assert result.is_default is True
    # Should have issued an UPDATE to clear other defaults
    mock_db.execute.assert_called()
    mock_db.commit.assert_called()


def _make_snapshot_case(case_id: str = "c1"):
    case = MagicMock()
    case.id = case_id
    case.case_number = "EVT-0042"
    case.case_type = "event"
    case.title = "Sample event"
    case.description = "Suspicious login"
    case.tenant_id = "t1"
    case.custom_values = {"region": "LATAM"}
    case.created_at = MagicMock()
    case.created_at.isoformat = MagicMock(return_value="2026-05-17T10:00:00+00:00")
    case.closed_at = None
    case.status = MagicMock(slug="logged", name="Logged")
    case.priority = MagicMock(slug="high", name="Alta")
    case.taxonomy = MagicMock(
        tuic_code="TUIC-001", name="Phishing",
        tlp_default="amber", mitre_techniques=["T1566"],
    )
    case.service_item = MagicMock(name="SOC Service")
    case.team = MagicMock(name="SOC L2")
    case.tenant = MagicMock(name="ACME")
    return case


def test_snapshot_case_extracts_expected_fields():
    from backend.src.modules.alert_reports.application.snapshot_builder import (
        _snapshot_case,
    )
    case = _make_snapshot_case()
    out = _snapshot_case(case)

    assert out["id"] == "c1"
    assert out["case_number"] == "EVT-0042"
    assert out["status_slug"] == "logged"
    assert out["priority_slug"] == "high"
    assert out["taxonomy_code"] == "TUIC-001"
    assert out["tlp"] == "amber"
    assert out["custom_values"] == {"region": "LATAM"}
    assert out["closed_at"] is None


def test_is_snapshot_too_large_detects_overflow():
    from backend.src.modules.alert_reports.application.snapshot_builder import (
        SNAPSHOT_SIZE_LIMIT, is_snapshot_too_large,
    )
    assert is_snapshot_too_large({"x": "small"}) is False
    # Build a payload guaranteed to exceed the 1 MB cap
    fat = {"big": "a" * (SNAPSHOT_SIZE_LIMIT + 1024)}
    assert is_snapshot_too_large(fat) is True


@pytest.mark.asyncio
async def test_snapshot_forensic_hunts_returns_empty_when_no_hunts():
    from backend.src.modules.alert_reports.application.snapshot_builder import (
        _snapshot_forensic_hunts,
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )
    mock_db.execute = AsyncMock(return_value=mock_result)
    out = await _snapshot_forensic_hunts(mock_db, "case-without-hunts")
    assert out == []


@pytest.mark.asyncio
async def test_build_data_snapshot_assembles_full_shape():
    from backend.src.modules.alert_reports.application.snapshot_builder import (
        build_data_snapshot,
    )
    case = _make_snapshot_case()

    mock_db = AsyncMock()
    # Every helper hits db.execute(...).scalars().all() or .scalar_one_or_none()
    # Wire a generic empty result; the snapshot pulls case-only data from the
    # case object itself.
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)

    snap = await build_data_snapshot(mock_db, case)
    assert snap["case"]["id"] == "c1"
    assert snap["priority_calculation"] is None
    assert snap["forensic_hunts"] == []
    assert snap["evidence_attachments"] == []
    assert snap["mitre_techniques"] == ["T1566"]
