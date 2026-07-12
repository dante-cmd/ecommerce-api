from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem
from app.models.product import Product


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_sales_summary(self) -> dict:
        stmt = select(func.count(Order.id), func.coalesce(func.sum(Order.total), Decimal("0.00"))).where(
            Order.status.in_(["paid", "processing", "shipped", "delivered"])
        )
        result = await self.session.execute(stmt)
        count, total = result.one_or_none() or (0, Decimal("0.00"))
        return {"total_orders": count, "total_sales": float(total or 0)}

    async def get_top_products(self, limit: int = 5) -> list[dict]:
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.slug,
                func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status.in_(["paid", "processing", "shipped", "delivered"]))
            .group_by(Product.id)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {"id": row.id, "name": row.name, "slug": row.slug, "units_sold": row.units_sold}
            for row in rows
        ]

    async def get_low_stock_count(self, threshold: int = 10) -> int:
        from app.models.product import ProductVariant

        stmt = select(func.count(ProductVariant.id)).where(ProductVariant.stock_quantity <= threshold)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
