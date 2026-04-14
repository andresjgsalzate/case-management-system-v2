import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from backend.src.core.config import get_settings

logger = logging.getLogger(__name__)


# ── SMTP resolution ───────────────────────────────────────────────────────────

async def _get_smtp_params() -> dict | None:
    """Return SMTP params from DB config (if enabled) else from .env. Returns None if unconfigured."""
    try:
        from backend.src.core.database import AsyncSessionLocal
        from backend.src.modules.email_config.application.smtp_use_cases import (
            SmtpConfigUseCases, _get_fernet,
        )
        async with AsyncSessionLocal() as db:
            uc = SmtpConfigUseCases(db)
            config = await uc.get()
            if config and config.is_enabled and config.host:
                password: str | None = None
                if config.password:
                    try:
                        password = _get_fernet().decrypt(config.password.encode()).decode()
                    except Exception:
                        pass
                return {
                    "host": config.host, "port": config.port,
                    "username": config.username, "password": password,
                    "from_email": config.from_email, "from_name": config.from_name,
                    "use_tls": config.use_tls,
                }
    except Exception as e:
        logger.debug("Could not load SMTP from DB (%s), falling back to .env", e)

    settings = get_settings()
    if settings.SMTP_HOST:
        return {
            "host": settings.SMTP_HOST, "port": settings.SMTP_PORT,
            "username": settings.SMTP_USERNAME or None,
            "password": settings.SMTP_PASSWORD.get_secret_value() or None,
            "from_email": settings.SMTP_FROM, "from_name": "CaseManager",
            "use_tls": True,
        }
    return None


# ── Email renderer ────────────────────────────────────────────────────────────

def _fmt(text: str, variables: dict) -> str:
    try:
        return text.format_map({k: (v or "") for k, v in variables.items()})
    except Exception:
        return text


def _render_block(block: dict, variables: dict) -> str:
    block_type = block.get("type", "")
    props = block.get("props", {})

    if block_type == "header":
        bg = props.get("bg_color", "#1e40af")
        title = _fmt(str(props.get("title", "")), variables)
        logo_url = props.get("logo_url", "")
        logo_html = f'<img src="{logo_url}" alt="Logo" style="max-height:40px;display:block;margin-bottom:8px;">' if logo_url else ""
        title_html = f'<h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:700;">{title}</h1>' if title else ""
        return f'<tr><td style="background:{bg};padding:24px 32px;">{logo_html}{title_html}</td></tr>'

    if block_type == "hero":
        bg = props.get("bg_color", "#eff6ff")
        tc = props.get("text_color", "#1e40af")
        title = _fmt(str(props.get("title", "")), variables)
        subtitle = _fmt(str(props.get("subtitle", "")), variables)
        t_html = f'<h2 style="margin:0 0 8px;color:{tc};font-size:24px;font-weight:700;">{title}</h2>' if title else ""
        s_html = f'<p style="margin:0;color:{tc};font-size:15px;opacity:.8;">{subtitle}</p>' if subtitle else ""
        return f'<tr><td style="background:{bg};padding:32px;text-align:center;">{t_html}{s_html}</td></tr>'

    if block_type in ("body", "text"):
        content = _fmt(str(props.get("content", "")), variables).replace("\n", "<br>")
        return f'<tr><td style="padding:24px 32px;color:#374151;font-size:15px;line-height:1.6;">{content}</td></tr>'

    if block_type == "button":
        label = _fmt(str(props.get("label", "Ver")), variables)
        url = _fmt(str(props.get("url", "#")), variables)
        bg = props.get("bg_color", "#1e40af")
        tc = props.get("text_color", "#ffffff")
        return (f'<tr><td style="padding:16px 32px;text-align:center;">'
                f'<a href="{url}" style="display:inline-block;background:{bg};color:{tc};'
                f'padding:12px 28px;border-radius:6px;text-decoration:none;font-size:15px;font-weight:600;">'
                f'{label}</a></td></tr>')

    if block_type == "divider":
        color = props.get("color", "#e5e7eb")
        thickness = props.get("thickness", 1)
        return f'<tr><td style="padding:0 32px;"><hr style="border:none;border-top:{thickness}px solid {color};margin:8px 0;"></td></tr>'

    if block_type == "footer":
        bg = props.get("bg_color", "#f9fafb")
        tc = props.get("text_color", "#6b7280")
        content = _fmt(str(props.get("content", "")), variables)
        return f'<tr><td style="background:{bg};padding:16px 32px;text-align:center;color:{tc};font-size:12px;">{content}</td></tr>'

    if block_type == "data_table":
        rows = props.get("rows", [])
        rows_html = "".join(
            f'<tr style="border-bottom:1px solid #e5e7eb;">'
            f'<td style="color:#6b7280;font-size:13px;padding:8px 4px;width:40%;">{r.get("label","")}</td>'
            f'<td style="color:#111827;font-size:13px;font-weight:500;padding:8px 4px;">{_fmt(str(r.get("value","")), variables)}</td>'
            f'</tr>'
            for r in rows
        )
        return (f'<tr><td style="padding:16px 32px;">'
                f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
                f'{rows_html}</table></td></tr>')

    if block_type == "alert":
        alert_type = props.get("alert_type", "info")
        message = _fmt(str(props.get("message", "")), variables)
        colors = {
            "info":    ("#eff6ff", "#1e40af", "#bfdbfe"),
            "warning": ("#fffbeb", "#92400e", "#fde68a"),
            "error":   ("#fef2f2", "#991b1b", "#fecaca"),
            "success": ("#f0fdf4", "#166534", "#bbf7d0"),
        }
        bg, tc, border = colors.get(alert_type, colors["info"])
        return (f'<tr><td style="padding:16px 32px;">'
                f'<div style="background:{bg};border:1px solid {border};border-radius:6px;'
                f'padding:12px 16px;color:{tc};font-size:14px;">{message}</div></td></tr>')

    if block_type == "image":
        url = props.get("url", "")
        alt = props.get("alt", "")
        width = props.get("width", "100%")
        if not url:
            return ""
        return (f'<tr><td style="padding:16px 32px;text-align:center;">'
                f'<img src="{url}" alt="{alt}" width="{width}" style="max-width:100%;display:block;margin:0 auto;">'
                f'</td></tr>')

    if block_type == "two_columns":
        left_html = "".join(_render_block(b, variables) for b in props.get("left", []))
        right_html = "".join(_render_block(b, variables) for b in props.get("right", []))
        return (f'<tr><td style="padding:16px 32px;">'
                f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'<td width="48%" valign="top"><table width="100%">{left_html}</table></td>'
                f'<td width="4%"></td>'
                f'<td width="48%" valign="top"><table width="100%">{right_html}</table></td>'
                f'</tr></table></td></tr>')

    return ""


def render_email_html(blocks: list, variables: dict) -> str:
    """Convert blocks JSON to full email-compatible HTML."""
    inner = "".join(_render_block(b, variables) for b in blocks)
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td align="center" style="padding:20px 0;">'
        '<table width="600" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border-radius:8px;overflow:hidden;'
        'box-shadow:0 1px 4px rgba(0,0,0,.08);">'
        f'{inner}'
        '</table></td></tr></table></body></html>'
    )


# ── Send email ────────────────────────────────────────────────────────────────

async def send_email(to_email: str, subject: str, html_body: str) -> None:
    params = await _get_smtp_params()
    if not params:
        logger.warning("SMTP no configurado — email omitido para %s", to_email)
        return

    message = MIMEMultipart("alternative")
    from_label = f"{params['from_name']} <{params['from_email']}>" if params.get("from_name") else params["from_email"]
    message["From"] = from_label
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=params["host"],
            port=params["port"],
            username=params["username"] or None,
            password=params["password"] or None,
            use_tls=False,
            start_tls=params["use_tls"],
        )
        logger.info("Email enviado a %s: %s", to_email, subject)
    except Exception as e:
        logger.error("Error enviando email a %s: %s", to_email, str(e))
