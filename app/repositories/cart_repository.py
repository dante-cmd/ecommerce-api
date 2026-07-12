from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem
from app.models.product import ProductVariant
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Cart)

    def _items_eager(self):
        return selectinload(Cart.items).selectinload(CartItem.variant).selectinload(
            ProductVariant.product
        )

    async def get_by_id_with_items(self, cart_id: int) -> Cart | None:
        stmt = (
            select(Cart)
            .where(Cart.id == cart_id)
            .options(self._items_eager())
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> Cart | None:
        stmt = select(Cart).where(Cart.user_id == user_id).options(self._items_eager())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_session_id(self, session_id: str) -> Cart | None:
        stmt = select(Cart).where(Cart.session_id == session_id).options(self._items_eager())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_cart_item(self, cart_id: int, variant_id: int) -> CartItem | None:
        stmt = (
            select(CartItem)
            .where(CartItem.cart_id == cart_id, CartItem.variant_id == variant_id)
            .options(selectinload(CartItem.variant).selectinload(ProductVariant.product))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_cart_item_by_id(self, item_id: int) -> CartItem | None:
        stmt = (
            select(CartItem)
            .where(CartItem.id == item_id)
            .options(selectinload(CartItem.variant).selectinload(ProductVariant.product))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
