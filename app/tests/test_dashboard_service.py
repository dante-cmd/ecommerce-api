import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.user import User
from app.services.dashboard_service import DashboardService


@pytest.fixture
def dashboard_service(db_session: AsyncSession):
    return DashboardService(db_session)


@pytest.mark.asyncio
async def test_get_sales_summary(dashboard_service: DashboardService, db_session: AsyncSession):
    user = User(email="dash@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()
    order = Order(
        user_id=user.id,
        status="paid",
        shipping_address="123",
        subtotal=100.00,
        shipping_cost=0,
        tax_amount=0,
        discount_amount=0,
        total=100.00,
    )
    db_session.add(order)
    await db_session.flush()

    summary = await dashboard_service.get_sales_summary()
    assert summary["total_orders"] == 1
    assert summary["total_sales"] == 100.00
