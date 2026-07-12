import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.main import app


def _get_test_database_url() -> str:
    base_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ecommerce",
    )
    return base_url.rsplit("/", 1)[0] + "/ecommerce_test"


def _get_test_redis_url(base_default: str = "redis://localhost:6379/1") -> str:
    base_url = os.environ.get("REDIS_URL", base_default)
    return base_url.rsplit("/", 1)[0] + "/15"


TEST_DATABASE_URL = _get_test_database_url()
TEST_REDIS_URL = _get_test_redis_url()
TEST_CELERY_BROKER_URL = _get_test_redis_url(
    os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
)
TEST_CELERY_RESULT_BACKEND = _get_test_redis_url(
    os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)


def get_test_settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        celery_broker_url=TEST_CELERY_BROKER_URL,
        celery_result_backend=TEST_CELERY_RESULT_BACKEND,
        secret_key=os.environ.get(
            "SECRET_KEY", "test-secret-key-for-tests-only-min-32-chars"
        ),
        environment="development",
        debug=True,
    )


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        transaction = await session.begin()
        yield session
        await transaction.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = get_test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def settings() -> Settings:
    return get_test_settings()


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, db_session: AsyncSession, settings: Settings):
    from app.models.user import User
    from app.core.security import get_password_hash

    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("Password123!"),
        first_name="Test",
        last_name="User",
        role="customer",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = create_access_token({"sub": str(user.id)}, settings)
    return {"Authorization": f"Bearer {token}", "user_id": user.id}


@pytest_asyncio.fixture
async def admin_headers(async_client: AsyncClient, db_session: AsyncSession, settings: Settings):
    from app.models.user import User
    from app.core.security import get_password_hash

    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("Password123!"),
        first_name="Admin",
        last_name="User",
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = create_access_token({"sub": str(user.id)}, settings)
    return {"Authorization": f"Bearer {token}", "user_id": user.id}
