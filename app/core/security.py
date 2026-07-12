from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedException
from app.core.redis import get_redis

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
security_bearer = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], settings: Settings, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict[str, Any], settings: Settings) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError as exc:
        raise UnauthorizedException("Invalid token") from exc


async def _extract_user_id(
    credentials: HTTPAuthorizationCredentials | None,
    settings: Settings,
    redis_client: redis.Redis,
    raise_on_missing: bool,
) -> int | None:
    if credentials is None:
        if raise_on_missing:
            raise UnauthorizedException("Missing authentication token")
        return None

    token = credentials.credentials
    payload = decode_token(token, settings)

    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedException("Invalid token payload")

    jti = payload.get("jti")
    if jti and await redis_client.get(f"token_blacklist:{jti}"):
        raise UnauthorizedException("Token revoked")

    return int(user_id)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    settings: Settings = Depends(get_settings),
    redis_client: redis.Redis = Depends(get_redis),
) -> int:
    result = await _extract_user_id(credentials, settings, redis_client, raise_on_missing=True)
    assert result is not None
    return result


async def get_optional_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    settings: Settings = Depends(get_settings),
    redis_client: redis.Redis = Depends(get_redis),
) -> int | None:
    return await _extract_user_id(credentials, settings, redis_client, raise_on_missing=False)


async def blacklist_refresh_token(
    token: str, settings: Settings, redis_client: redis.Redis
) -> None:
    payload = decode_token(token, settings)
    if payload.get("type") != "refresh":
        raise UnauthorizedException("Invalid token type")

    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        ttl = int(exp - datetime.now(timezone.utc).timestamp())
        if ttl > 0:
            await redis_client.setex(f"token_blacklist:{jti}", ttl, "1")


def create_email_token(user_id: int, settings: Settings, purpose: str = "verify") -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    return jwt.encode(
        {"sub": str(user_id), "type": purpose, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_password_reset_token(user_id: int, settings: Settings) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    return jwt.encode(
        {"sub": str(user_id), "type": "password_reset", "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
