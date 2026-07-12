from datetime import timedelta

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictException, NotFoundException, UnauthorizedException, ValidationException
from app.core.security import (
    blacklist_refresh_token,
    create_access_token,
    create_email_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import PasswordResetConfirm, TokenResponse, UserCreate, UserLogin
from app.tasks.email_tasks import send_password_reset_email, send_verification_email


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings, redis_client: redis.Redis) -> None:
        self.session = session
        self.settings = settings
        self.redis = redis_client
        self.user_repo = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        existing = await self.user_repo.get_by_email(str(data.email))
        if existing:
            raise ConflictException("Email already registered")

        user = User(
            email=str(data.email),
            hashed_password=get_password_hash(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            role="customer",
            is_active=True,
            is_verified=False,
        )
        await self.user_repo.create(user)
        token = create_email_token(user.id, self.settings)
        send_verification_email.delay(user.email, token)
        return user

    async def verify_email(self, token: str) -> User:
        payload = decode_token(token, self.settings)
        if payload.get("type") != "verify":
            raise ValidationException("Invalid verification token")

        user_id = int(payload.get("sub", 0))
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")

        user.is_verified = True
        await self.user_repo.update(user)
        return user

    async def login(self, data: UserLogin) -> TokenResponse:
        user = await self.user_repo.get_by_email(str(data.email))
        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedException("Invalid credentials")

        if not user.is_active:
            raise UnauthorizedException("Account disabled")

        access = create_access_token({"sub": str(user.id)}, self.settings)
        refresh = create_refresh_token({"sub": str(user.id)}, self.settings)
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, self.settings)
        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type")

        jti = payload.get("jti")
        if jti and await self.redis.get(f"token_blacklist:{jti}"):
            raise UnauthorizedException("Refresh token revoked")

        user_id = int(payload.get("sub", 0))
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("User not found")

        access = create_access_token({"sub": str(user.id)}, self.settings)
        new_refresh = create_refresh_token({"sub": str(user.id)}, self.settings)
        await blacklist_refresh_token(refresh_token, self.settings, self.redis)
        return TokenResponse(access_token=access, refresh_token=new_refresh)

    async def logout(self, refresh_token: str) -> None:
        await blacklist_refresh_token(refresh_token, self.settings, self.redis)

    async def request_password_reset(self, email: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if user:
            token = create_password_reset_token(user.id, self.settings)
            send_password_reset_email.delay(user.email, token)

    async def confirm_password_reset(self, data: PasswordResetConfirm) -> User:
        payload = decode_token(data.token, self.settings)
        if payload.get("type") != "password_reset":
            raise ValidationException("Invalid reset token")

        user_id = int(payload.get("sub", 0))
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")

        user.hashed_password = get_password_hash(data.new_password)
        await self.user_repo.update(user)
        return user
