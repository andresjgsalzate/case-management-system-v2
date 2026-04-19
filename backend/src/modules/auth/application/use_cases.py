import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.src.core.security import verify_password, create_access_token
from backend.src.core.config import get_settings
from backend.src.core.exceptions import UnauthorizedError
from backend.src.modules.users.infrastructure.models import UserModel
from backend.src.modules.auth.infrastructure.models import UserSessionModel
from backend.src.modules.auth.application.dtos import LoginDTO, TokenResponseDTO


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, dto: LoginDTO, ip_address: str | None = None) -> TokenResponseDTO:
        result = await self.db.execute(
            select(UserModel).options(selectinload(UserModel.role))
            .where(UserModel.email == dto.email, UserModel.is_active == True)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(dto.password, user.hashed_password):
            raise UnauthorizedError("Invalid credentials")

        role_level = user.role.level if user.role else 1

        settings = get_settings()
        access_token = create_access_token(
            subject=user.id,
            extra_claims={
                "email": user.email,
                "role_id": user.role_id or "",
                "tenant_id": user.tenant_id or "default",
                "role_level": role_level,
            },
        )

        refresh_token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        session = UserSessionModel(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=_hash_refresh_token(refresh_token),
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self.db.add(session)
        await self.db.commit()

        return TokenResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            user={"id": user.id, "email": user.email, "full_name": user.full_name, "role_id": user.role_id},
        )

    async def refresh(self, refresh_token: str) -> TokenResponseDTO:
        token_hash = _hash_refresh_token(refresh_token)
        result = await self.db.execute(
            select(UserSessionModel).where(
                UserSessionModel.refresh_token_hash == token_hash,
                UserSessionModel.is_revoked == False,
                UserSessionModel.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise UnauthorizedError("Invalid or expired refresh token")

        # Revoke current session (token rotation)
        session.is_revoked = True

        user = await self.db.get(UserModel, session.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User not active")

        from sqlalchemy.orm import selectinload as _sl
        role_result = await self.db.execute(
            select(UserModel).options(_sl(UserModel.role)).where(UserModel.id == user.id)
        )
        user = role_result.scalar_one()
        role_level = user.role.level if user.role else 1

        settings = get_settings()
        access_token = create_access_token(
            subject=user.id,
            extra_claims={
                "email": user.email,
                "role_id": user.role_id or "",
                "tenant_id": user.tenant_id or "default",
                "role_level": role_level,
            },
        )
        new_refresh_token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        new_session = UserSessionModel(
            id=str(uuid.uuid4()),
            user_id=user.id,
            refresh_token_hash=_hash_refresh_token(new_refresh_token),
            ip_address=session.ip_address,
            expires_at=expires_at,
        )
        self.db.add(new_session)
        await self.db.commit()

        return TokenResponseDTO(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user={"id": user.id, "email": user.email, "full_name": user.full_name, "role_id": user.role_id},
        )

    async def logout(self, refresh_token: str) -> None:
        token_hash = _hash_refresh_token(refresh_token)
        result = await self.db.execute(
            select(UserSessionModel).where(UserSessionModel.refresh_token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if session:
            session.is_revoked = True
            await self.db.commit()
