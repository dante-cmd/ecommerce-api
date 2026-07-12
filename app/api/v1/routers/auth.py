from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi import HTTPException
from fastapi.security import HTTPBearer
from app.core.limiter import limiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.schemas.common import MessageResponse
from app.schemas.user import (
    EmailVerifyRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
)
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer(auto_error=False)

DbDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RedisDep = Annotated[redis.Redis, Depends(get_redis)]


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: UserCreate,
    db: DbDep,
    settings: SettingsDep,
    redis_client: RedisDep,
):
    service = AuthService(db, settings, redis_client)
    await service.register(data)
    return MessageResponse(message="Registration successful. Please verify your email.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    data: EmailVerifyRequest,
    db: DbDep,
    settings: SettingsDep,
    redis_client: RedisDep,
):
    service = AuthService(db, settings, redis_client)
    await service.verify_email(data.token)
    return MessageResponse(message="Email verified successfully")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    data: UserLogin,
    db: DbDep,
    settings: SettingsDep,
    redis_client: RedisDep,
    response: Response,
):
    service = AuthService(db, settings, redis_client)
    tokens = await service.login(data)
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,
    )
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: DbDep,
    settings: SettingsDep,
    redis_client: RedisDep,
):
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        refresh = request.headers.get("X-Refresh-Token")
    if not refresh:
        raise HTTPException(status_code=400, detail="Refresh token required")

    service = AuthService(db, settings, redis_client)
    tokens = await service.refresh_access_token(refresh)
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,
    )
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    redis_client: RedisDep,
    response: Response,
):
    refresh = request.cookies.get("refresh_token")
    if refresh:
        service = AuthService(db, settings, redis_client)
        await service.logout(refresh)
    response.delete_cookie("refresh_token")
    return MessageResponse(message="Logged out successfully")


@router.post("/password-reset-request", response_model=MessageResponse)
@limiter.limit("5/minute")
async def password_reset_request(
    request: Request,
    data: PasswordResetRequest,
    db: DbDep,
    settings: SettingsDep,
    redis_client: RedisDep,
):
    service = AuthService(db, settings, redis_client)
    await service.request_password_reset(str(data.email))
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/password-reset-confirm", response_model=MessageResponse)
async def password_reset_confirm(
    data: PasswordResetConfirm,
    db: DbDep,
    settings: SettingsDep,
    redis_client: RedisDep,
):
    service = AuthService(db, settings, redis_client)
    await service.confirm_password_reset(data)
    return MessageResponse(message="Password reset successfully")
