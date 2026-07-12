import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.models.cart import Cart, CartItem
from app.models.product import Category, Product, ProductVariant
from app.models.user import Address, User
from app.schemas.order import OrderCreate
from app.services.cart_service import CartService
from app.services.order_service import OrderService


@pytest.fixture
def order_service(db_session: AsyncSession):
    return OrderService(db_session)


@pytest.mark.asyncio
async def test_create_order_success(order_service: OrderService, db_session: AsyncSession):
    user = User(email="order@example.com", hashed_password="x", is_active=True, is_verified=True)
    category = Category(name="Music", slug="music")
    db_session.add_all([user, category])
    await db_session.flush()

    product = Product(name="Guitar", slug="guitar", category_id=category.id, base_price=199.99)
    db_session.add(product)
    await db_session.flush()
    variant = ProductVariant(product_id=product.id, sku="GT-001", stock_quantity=10)
    db_session.add(variant)
    address = Address(
        user_id=user.id,
        street="123 Main St",
        city="City",
        state="ST",
        postal_code="12345",
        country="US",
    )
    db_session.add(address)
    await db_session.flush()

    cart_service = CartService(db_session)
    from app.schemas.cart import CartItemCreate
    await cart_service.add_item(
        CartItemCreate(variant_id=variant.id, quantity=1), user_id=user.id
    )

    order = await order_service.create_order(user.id, OrderCreate(shipping_address_id=address.id))
    assert order.status == "pending"
    assert order.total > 0
    assert len(order.items) == 1


@pytest.mark.asyncio
async def test_create_order_empty_cart(order_service: OrderService, db_session: AsyncSession):
    user = User(email="order2@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()
    address = Address(
        user_id=user.id,
        street="123 Main St",
        city="City",
        state="ST",
        postal_code="12345",
        country="US",
    )
    db_session.add(address)
    await db_session.flush()

    with pytest.raises(ValidationException):
        await order_service.create_order(user.id, OrderCreate(shipping_address_id=address.id))


@pytest.mark.asyncio
async def test_invalid_status_transition(order_service: OrderService, db_session: AsyncSession):
    from app.models.order import Order
    user = User(email="order3@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()

    order = Order(
        user_id=user.id,
        status="cancelled",
        shipping_address="x",
        subtotal=10.00,
        shipping_cost=0,
        tax_amount=0,
        discount_amount=0,
        total=10.00,
    )
    db_session.add(order)
    await db_session.flush()

    from app.schemas.order import OrderStatusUpdate
    with pytest.raises(ValidationException):
        await order_service.update_status(order.id, OrderStatusUpdate(status="paid"))
