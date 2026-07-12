import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.user import User


@pytest.mark.asyncio
async def test_list_all_orders_admin(async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession):
    user_id = admin_headers.pop("user_id")
    headers = admin_headers
    user = await db_session.get(User, user_id)
    order = Order(
        user_id=user_id,
        status="pending",
        shipping_address="123",
        subtotal=10.00,
        shipping_cost=0,
        tax_amount=0,
        discount_amount=0,
        total=10.00,
    )
    db_session.add(order)
    await db_session.flush()

    response = await async_client.get("/api/v1/admin/orders", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_dashboard_admin(async_client: AsyncClient, admin_headers: dict):
    headers = {k: v for k, v in admin_headers.items() if k != "user_id"}
    response = await async_client.get("/api/v1/admin/dashboard/sales", headers=headers)
    assert response.status_code == 200
    assert "total_sales" in response.json()
