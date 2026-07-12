from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Payment)

    async def get_by_order_id(self, order_id: int) -> Payment | None:
        stmt = select(Payment).where(Payment.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        stmt = select(Payment).where(Payment.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider_payment_id(self, provider_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.provider_payment_id == provider_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
