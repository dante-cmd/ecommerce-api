from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import Cart, CartItem
from app.models.product import Category, Product, ProductVariant
from app.models.user import Address, User


@pytest.mark.asyncio
async def test_create_order(async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    user_id = auth_headers.pop("user_id")
    user = await db_session.get(User, user_id)
    category = Category(name="Order Cat", slug="order-cat")
    db_session.add(category)
    await db_session.flush()
    product = Product(name="Order Product", slug="order-product", category_id=category.id, base_price=Decimal("25.00"))
    db_session.add(product)
    await db_session.flush()
    variant = ProductVariant(product_id=product.id, sku="ORDER-001", stock_quantity=30)
    db_session.add(variant)
    address = Address(
        user_id=user_id,
        street="456 Oak",
        city="Town",
        state="TS",
        postal_code="54321",
        country="US",
    )
    db_session.add(address)
    await db_session.flush()

    cart = Cart(user_id=user_id)
    db_session.add(cart)
    await db_session.flush()
    db_session.add(CartItem(cart_id=cart.id, variant_id=variant.id, quantity=1))
    await db_session.flush()

    response = await async_client.post(
        "/api/v1/orders",
        json={"shipping_address_id": address.id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
