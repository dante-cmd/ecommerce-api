from __future__ import annotations

import base64
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Category, Product, ProductImage, ProductVariant, Review
from app.models.order import Order, OrderItem
from app.repositories.base import BaseRepository
from app.schemas.common import CursorPagination
from app.schemas.product import ProductSearchFilters


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Product)

    async def get_by_id(self, product_id: int) -> Product | None:
        stmt = select(Product).where(Product.id == product_id).options(selectinload(Product.category))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Product | None:
        stmt = (
            select(Product)
            .where(Product.slug == slug)
            .options(selectinload(Product.category))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_category_by_id(self, category_id: int) -> Category | None:
        stmt = select(Category).where(Category.id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_category_by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_categories(self) -> list[Category]:
        stmt = select(Category).where(Category.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_products(
        self, filters: ProductSearchFilters
    ) -> CursorPagination:
        stmt = select(Product).where(Product.is_active == True)

        if filters.category_id:
            stmt = stmt.where(Product.category_id == filters.category_id)

        if filters.min_price is not None:
            stmt = stmt.where(Product.base_price >= filters.min_price)
        if filters.max_price is not None:
            stmt = stmt.where(Product.base_price <= filters.max_price)

        if filters.min_rating:
            stmt = stmt.where(Product.rating_average >= filters.min_rating)

        if filters.q:
            ts_vector = func.to_tsvector(
                "english",
                func.concat(Product.name, " ", func.coalesce(Product.description, "")),
            )
            stmt = stmt.where(ts_vector.op("@@")(func.plainto_tsquery("english", filters.q)))

        stmt = stmt.options(selectinload(Product.category))

        if filters.cursor:
            try:
                cursor_data = json.loads(base64.urlsafe_b64decode(filters.cursor.encode()).decode())
                cursor_id = cursor_data.get("id")
                cursor_value = cursor_data.get("created_at")
                if cursor_id and cursor_value:
                    cursor_dt = datetime.fromisoformat(cursor_value)
                    stmt = stmt.where(
                        or_(
                            Product.created_at < cursor_dt,
                            and_(Product.created_at == cursor_dt, Product.id < cursor_id),
                        )
                    )
            except Exception:
                pass

        stmt = stmt.order_by(Product.created_at.desc(), Product.id.desc())
        limit = filters.limit + 1
        result = await self.session.execute(stmt.limit(limit))
        items = list(result.scalars().all())

        has_more = len(items) > filters.limit
        items = items[: filters.limit]

        next_cursor = None
        if has_more and items:
            last = items[-1]
            cursor_payload = json.dumps(
                {"id": last.id, "created_at": last.created_at.isoformat()}
            ).encode()
            next_cursor = base64.urlsafe_b64encode(cursor_payload).decode()

        return CursorPagination(items=items, next_cursor=next_cursor, has_more=has_more)

    async def get_variant_by_id(self, variant_id: int) -> ProductVariant | None:
        stmt = select(ProductVariant).where(ProductVariant.id == variant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_variant_by_sku(self, sku: str) -> ProductVariant | None:
        stmt = select(ProductVariant).where(ProductVariant.sku == sku)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def sku_exists(self, sku: str) -> bool:
        stmt = select(ProductVariant).where(ProductVariant.sku == sku)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_reviews_by_product(self, product_id: int) -> list[Review]:
        stmt = select(Review).where(Review.product_id == product_id).order_by(Review.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def has_user_purchased_product(self, user_id: int, product_id: int) -> bool:
        stmt = (
            select(OrderItem)
            .join(Order)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.status.in_(["paid", "processing", "shipped", "delivered"]),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def update_product_rating(self, product_id: int) -> None:
        stmt = (
            select(func.avg(Review.rating), func.count(Review.id))
            .where(Review.product_id == product_id)
        )
        result = await self.session.execute(stmt)
        avg, count = result.one_or_none() or (0, 0)
        product = await self.get_by_id(product_id)
        if product:
            product.rating_average = Decimal(str(avg or 0))
            product.rating_count = count or 0
            self.session.add(product)
