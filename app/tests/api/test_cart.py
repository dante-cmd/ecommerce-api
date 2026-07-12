import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Category, Product, ProductVariant


@pytest.mark.asyncio
async def test_add_to_cart(async_client: AsyncClient, db_session: AsyncSession):
    category = Category(name="Cart Cat", slug="cart-cat")
    db_session.add(category)
    await db_session.flush()
    product = Product(name="Cart Product", slug="cart-product", category_id=category.id, base_price=15.00)
    db_session.add(product)
    await db_session.flush()
    variant = ProductVariant(product_id=product.id, sku="CART-001", stock_quantity=20)
    db_session.add(variant)
    await db_session.flush()

    response = await async_client.post("/api/v1/cart/items", json={"variant_id": variant.id, "quantity": 2})
    assert response.status_code == 201
    data = response.json()
    assert data["item_count"] == 2


@pytest.mark.asyncio
async def test_get_cart(async_client: AsyncClient, db_session: AsyncSession):
    response = await async_client.get("/api/v1/cart")
    assert response.status_code == 200
    assert "items" in response.json()
