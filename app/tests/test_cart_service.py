import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Category, Product, ProductVariant
from app.models.user import User
from app.schemas.cart import CartItemCreate, CartItemUpdate
from app.services.cart_service import CartService


@pytest.fixture
def cart_service(db_session: AsyncSession):
    return CartService(db_session)


@pytest.mark.asyncio
async def test_add_item_to_cart(cart_service: CartService, db_session: AsyncSession):
    user = User(email="cart@example.com", hashed_password="x", is_active=True, is_verified=True)
    category = Category(name="Food", slug="food")
    db_session.add_all([user, category])
    await db_session.flush()

    product = Product(name="Snack", slug="snack", category_id=category.id, base_price=5.00)
    db_session.add(product)
    await db_session.flush()
    variant = ProductVariant(product_id=product.id, sku="SN-001", stock_quantity=10)
    db_session.add(variant)
    await db_session.flush()

    cart = await cart_service.add_item(CartItemCreate(variant_id=variant.id, quantity=2), user_id=user.id)
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2


@pytest.mark.asyncio
async def test_add_item_exceeds_stock(cart_service: CartService, db_session: AsyncSession):
    user = User(email="cart2@example.com", hashed_password="x", is_active=True, is_verified=True)
    category = Category(name="Drinks", slug="drinks")
    db_session.add_all([user, category])
    await db_session.flush()

    product = Product(name="Soda", slug="soda", category_id=category.id, base_price=2.00)
    db_session.add(product)
    await db_session.flush()
    variant = ProductVariant(product_id=product.id, sku="SO-001", stock_quantity=3)
    db_session.add(variant)
    await db_session.flush()

    from app.core.exceptions import ValidationException
    with pytest.raises(ValidationException):
        await cart_service.add_item(CartItemCreate(variant_id=variant.id, quantity=5), user_id=user.id)


@pytest.mark.asyncio
async def test_remove_item(cart_service: CartService, db_session: AsyncSession):
    user = User(email="cart3@example.com", hashed_password="x", is_active=True, is_verified=True)
    category = Category(name="Gear", slug="gear")
    db_session.add_all([user, category])
    await db_session.flush()

    product = Product(name="Bag", slug="bag", category_id=category.id, base_price=20.00)
    db_session.add(product)
    await db_session.flush()
    variant = ProductVariant(product_id=product.id, sku="BG-001", stock_quantity=10)
    db_session.add(variant)
    await db_session.flush()

    cart = await cart_service.add_item(CartItemCreate(variant_id=variant.id, quantity=1), user_id=user.id)
    cart = await cart_service.remove_item(cart.items[0].id, user_id=user.id, session_id=None)
    assert len(cart.items) == 0
