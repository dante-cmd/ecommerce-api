from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Order)

    def _items_eager(self):
        return selectinload(Order.items)

    async def get_by_id_with_items(self, order_id: int) -> Order | None:
        stmt = select(Order).where(Order.id == order_id).options(self._items_eager())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .options(self._items_eager())
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(
        self, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list[Order]:
        stmt = select(Order).options(self._items_eager()).order_by(Order.created_at.desc())
        if status:
            stmt = stmt.where(Order.status == status)
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())
