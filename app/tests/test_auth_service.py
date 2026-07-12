import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.redis import get_redis_pool
from app.schemas.user import UserCreate, UserLogin
from app.services.auth_service import AuthService


@pytest.fixture
def auth_service(db_session: AsyncSession, settings: Settings):
    redis_client = get_redis_pool(settings)
    return AuthService(db_session, settings, redis_client)


@pytest.mark.asyncio
async def test_register_user(auth_service: AuthService, db_session: AsyncSession):
    data = UserCreate(email="new@example.com", password="Password123!")
    user = await auth_service.register(data)
    assert user.email == "new@example.com"
    assert user.role == "customer"
    assert not user.is_verified


@pytest.mark.asyncio
async def test_register_duplicate_email(auth_service: AuthService, db_session: AsyncSession):
    data = UserCreate(email="dup@example.com", password="Password123!")
    await auth_service.register(data)
    with pytest.raises(ConflictException):
        await auth_service.register(data)


@pytest.mark.asyncio
async def test_login_success(auth_service: AuthService, db_session: AsyncSession):
    data = UserCreate(email="login@example.com", password="Password123!")
    await auth_service.register(data)
    tokens = await auth_service.login(UserLogin(email="login@example.com", password="Password123!"))
    assert tokens.access_token
    assert tokens.refresh_token


@pytest.mark.asyncio
async def test_login_invalid_password(auth_service: AuthService, db_session: AsyncSession):
    data = UserCreate(email="badlogin@example.com", password="Password123!")
    await auth_service.register(data)
    with pytest.raises(UnauthorizedException):
        await auth_service.login(UserLogin(email="badlogin@example.com", password="WrongPass!"))
