import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_get_by_email(db_session: AsyncSession):
    user = User(email="repo@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()

    repo = UserRepository(db_session)
    found = await repo.get_by_email("repo@example.com")
    assert found is not None
    assert found.id == user.id


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    repo = UserRepository(db_session)
    found = await repo.get_by_id(99999)
    assert found is None
