import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Category, Product


@pytest.mark.asyncio
async def test_list_products(async_client: AsyncClient, db_session: AsyncSession):
    category = Category(name="Test Cat", slug="test-cat")
    db_session.add(category)
    await db_session.flush()
    product = Product(name="Test Product", slug="test-product", category_id=category.id, base_price=9.99)
    db_session.add(product)
    await db_session.flush()

    response = await async_client.get("/api/v1/products")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_get_product(async_client: AsyncClient, db_session: AsyncSession):
    category = Category(name="Test Cat 2", slug="test-cat-2")
    db_session.add(category)
    await db_session.flush()
    product = Product(name="Test Product 2", slug="test-product-2", category_id=category.id, base_price=19.99)
    db_session.add(product)
    await db_session.flush()

    response = await async_client.get("/api/v1/products/test-product-2")
    assert response.status_code == 200
    assert response.json()["slug"] == "test-product-2"


@pytest.mark.asyncio
async def test_create_product_admin(async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession):
    headers = {k: v for k, v in admin_headers.items() if k != "user_id"}
    category = Category(name="Admin Cat", slug="admin-cat")
    db_session.add(category)
    await db_session.flush()

    response = await async_client.post(
        "/api/v1/products",
        json={
            "name": "Admin Product",
            "slug": "admin-product",
            "category_id": category.id,
            "base_price": 49.99,
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "admin-product"


@pytest.mark.asyncio
async def test_create_product_forbidden(async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    headers = {k: v for k, v in auth_headers.items() if k != "user_id"}
    category = Category(name="User Cat", slug="user-cat")
    db_session.add(category)
    await db_session.flush()

    response = await async_client.post(
        "/api/v1/products",
        json={
            "name": "User Product",
            "slug": "user-product",
            "category_id": category.id,
            "base_price": 9.99,
        },
        headers=headers,
    )
    assert response.status_code == 403
