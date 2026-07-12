import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import AddressCreate, UserUpdate
from app.services.user_service import UserService


@pytest.fixture
def user_service(db_session: AsyncSession):
    return UserService(db_session)


@pytest.mark.asyncio
async def test_update_profile(user_service: UserService, db_session: AsyncSession):
    user = User(email="profile@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()

    updated = await user_service.update_profile(user.id, UserUpdate(first_name="John"))
    assert updated.first_name == "John"


@pytest.mark.asyncio
async def test_create_address(user_service: UserService, db_session: AsyncSession):
    user = User(email="addr@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()

    address = await user_service.create_address(
        user.id,
        AddressCreate(
            street="123 Main",
            city="City",
            state="ST",
            postal_code="12345",
            country="US",
        ),
    )
    assert address.user_id == user.id
    assert address.street == "123 Main"


@pytest.mark.asyncio
async def test_list_addresses(user_service: UserService, db_session: AsyncSession):
    user = User(email="addr2@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()

    await user_service.create_address(
        user.id,
        AddressCreate(
            street="456 Oak",
            city="Town",
            state="TS",
            postal_code="54321",
            country="US",
        ),
    )
    addresses = await user_service.list_addresses(user.id)
    assert len(addresses) == 1
