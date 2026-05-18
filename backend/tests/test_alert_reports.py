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
    # `REAL_DATABASE_URL` survives conftest's autouse `set_test_env` fixture
    # which patches `DATABASE_URL` to a dummy `localhost/db` for the whole
    # test session. Containerised runs export REAL_DATABASE_URL pointing at
    # the in-network `postgres` host. Host-based dev still reads from
    # `backend/.env` when neither env var is set.
    import os
    url = os.environ.get("REAL_DATABASE_URL")
    if not url:
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        url = env.get("DATABASE_URL")
    if not url:
        pytest.skip(
            "neither REAL_DATABASE_URL nor backend/.env DATABASE_URL set"
        )
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


def _make_snapshot(case_id: str = "c1") -> dict:
    return {
        "case": {
            "id": case_id,
            "case_number": "EVT-0042",
            "title": "Sample event",
            "tenant_name": "ACME",
            "taxonomy_code": "TUIC-001",
            "taxonomy_name": "Phishing",
            "case_type": "event",
            "priority_name": "Alta",
            "service_item_name": "SOC",
            "team_name": "L2",
            "created_at": "2026-05-17T10:00:00+00:00",
            "tlp": "amber",
        },
        "priority_calculation": None,
        "forensic_hunts": [
            {
                "hunt_id": "h1",
                "artifact_name": "Windows.Detection.Yara.Process",
                "target_label": "PC-X",
                "status": "completed",
                "result_hash": "abc123",
                "result_summary": {"total_rows": 3, "client_count": 1},
                "completed_at": "2026-05-17T10:30:00+00:00",
            }
        ],
        "evidence_attachments": [],
        "notes_summary": "",
        "activity_timeline": [],
        "recommendations": None,
        "behavior_relation": None,
        "iocs": [],
        "mitre_techniques": ["T1566"],
    }


def test_render_blocks_in_order():
    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    html = renderer.render(
        blocks=[
            {"type": "page_break", "params": {}},
            {"type": "spacer", "params": {"height_px": 50}},
            {"type": "alert_metadata", "params": {}},
        ],
        snapshot=_make_snapshot(),
        header_config={},
        footer_config={},
    )
    pos_pb = html.find("page-break")
    pos_sp = html.find('height: 50px')
    pos_meta = html.find("alert-metadata")
    assert pos_pb < pos_sp < pos_meta


def test_render_unknown_block_renders_placeholder():
    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    html = renderer.render(
        blocks=[{"type": "wat", "params": {}}],
        snapshot=_make_snapshot(),
        header_config={},
        footer_config={},
    )
    assert 'class="block-error"' in html
    assert "wat" in html


def test_render_alert_metadata_uses_snapshot():
    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    html = renderer.render(
        blocks=[{"type": "alert_metadata", "params": {}}],
        snapshot=_make_snapshot(),
        header_config={},
        footer_config={},
    )
    assert "EVT-0042" in html
    assert "Phishing" in html
    assert "TUIC-001" in html
    assert "amber" in html.lower()


def test_render_evidence_grid_includes_forensic_hunts_when_param_true():
    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    html = renderer.render(
        blocks=[{
            "type": "evidence_grid",
            "params": {"include_forensic_hunts": True},
        }],
        snapshot=_make_snapshot(),
        header_config={},
        footer_config={},
    )
    assert "Windows.Detection.Yara.Process" in html


def test_render_evidence_grid_excludes_when_param_false():
    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    html = renderer.render(
        blocks=[{
            "type": "evidence_grid",
            "params": {"include_forensic_hunts": False},
        }],
        snapshot=_make_snapshot(),
        header_config={},
        footer_config={},
    )
    assert "Windows.Detection.Yara.Process" not in html


def test_render_recommendations_uses_default_when_note_empty():
    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    snap = _make_snapshot()
    html = renderer.render(
        blocks=[{
            "type": "recommendations",
            "params": {
                "default_recommendations": [
                    "Aislar el host",
                    "Rotar credenciales",
                ],
            },
        }],
        snapshot=snap,
        header_config={},
        footer_config={},
    )
    assert "Aislar el host" in html
    assert "Rotar credenciales" in html


def test_render_text_block_jinja2_sandbox():
    """Sandboxed env blocks attribute access to internals."""
    from jinja2.exceptions import SecurityError

    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    with pytest.raises(SecurityError):
        renderer.render(
            blocks=[{
                "type": "text",
                "params": {
                    "content_template": "{{ ''.__class__.__mro__ }}",
                },
            }],
            snapshot=_make_snapshot(),
            header_config={},
            footer_config={},
        )


def test_render_text_block_markdown_html_sanitized():
    """Markdown render + bleach strips disallowed tags like <script>."""
    from backend.src.modules.alert_reports.application.block_renderer import (
        BlockRenderer,
    )
    renderer = BlockRenderer()
    html = renderer.render(
        blocks=[{
            "type": "text",
            "params": {
                "use_markdown": True,
                "content_template": (
                    "Hello\n\n<script>alert(1)</script>\n\n**bold** text"
                ),
            },
        }],
        snapshot=_make_snapshot(),
        header_config={},
        footer_config={},
    )
    assert "<script>" not in html
    assert "alert(1)" not in html
    assert "<strong>bold</strong>" in html or "bold" in html


# ── PDF generator (Task 7) ──────────────────────────────────────────────
#
# WeasyPrint runtime needs GTK3 native libs (libcairo2, libpango, gdk-pixbuf,
# gobject). Host Windows dev does not ship these; tests below run only inside
# the `backend` Docker container where the libs are baked into the image.


def _weasyprint_works() -> bool:
    """Returns True if WeasyPrint can actually render — checked at import time
    so tests skip cleanly in environments without GTK3."""
    try:
        import weasyprint
        weasyprint.HTML(string="<p>x</p>").write_pdf()
        return True
    except Exception:
        return False


_skip_no_pdf = pytest.mark.skipif(
    not _weasyprint_works(),
    reason="WeasyPrint native libs (GTK3) not available — run inside backend container",
)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Concatenate text from every page of a PDF buffer."""
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


@_skip_no_pdf
@pytest.mark.asyncio
async def test_html_to_pdf_returns_pdf_bytes_starts_with_magic():
    from backend.src.modules.alert_reports.application.pdf_generator import (
        html_to_pdf,
    )
    pdf = await html_to_pdf(
        html="<html><body><p>Test</p></body></html>",
        header_config={},
        footer_config={},
        snapshot={},
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 200  # not empty


@_skip_no_pdf
@pytest.mark.asyncio
async def test_html_to_pdf_includes_page_numbers():
    from backend.src.modules.alert_reports.application.pdf_generator import (
        html_to_pdf,
    )
    pdf = await html_to_pdf(
        html="<html><body><p>Page content</p></body></html>",
        header_config={},
        footer_config={},
        snapshot={"case": {"tlp": "WHITE"}},
    )
    text = _extract_pdf_text(pdf)
    assert "Página" in text
    assert " 1 " in text and " de " in text


@_skip_no_pdf
@pytest.mark.asyncio
async def test_html_to_pdf_includes_tlp_in_header():
    from backend.src.modules.alert_reports.application.pdf_generator import (
        html_to_pdf,
    )
    pdf = await html_to_pdf(
        html="<html><body><p>Confidencial</p></body></html>",
        header_config={"title_template": "REPORTE SOC"},
        footer_config={},
        snapshot={"case": {"tlp": "AMBER"}},
    )
    text = _extract_pdf_text(pdf)
    assert "TLP" in text
    assert "AMBER" in text
    assert "REPORTE SOC" in text


# ── generate_report end-to-end (Task 8) ─────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_template_uses_explicit_id_when_given():
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    explicit = MagicMock(id="tpl-explicit", tenant_id="t1", is_default=False)
    explicit_version = MagicMock(id="v-explicit", version=2)

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[explicit, explicit_version])

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    template, version = await uc._resolve_template(
        tenant_id="t1", template_id="tpl-explicit",
        current_version_id_resolver=lambda t: t.id and "v-explicit",
    )
    assert template.id == "tpl-explicit"
    assert version.id == "v-explicit"


@pytest.mark.asyncio
async def test_resolve_template_falls_back_to_global_default():
    """Tenant has no default → uses tenant_id IS NULL + is_default=True row."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    global_default = MagicMock(
        id="tpl-global", tenant_id=None, is_default=True,
        current_version_id="v-global",
    )
    global_version = MagicMock(id="v-global", version=1)

    mock_db = AsyncMock()
    # First execute: tenant default → nothing
    # Second execute: global default → global row
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none = MagicMock(return_value=None)
    mock_result_global = MagicMock()
    mock_result_global.scalar_one_or_none = MagicMock(return_value=global_default)
    mock_db.execute = AsyncMock(
        side_effect=[mock_result_empty, mock_result_global]
    )
    mock_db.get = AsyncMock(return_value=global_version)

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    template, version = await uc._resolve_template(
        tenant_id="t1", template_id=None,
        current_version_id_resolver=None,
    )
    assert template.tenant_id is None
    assert template.is_default is True
    assert version.id == "v-global"


@pytest.mark.asyncio
async def test_resolve_template_no_default_anywhere_raises():
    from backend.src.core.exceptions import BusinessRuleError
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    with pytest.raises(BusinessRuleError, match="default"):
        await uc._resolve_template(
            tenant_id="t1", template_id=None,
            current_version_id_resolver=None,
        )


@pytest.mark.asyncio
async def test_generate_report_actor_sets_manual_ui_via():
    """actor present + no n8n_run_id → generated_via='manual_ui'."""
    import hashlib
    fake_pdf = b"%PDF-1.4\nfake content"
    pdf_hash = hashlib.sha256(fake_pdf).hexdigest()

    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )

    case = MagicMock(id="c1", tenant_id="t1")
    template = MagicMock(id="tpl1", tenant_id="t1", current_version_id="v1")
    version = MagicMock(
        id="v1", version=3, blocks=[], header_config={}, footer_config={},
        css_overrides=None, name_snapshot="SOC standard",
    )

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=case)
    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="t1", is_global=False,
    )

    captured: dict = {}

    async def fake_render_html(*args, **kwargs):
        return "<html>...</html>"

    async def fake_html_to_pdf(**kwargs):
        return fake_pdf

    async def fake_build_snapshot(db, c):
        return {"case": {"id": c.id, "tenant_name": "ACME", "tlp": "WHITE"}}

    async def fake_persist_attachment(*, pdf_bytes, filename, case, actor_id):
        att = MagicMock(id="att-1")
        captured["filename"] = filename
        captured["actor_id"] = actor_id
        return att

    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "backend.src.modules.alert_reports.application.use_cases.build_data_snapshot",
        new=fake_build_snapshot,
    ), patch(
        "backend.src.modules.alert_reports.application.use_cases.html_to_pdf",
        new=fake_html_to_pdf,
    ):
        uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
        # Patch instance helpers that talk to FS / template-resolution
        with patch.object(
            uc, "_resolve_template",
            new=AsyncMock(return_value=(template, version)),
        ), patch.object(
            uc.renderer, "render",
            return_value="<html>...</html>",
        ), patch.object(
            uc, "_persist_pdf_attachment",
            new=AsyncMock(side_effect=fake_persist_attachment),
        ):
            report = await uc.generate_report(
                actor=actor, case_id="c1",
                template_id=None, n8n_run_id=None,
            )

    assert report.generated_via == "manual_ui"
    assert report.pdf_sha256 == pdf_hash
    assert report.pdf_size_bytes == len(fake_pdf)
    assert report.template_id == "tpl1"
    assert report.template_version_number == 3
    assert report.generated_by_user_id == "u1"
    assert report.generated_by_n8n_run_id is None


@pytest.mark.asyncio
async def test_generate_report_n8n_actor_sets_n8n_api_via():
    """No actor + n8n_run_id → generated_via='n8n_api', user_id NULL."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    case = MagicMock(id="c1", tenant_id="t1")
    template = MagicMock(id="tpl1", tenant_id="t1")
    version = MagicMock(
        id="v1", version=1, blocks=[], header_config={}, footer_config={},
        css_overrides=None, name_snapshot="SOC standard",
    )

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=case)

    async def fake_build_snapshot(db, c):
        return {"case": {"id": c.id, "tlp": "WHITE"}}

    async def fake_html_to_pdf(**kwargs):
        return b"%PDF-1.4\nx"

    with patch(
        "backend.src.modules.alert_reports.application.use_cases.build_data_snapshot",
        new=fake_build_snapshot,
    ), patch(
        "backend.src.modules.alert_reports.application.use_cases.html_to_pdf",
        new=fake_html_to_pdf,
    ):
        uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
        with patch.object(
            uc, "_resolve_template",
            new=AsyncMock(return_value=(template, version)),
        ), patch.object(
            uc.renderer, "render", return_value="<html>...</html>",
        ), patch.object(
            uc, "_persist_pdf_attachment",
            new=AsyncMock(return_value=MagicMock(id="att-1")),
        ):
            report = await uc.generate_report(
                actor=None, case_id="c1",
                template_id="tpl1", n8n_run_id="run-42",
            )

    assert report.generated_via == "n8n_api"
    assert report.generated_by_user_id is None
    assert report.generated_by_n8n_run_id == "run-42"


# ── verify_integrity + delete_report (Task 9) ───────────────────────────


@pytest.mark.asyncio
async def test_verify_integrity_intact_when_bytes_hash_matches():
    import hashlib

    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )

    pdf = b"%PDF-1.4\nbody bytes that were stored"
    expected_hash = hashlib.sha256(pdf).hexdigest()

    report = MagicMock(
        id="rep-1", case_id="c1", attachment_id="att-1",
        pdf_sha256=expected_hash,
    )
    case = MagicMock(id="c1", tenant_id="t1")
    attachment = MagicMock(id="att-1", file_path="/fake/path.pdf")

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[report, case, attachment])

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="t1", is_global=False,
    )
    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch.object(
        uc, "_read_attachment_bytes",
        new=AsyncMock(return_value=pdf),
    ):
        result = await uc.verify_report_integrity(
            actor=actor, report_id="rep-1",
        )

    assert result["is_intact"] is True
    assert result["expected_sha256"] == expected_hash
    assert result["actual_sha256"] == expected_hash
    assert "verified_at" in result


@pytest.mark.asyncio
async def test_verify_integrity_detects_tampered_attachment():
    """Bytes-on-disk hash differs from stored → is_intact=False."""
    import hashlib

    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )

    stored_hash = hashlib.sha256(b"original").hexdigest()
    report = MagicMock(
        id="rep-1", case_id="c1", attachment_id="att-1",
        pdf_sha256=stored_hash,
    )
    case = MagicMock(id="c1", tenant_id="t1")
    attachment = MagicMock(id="att-1", file_path="/fake/tampered.pdf")

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[report, case, attachment])

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="t1", is_global=False,
    )
    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch.object(
        uc, "_read_attachment_bytes",
        new=AsyncMock(return_value=b"corrupted"),
    ):
        result = await uc.verify_report_integrity(
            actor=actor, report_id="rep-1",
        )

    assert result["is_intact"] is False
    assert result["expected_sha256"] != result["actual_sha256"]


@pytest.mark.asyncio
async def test_delete_report_requires_non_empty_reason():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    uc = AlertReportGenerationUseCases(db=AsyncMock(), system_user_id="sys")
    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="t1", is_global=False,
    )
    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ):
        with pytest.raises(ValidationError, match="razón"):
            await uc.delete_report(
                actor=actor, report_id="rep-1", reason="",
            )
        with pytest.raises(ValidationError, match="razón"):
            await uc.delete_report(
                actor=actor, report_id="rep-1", reason="   ",
            )


@pytest.mark.asyncio
async def test_delete_report_soft_deletes_attachment_and_logs_audit():
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    report = MagicMock(
        id="rep-1", case_id="c1", tenant_id="t1",
        attachment_id="att-1", pdf_sha256="abc123",
    )
    case = MagicMock(id="c1", tenant_id="t1")
    attachment = MagicMock(id="att-1", is_deleted=False)

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[report, case, attachment])

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="t1", is_global=False,
    )

    captured: dict = {}

    async def fake_audit_log(**kwargs):
        captured.update(kwargs)

    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch.object(
        uc, "_audit_log_delete",
        new=AsyncMock(side_effect=fake_audit_log),
    ):
        await uc.delete_report(
            actor=actor, report_id="rep-1",
            reason="False positive — duplicado",
        )

    assert attachment.is_deleted is True
    mock_db.delete.assert_called_once_with(report)
    assert captured.get("reason") == "False positive — duplicado"
    assert captured.get("report_id") == "rep-1"


# ── preview_template (Task 10) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_returns_pdf_without_persisting():
    """preview_template returns bytes and never touches db.add/commit/delete."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    template = MagicMock(
        id="tpl-1", tenant_id="t1", current_version_id="v-1",
    )
    version = MagicMock(
        id="v-1", version=1,
        blocks=[{"type": "alert_metadata", "params": {}}],
        header_config={"title_template": "STD"},
        footer_config={},
        css_overrides=None,
    )
    case = MagicMock(id="c1", tenant_id="t1")
    fake_pdf = b"%PDF-1.4\npreview"

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[template, version, case])

    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="t1", is_global=False,
    )

    async def fake_build_snapshot(db, c):
        return {"case": {"id": c.id, "tlp": "WHITE"}}

    async def fake_html_to_pdf(**kwargs):
        return fake_pdf

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "backend.src.modules.alert_reports.application.use_cases.build_data_snapshot",
        new=fake_build_snapshot,
    ), patch(
        "backend.src.modules.alert_reports.application.use_cases.html_to_pdf",
        new=fake_html_to_pdf,
    ), patch.object(
        uc.renderer, "render", return_value="<html>...</html>",
    ):
        pdf = await uc.preview_template(
            actor=actor,
            template_id="tpl-1",
            sample_case_id="c1",
        )

    assert pdf == fake_pdf
    # The preview must not write to the DB
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.delete.assert_not_called()
    mock_db.flush.assert_not_called()


@pytest.mark.asyncio
async def test_preview_uses_overrides_instead_of_stored_version():
    """Overrides supplied by editor take precedence over version snapshot."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportGenerationUseCases,
    )
    template = MagicMock(
        id="tpl-1", tenant_id="t1", current_version_id="v-1",
    )
    version = MagicMock(
        id="v-1",
        blocks=[{"type": "alert_metadata", "params": {}}],
        header_config={"title_template": "ORIGINAL"},
        footer_config={"footer_text": "old"},
        css_overrides=None,
    )
    case = MagicMock(id="c1", tenant_id="t1")
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[template, version, case])

    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="t1", is_global=False,
    )

    captured: dict = {}

    async def fake_build_snapshot(db, c):
        return {"case": {"id": c.id, "tlp": "WHITE"}}

    async def fake_html_to_pdf(**kwargs):
        captured["header"] = kwargs["header_config"]
        captured["footer"] = kwargs["footer_config"]
        return b"%PDF-1.4\nx"

    def fake_render(**kwargs):
        captured["blocks"] = kwargs["blocks"]
        return "<html>...</html>"

    uc = AlertReportGenerationUseCases(db=mock_db, system_user_id="sys")
    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "backend.src.modules.alert_reports.application.use_cases.build_data_snapshot",
        new=fake_build_snapshot,
    ), patch(
        "backend.src.modules.alert_reports.application.use_cases.html_to_pdf",
        new=fake_html_to_pdf,
    ), patch.object(
        uc.renderer, "render", side_effect=fake_render,
    ):
        await uc.preview_template(
            actor=actor,
            template_id="tpl-1",
            sample_case_id="c1",
            blocks_override=[
                {"type": "text", "params": {"content_template": "OVERRIDE"}},
            ],
            header_override={"title_template": "OVERRIDDEN"},
            footer_override={"footer_text": "new footer"},
        )

    assert captured["blocks"] == [
        {"type": "text", "params": {"content_template": "OVERRIDE"}},
    ]
    assert captured["header"]["title_template"] == "OVERRIDDEN"
    assert captured["footer"]["footer_text"] == "new footer"


# ── tenant isolation + template cloning (Task 11) ──────────────────────


@pytest.mark.asyncio
async def test_require_template_access_rejects_cross_tenant_non_global():
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    uc = AlertReportTemplateUseCases(db=AsyncMock())
    template = MagicMock(tenant_id="tenant-A")
    actor = MagicMock(
        user_id="u1", tenant_id="tenant-B", is_global=False,
    )
    with pytest.raises(PermissionDeniedError, match="otro tenant"):
        uc._require_template_access(actor, template)


@pytest.mark.asyncio
async def test_require_template_access_allows_global_admin_cross_tenant():
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    uc = AlertReportTemplateUseCases(db=AsyncMock())
    template = MagicMock(tenant_id="tenant-A")
    actor = MagicMock(
        user_id="u1", tenant_id="tenant-B", is_global=True,
    )
    # Should not raise
    uc._require_template_access(actor, template)


@pytest.mark.asyncio
async def test_require_template_access_allows_anyone_for_global_template():
    """tenant_id IS NULL template → access granted regardless of actor tenant."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    uc = AlertReportTemplateUseCases(db=AsyncMock())
    global_template = MagicMock(tenant_id=None)
    actor = MagicMock(
        user_id="u1", tenant_id="tenant-A", is_global=False,
    )
    uc._require_template_access(actor, global_template)


@pytest.mark.asyncio
async def test_clone_template_copies_current_version_into_new_tenant():
    """Clone of a global template produces a fresh template + v1 for target tenant."""
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    source = MagicMock(
        id="tpl-source", tenant_id=None, current_version_id="v-source",
        name="SOC estándar", description="Default global",
        code="soc_standard",
    )
    source_version = MagicMock(
        id="v-source", version=4,
        name_snapshot="SOC estándar",
        header_config={"show_logo": True},
        footer_config={"footer_text": "Confidencial"},
        blocks=[{"type": "alert_metadata", "params": {}}],
        css_overrides=None,
    )

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(side_effect=[source, source_version])

    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="tenant-B",
        is_global=True,
    )

    captured: list = []

    def fake_add(obj):
        captured.append(obj)

    mock_db.add = MagicMock(side_effect=fake_add)

    uc = AlertReportTemplateUseCases(db=mock_db)
    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ):
        cloned = await uc.clone_template_for_tenant(
            actor=actor,
            template_id="tpl-source",
            target_tenant_id="tenant-B",
            new_code="soc_standard_b",
        )

    # Should have inserted a new template + v1 version row
    template_rows = [c for c in captured if hasattr(c, "code")]
    version_rows = [c for c in captured if hasattr(c, "version")]
    assert len(template_rows) == 1
    assert len(version_rows) == 1
    assert template_rows[0].tenant_id == "tenant-B"
    assert template_rows[0].code == "soc_standard_b"
    assert version_rows[0].version == 1
    assert version_rows[0].blocks == [
        {"type": "alert_metadata", "params": {}}
    ]
    assert version_rows[0].header_config == {"show_logo": True}
    assert cloned is template_rows[0]


@pytest.mark.asyncio
async def test_clone_template_tenant_admin_cannot_clone_to_other_tenant():
    """Non-global admin can only clone into own tenant."""
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.alert_reports.application.use_cases import (
        AlertReportTemplateUseCases,
    )
    source = MagicMock(
        id="tpl-source", tenant_id=None, current_version_id="v-source",
        code="soc_standard",
    )
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=source)

    actor = MagicMock(
        user_id="u1", role_id="r1", tenant_id="tenant-A",
        is_global=False,
    )

    uc = AlertReportTemplateUseCases(db=mock_db)
    with patch(
        "backend.src.modules.alert_reports.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ):
        with pytest.raises(PermissionDeniedError, match="global"):
            await uc.clone_template_for_tenant(
                actor=actor,
                template_id="tpl-source",
                target_tenant_id="tenant-B",  # NOT actor.tenant_id
                new_code="soc_b",
            )


# ── default SOC template seed (Task 12) ─────────────────────────────────


def test_default_soc_template_seeded():
    """A global template with code='soc_standard' exists and covers the
    8 sections from master spec §7 acceptance criteria."""
    from sqlalchemy import text

    async def _check():
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(_get_real_url())
        try:
            async with engine.connect() as conn:
                template_row = (await conn.execute(text(
                    "SELECT id, current_version_id, is_default, is_active "
                    "FROM alert_report_templates "
                    "WHERE code = 'soc_standard' AND tenant_id IS NULL"
                ))).fetchone()
                if not template_row:
                    return None
                version_row = (await conn.execute(text(
                    "SELECT version, blocks "
                    "FROM alert_report_template_versions "
                    "WHERE id = :vid"
                ), {"vid": template_row[1]})).fetchone()
                return {
                    "is_default": template_row[2],
                    "is_active": template_row[3],
                    "version": version_row[0] if version_row else None,
                    "blocks": version_row[1] if version_row else None,
                }
        finally:
            await engine.dispose()

    info = asyncio.run(_check())
    assert info is not None, (
        "Global SOC standard template missing — check seed migration"
    )
    assert info["is_default"] is True
    assert info["is_active"] is True
    assert info["version"] == 1

    block_types = [b["type"] for b in info["blocks"]]
    # Master spec §7 acceptance: the 8 sections that operators expect
    for required in (
        "alert_metadata", "priority_calculation", "triage_analysis",
        "evidence_grid", "forensic_artifacts_list", "behavior_relation",
        "mitre_techniques", "recommendations",
    ):
        assert required in block_types, f"missing block '{required}'"


# ── router smoke tests (Task 13) ────────────────────────────────────────


def test_router_exposes_expected_paths():
    """All endpoints in spec §5 are registered with the right HTTP verbs."""
    from backend.src.modules.alert_reports.router import router

    routes = {
        (r.path, tuple(sorted(r.methods))) for r in router.routes
    }
    expected = {
        # Templates
        ("/api/v1/alert-report-templates", ("GET",)),
        ("/api/v1/alert-report-templates", ("POST",)),
        ("/api/v1/alert-report-templates/{template_id}", ("GET",)),
        ("/api/v1/alert-report-templates/{template_id}", ("PATCH",)),
        ("/api/v1/alert-report-templates/{template_id}", ("DELETE",)),
        (
            "/api/v1/alert-report-templates/{template_id}/set-default",
            ("POST",),
        ),
        (
            "/api/v1/alert-report-templates/{template_id}/versions",
            ("GET",),
        ),
        (
            "/api/v1/alert-report-templates/{template_id}/preview",
            ("POST",),
        ),
        (
            "/api/v1/alert-report-templates/{template_id}/clone",
            ("POST",),
        ),
        # Generation
        ("/api/v1/cases/{case_id}/alert-reports", ("GET",)),
        ("/api/v1/cases/{case_id}/alert-reports", ("POST",)),
        ("/api/v1/alert-reports/{report_id}", ("GET",)),
        ("/api/v1/alert-reports/{report_id}", ("DELETE",)),
        ("/api/v1/alert-reports/{report_id}/download", ("GET",)),
        ("/api/v1/alert-reports/{report_id}/verify", ("GET",)),
    }
    missing = expected - routes
    assert not missing, f"Missing alert_reports routes: {missing}"


def test_main_app_includes_alert_reports_router():
    """FastAPI app boots with the alert_reports router mounted."""
    from backend.src.main import create_app
    app = create_app()
    paths = {
        getattr(r, "path", "") for r in app.routes
        if getattr(r, "path", "").startswith("/api/v1/alert-report")
        or getattr(r, "path", "").startswith("/api/v1/cases/{case_id}/alert-reports")
    }
    assert any("alert-report-templates" in p for p in paths)
    assert any("cases/{case_id}/alert-reports" in p for p in paths)
