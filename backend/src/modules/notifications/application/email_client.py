import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from backend.src.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, html_body: str) -> None:
    """
    Envía email async usando aiosmtplib.
    Si SMTP_HOST no está configurado, registra warning y no hace nada.
    Los errores de envío se registran pero no se relanzman para no bloquear
    la operación principal.
    """
    settings = get_settings()
    if not settings.SMTP_HOST:
        logger.warning("SMTP_HOST no configurado — email omitido para %s", to_email)
        return

    message = MIMEMultipart("alternative")
    message["From"] = settings.SMTP_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD.get_secret_value() or None,
            use_tls=False,
            start_tls=True,
        )
        logger.info("Email enviado a %s: %s", to_email, subject)
    except Exception as e:
        logger.error("Error enviando email a %s: %s", to_email, str(e))
