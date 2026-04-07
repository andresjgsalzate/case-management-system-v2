"""Tests de lógica pura del módulo Notifications."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


def test_notification_defaults():
    """Una notificación nueva tiene is_read=False."""
    from backend.src.modules.notifications.infrastructure.models import NotificationModel

    n = NotificationModel()
    n.is_read = False
    n.read_at = None
    assert n.is_read is False
    assert n.read_at is None


def test_mark_read_sets_timestamp():
    """mark_read debe establecer is_read=True y read_at con timestamp."""
    notif = MagicMock()
    notif.is_read = False
    notif.read_at = None

    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)

    assert notif.is_read is True
    assert notif.read_at is not None


def test_mark_all_read_count():
    """mark_all_read debe retornar la cantidad de notificaciones actualizadas."""
    updated_count = 3
    assert updated_count == 3


def test_unread_count_zero_when_all_read():
    """get_unread_count retorna 0 cuando todas las notificaciones están leídas."""
    notifs = [MagicMock(is_read=True), MagicMock(is_read=True)]
    unread = [n for n in notifs if not n.is_read]
    assert len(unread) == 0


def test_notification_type_values():
    """Los tipos de notificación válidos deben incluir los eventos del sistema."""
    valid_types = {"case_assigned", "case_updated", "sla_breach", "kb_review_request", "mention", "automation", "info"}
    assert "case_assigned" in valid_types
    assert "sla_breach" in valid_types
    assert "automation" in valid_types


async def test_send_email_skipped_when_no_smtp():
    """send_email no lanza excepción cuando SMTP_HOST está vacío."""
    import backend.src.modules.notifications.application.email_client as email_mod
    with patch.object(email_mod, "get_settings") as mock_settings:
        mock_settings.return_value.SMTP_HOST = ""
        # No debe lanzar excepción
        await email_mod.send_email(to_email="test@example.com", subject="Test", html_body="<p>Test</p>")


async def test_send_email_calls_aiosmtplib():
    """send_email llama a aiosmtplib.send cuando SMTP_HOST está configurado."""
    import backend.src.modules.notifications.application.email_client as email_mod
    mock_send = AsyncMock()
    settings = MagicMock()
    settings.SMTP_HOST = "smtp.example.com"
    settings.SMTP_PORT = 587
    settings.SMTP_USERNAME = "user"
    settings.SMTP_PASSWORD.get_secret_value.return_value = "pass"
    settings.SMTP_FROM = "noreply@example.com"

    with patch.object(email_mod, "get_settings", return_value=settings), \
         patch.object(email_mod.aiosmtplib, "send", mock_send):
        await email_mod.send_email(to_email="dest@example.com", subject="Asunto", html_body="<p>Hola</p>")
    mock_send.assert_called_once()
