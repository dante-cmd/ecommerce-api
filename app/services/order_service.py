from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.models.order import Order, OrderItem
from app.models.product import ProductVariant

from app.repositories.cart_repository import CartRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import UserRepository
from app.schemas.order import OrderCreate, OrderStatusUpdate
from app.services.pricing_service import PricingService
from app.tasks.email_tasks import send_order_confirmation_email, send_order_status_email


class OrderService:
    VALID_TRANSITIONS = {
        "pending": {"paid", "cancelled"},
        "paid": {"processing", "cancelled", "refunded"},
        "processing": {"shipped", "cancelled", "refunded"},
        "shipped": {"delivered", "refunded"},
        "delivered": {"refunded"},
        "cancelled": set(),
        "refunded": set(),
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.order_repo = OrderRepository(session)
        self.cart_repo = CartRepository(session)
        self.user_repo = UserRepository(session)
        self.product_repo = ProductRepository(session)

    async def _get_user_email(self, user_id: int) -> str:
        user = await self.user_repo.get_by_id(user_id)
        return user.email if user else "customer@example.com"

    async def create_order(self, user_id: int, data: OrderCreate) -> Order:
        user_email = await self._get_user_email(user_id)
        address = await self.user_repo.get_address_by_id(data.shipping_address_id)
        if not address or address.user_id != user_id:
            raise NotFoundException("Shipping address not found")

        cart = await self.cart_repo.get_by_user_id(user_id)
        if not cart or not cart.items:
            raise ValidationException("Cart is empty")

        subtotal = Decimal("0.00")
        order_items = []

        for cart_item in cart.items:
            variant = cart_item.variant
            if variant.stock_quantity < cart_item.quantity:
                raise ValidationException(
                    f"Insufficient stock for {variant.product.name} ({variant.sku})"
                )

            unit_price = Decimal(str(variant.product.base_price)) + Decimal(
                str(variant.price_adjustment or Decimal("0.00"))
            )
            total_price = unit_price * cart_item.quantity
            subtotal += total_price

            order_items.append(
                OrderItem(
                    product_id=variant.product_id,
                    variant_id=variant.id,
                    product_name=variant.product.name,
                    variant_name=f"{variant.size or ''} {variant.color or ''}".strip() or None,
                    unit_price=unit_price,
                    quantity=cart_item.quantity,
                    total_price=total_price,
                )
            )
            variant.stock_quantity -= cart_item.quantity
            self.session.add(variant)

        totals = PricingService.calculate_order_totals(subtotal, data.coupon_code)

        order = Order(
            user_id=user_id,
            status="pending",
            shipping_address=f"{address.street}, {address.city}, {address.state}, {address.postal_code}, {address.country}",
            subtotal=totals["subtotal"],
            shipping_cost=totals["shipping_cost"],
            tax_amount=totals["tax_amount"],
            discount_amount=totals["discount_amount"],
            total=totals["total"],
            coupon_code=data.coupon_code,
            notes=data.notes,
        )
        await self.order_repo.create(order)

        for item in order_items:
            item.order_id = order.id
            self.session.add(item)

        for cart_item in cart.items:
            await self.cart_repo.delete(cart_item)

        await self.session.flush()
        await self.session.refresh(order, attribute_names=["items"])
        send_order_confirmation_email.delay(order.id, str(order.total), user_email)
        return order

    async def get_order(self, user_id: int, order_id: int, is_admin: bool = False) -> Order:
        order = await self.order_repo.get_by_id_with_items(order_id)
        if not order:
            raise NotFoundException("Order not found")
        if order.user_id != user_id and not is_admin:
            raise ForbiddenException("Not allowed to view this order")
        return order

    async def list_user_orders(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Order]:
        return await self.order_repo.list_by_user(user_id, limit, offset)

    async def update_status(
        self, order_id: int, data: OrderStatusUpdate, is_admin: bool = False
    ) -> Order:
        order = await self.order_repo.get_by_id_with_items(order_id)
        if not order:
            raise NotFoundException("Order not found")

        if data.status not in self.VALID_TRANSITIONS:
            raise ValidationException(f"Invalid status: {data.status}")

        if data.status not in self.VALID_TRANSITIONS.get(order.status, set()):
            raise ValidationException(
                f"Cannot transition from {order.status} to {data.status}"
            )

        order.status = data.status
        await self.order_repo.update(order)
        await self.session.refresh(order, attribute_names=["items"])
        user_email = await self._get_user_email(order.user_id)
        send_order_status_email.delay(order.id, order.status, user_email)
        return order

    async def cancel_order(self, user_id: int, order_id: int) -> Order:
        order = await self.get_order(user_id, order_id)
        if order.status not in {"pending", "paid"}:
            raise ValidationException("Order cannot be cancelled")

        if order.status == "paid":
            # Restore stock only if payment already made; refunds handled separately
            for item in order.items:
                variant = await self.product_repo.get_variant_by_id(item.variant_id) if item.variant_id else None
                if variant:
                    variant.stock_quantity += item.quantity
                    self.session.add(variant)

        order.status = "cancelled"
        await self.order_repo.update(order)
        await self.session.refresh(order, attribute_names=["items"])
        user_email = await self._get_user_email(order.user_id)
        send_order_status_email.delay(order.id, order.status, user_email)
        return order
