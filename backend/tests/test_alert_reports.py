"""Alert Reports module unit tests."""
import asyncio

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
