import base64
import uuid
from datetime import datetime, timezone

import aiosmtplib
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.config import get_settings
from backend.src.modules.email_config.infrastructure.models import SmtpConfigModel

SMTP_CONFIG_ID = "default"


def _get_fernet() -> Fernet:
    settings = get_settings()
    key_bytes = settings.SECRET_KEY.encode()[:32].ljust(32, b"\x00")
    return Fernet(base64.urlsafe_b64encode(key_bytes))


class SmtpConfigUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> SmtpConfigModel | None:
        result = await self.db.execute(
            select(SmtpConfigModel).where(SmtpConfigModel.id == SMTP_CONFIG_ID)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_email: str,
        from_name: str,
        use_tls: bool,
        is_enabled: bool,
    ) -> SmtpConfigModel:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(SmtpConfigModel).where(SmtpConfigModel.id == SMTP_CONFIG_ID)
        )
        config = result.scalar_one_or_none()

        encrypted_password: str | None = None
        if password:
            encrypted_password = _get_fernet().encrypt(password.encode()).decode()

        if config is None:
            config = SmtpConfigModel(
                id=SMTP_CONFIG_ID,
                host=host, port=port, username=username,
                password=encrypted_password,
                from_email=from_email, from_name=from_name,
                use_tls=use_tls, is_enabled=is_enabled,
                updated_at=now,
            )
            self.db.add(config)
        else:
            config.host = host
            config.port = port
            config.username = username
            if password == "":
                config.password = None   # explicit clear
            elif password:
                config.password = encrypted_password
            # if password is None: keep existing (no-op)
            config.from_email = from_email
            config.from_name = from_name
            config.use_tls = use_tls
            config.is_enabled = is_enabled
            config.updated_at = now

        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def test_connection(self) -> dict:
        config = await self.get()
        if not config or not config.host:
            return {"success": False, "message": "SMTP no configurado"}

        password: str | None = None
        if config.password:
            try:
                password = _get_fernet().decrypt(config.password.encode()).decode()
            except Exception:
                return {"success": False, "message": "Error desencriptando contraseña — guarda la config de nuevo"}

        use_tls, start_tls = resolve_tls_mode(config.port, config.use_tls)
        try:
            smtp = aiosmtplib.SMTP(
                hostname=config.host,
                port=config.port,
                use_tls=use_tls,
                start_tls=start_tls,
                timeout=10,
            )
            await smtp.connect()
            if config.username and password:
                await smtp.login(config.username, password)
            await smtp.quit()
            return {"success": True, "message": f"Conexión exitosa a {config.host}:{config.port}"}
        except Exception as e:
            return {"success": False, "message": str(e)}


def resolve_tls_mode(port: int, use_tls_flag: bool) -> tuple[bool, bool]:
    """Map (port, user-intent flag) to aiosmtplib's (use_tls, start_tls) pair.

    SMTP has three modes that the single `use_tls` checkbox in the CMS UI
    can't represent cleanly, so we derive the right combination from the
    port + the flag:

    * Port 465  -> implicit TLS (SMTPS, RFC 8314). Connection is encrypted
                   from byte 0. Required by Hostinger, Gmail SSL, etc.
                   `use_tls=True, start_tls=False`.
    * Port 587  -> STARTTLS upgrade. Connection starts plain, then the
                   client issues STARTTLS to upgrade. The standard
                   submission port.
                   `use_tls=False, start_tls=True`.
    * Other     -> respect the flag: True means STARTTLS, False means plain.

    The previous implementation hardcoded `use_tls=False` and routed the
    flag into `start_tls`, which silently broke implicit-TLS servers
    (the client opened plain on 465 and timed out waiting for a "220
    ready" greeting that was already wrapped in TLS).
    """
    if not use_tls_flag:
        return (False, False)
    if port == 465:
        return (True, False)
    return (False, True)
