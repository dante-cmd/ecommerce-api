from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.user import Address, User
from app.repositories.user_repository import UserRepository
from app.schemas.user import AddressCreate, AddressUpdate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def get_profile(self, user_id: int) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")
        return user

    async def update_profile(self, user_id: int, data: UserUpdate) -> User:
        user = await self.get_profile(user_id)
        for field in ["first_name", "last_name", "phone", "avatar_url"]:
            value = getattr(data, field)
            if value is not None:
                setattr(user, field, value)
        return await self.repo.update(user)

    async def list_addresses(self, user_id: int) -> list[Address]:
        return await self.repo.get_addresses_by_user(user_id)

    async def create_address(self, user_id: int, data: AddressCreate) -> Address:
        address = Address(
            user_id=user_id,
            label=data.label,
            street=data.street,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            country=data.country,
            is_default=data.is_default,
        )
        return await self.repo.create(address)

    async def update_address(
        self, user_id: int, address_id: int, data: AddressUpdate
    ) -> Address:
        address = await self.repo.get_address_by_id(address_id)
        if not address or address.user_id != user_id:
            raise NotFoundException("Address not found")

        for field in ["label", "street", "city", "state", "postal_code", "country", "is_default"]:
            value = getattr(data, field)
            if value is not None:
                setattr(address, field, value)
        return await self.repo.update(address)

    async def delete_address(self, user_id: int, address_id: int) -> None:
        address = await self.repo.get_address_by_id(address_id)
        if not address or address.user_id != user_id:
            raise NotFoundException("Address not found")
        await self.repo.delete(address)
