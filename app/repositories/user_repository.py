from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Address, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_address_by_id(self, address_id: int) -> Address | None:
        stmt = select(Address).where(Address.id == address_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_addresses_by_user(self, user_id: int) -> list[Address]:
        stmt = select(Address).where(Address.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
